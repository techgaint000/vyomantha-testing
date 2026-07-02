import os
import sys
import time
import json
import uuid
import requests
import pymysql
import boto3
from botocore.client import Config

# Ensure stdout is unbuffered for clean Render logs
sys.stdout.reconfigure(line_buffering=True)

# Parse database connection from environment
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "4000"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "123")
DB_NAME = os.environ.get("DB_NAME", "test")
DB_RESOURCES_NAME = os.environ.get("DB_RESOURCES_NAME", "pdf_resources_db")

# B2 configuration
B2_KEY_ID = os.environ.get("B2_KEY_ID")
B2_APPLICATION_KEY = os.environ.get("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.environ.get("B2_BUCKET_NAME")
B2_ENDPOINT = os.environ.get("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")
B2_REGION = os.environ.get("B2_REGION", "us-west-004")

# Redis configuration
UPSTASH_REDIS_REST_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_REDIS_REST_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

# API Keys rotation setup
API_KEYS = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_1"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
    os.environ.get("GEMINI_API_KEY_4")
]
API_KEYS = [k for k in API_KEYS if k]

def get_rotated_key(attempt):
    if not API_KEYS:
        return None
    return API_KEYS[attempt % len(API_KEYS)]

def get_db_connection():
    ssl_config = None
    if os.environ.get("DB_SSL") == "true":
        ssl_config = {'ca': '/etc/ssl/certs/ca-certificates.crt'}
        
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl=ssl_config,
        autocommit=True
    )

def publish_status(document_id, status, error_message=None):
    if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
        print("Redis config missing, skipping status publish.")
        return
    
    payload = {
        "documentId": document_id,
        "status": status,
        "error": error_message
    }
    
    url = f"{UPSTASH_REDIS_REST_URL}/publish/document:status:{document_id}"
    headers = {
        "Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # Publish the event via Upstash REST Pub/Sub
        requests.post(url, headers=headers, data=json.dumps(json.dumps(payload)))
        print(f"Published status '{status}' for document {document_id}")
    except Exception as e:
        print(f"Failed to publish status via Redis: {e}")

def get_embedding_with_retry(text, attempt=0, retries=5, base_delay=1):
    api_key = get_rotated_key(attempt)
    if not api_key:
        raise Exception("No active Gemini API keys configured.")
        
    for i in range(retries):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": 768
            }
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if res.status_code == 429:
                delay = base_delay * (2 ** i)
                print(f"Gemini API rate limit (429). Retrying chunk in {delay}s...")
                time.sleep(delay)
                continue
                
            data = res.json()
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown API error")
                if data["error"].get("code") in [429, 503]:
                    delay = base_delay * (2 ** i)
                    print(f"Gemini API error ({data['error'].get('code')}). Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(error_msg)
            
            return data["embedding"]["values"]
        except Exception as e:
            if i == retries - 1:
                raise e
            delay = base_delay * (2 ** i)
            print(f"Network error: {e}. Retrying chunk in {delay}s...")
            time.sleep(delay)
            
    raise Exception("Failed to fetch embedding after max retries.")

def split_text(text, chunk_size=1000, overlap=200):
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= chunk_size:
            current_chunk += (p + '\n\n')
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            if len(p) > chunk_size:
                lines = p.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= chunk_size:
                        current_chunk += (line + '\n')
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        if len(line) > chunk_size:
                            words = line.split(' ')
                            for word in words:
                                if len(current_chunk) + len(word) + 1 <= chunk_size:
                                    current_chunk += (word + ' ')
                                else:
                                    if current_chunk:
                                        chunks.append(current_chunk.strip())
                                    current_chunk = word + ' '
                        else:
                            current_chunk = line + '\n'
            else:
                current_chunk = p + '\n\n'
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    final_chunks = []
    for i, chunk in enumerate(chunks):
        if i > 0 and overlap > 0:
            prev = chunks[i-1]
            overlap_text = prev[-overlap:] if len(prev) > overlap else prev
            chunk = overlap_text + "\n" + chunk
        final_chunks.append(chunk)
    return final_chunks

def process_job(conn, job):
    job_id = job["id"]
    doc_id = job["document_id"]
    tenant_id = job["tenant_id"]
    attempts = job["attempts"]
    
    print(f"Processing job {job_id} for document {doc_id} (Attempt {attempts + 1})")
    
    # 1. Update status to running
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE `LMS Background Job Queue` SET status = 'running', attempts = attempts + 1 WHERE id = %s",
            (job_id,)
        )
        cursor.execute(
            "UPDATE `tabLMS Session Document` SET status = 'processing' WHERE name = %s",
            (doc_id,)
        )
    
    publish_status(doc_id, "processing")
    
    local_pdf = f"/tmp/{doc_id}.pdf"
    
    try:
        # 2. Get document metadata
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT file_key, owner, session_id, course_id FROM `tabLMS Session Document` WHERE name = %s",
                (doc_id,)
            )
            doc_meta = cursor.fetchone()
            
        if not doc_meta:
            raise Exception("Document metadata not found in database.")
            
        file_key = doc_meta["file_key"]
        user_id = doc_meta["owner"]
        session_id = doc_meta["session_id"]
        course_id = doc_meta["course_id"]
        
        # 3. Download from B2
        print(f"Downloading from B2: Key={file_key}")
        resolved_region = B2_REGION
        if B2_ENDPOINT and 'backblazeb2.com' in B2_ENDPOINT:
            parts = B2_ENDPOINT.split('.')
            if len(parts) >= 2 and parts[1] != 'backblazeb2':
                resolved_region = parts[1]
                
        s3 = boto3.client(
            's3',
            endpoint_url=B2_ENDPOINT,
            aws_access_key_id=B2_KEY_ID,
            aws_secret_access_key=B2_APPLICATION_KEY,
            region_name=resolved_region,
            config=Config(signature_version='s3v4')
        )
        s3.download_file(B2_BUCKET_NAME, file_key, local_pdf)
        
        # 4. Parse PDF text page-by-page
        print("Extracting text and chunking...")
        from pypdf import PdfReader
        reader = PdfReader(local_pdf)
        
        all_chunks = []
        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            text = page.extract_text() or ""
            if not text.strip():
                continue
            # Split text of this page
            page_chunks = split_text(text, chunk_size=1000, overlap=200)
            for chunk_idx, content in enumerate(page_chunks):
                all_chunks.append({
                    "content": content,
                    "page_number": page_num,
                    "chunk_index": len(all_chunks)
                })
                
        if not all_chunks:
            raise Exception("No readable text found in PDF document.")
            
        # 5. Embed and save chunks
        print(f"Generating embeddings for {len(all_chunks)} chunks...")
        with conn.cursor() as cursor:
            # Delete any existing chunks for this document in case of retries
            cursor.execute("DELETE FROM `LMS Document Chunk` WHERE document_id = %s", (doc_id,))
            
            for idx, chunk in enumerate(all_chunks):
                content = chunk["content"]
                page_num = chunk["page_number"]
                chunk_idx = chunk["chunk_index"]
                
                # Fetch embedding (pass index to rotate API keys)
                vector = get_embedding_with_retry(content, attempt=attempts + idx)
                
                # Insert chunk row
                chunk_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO `LMS Document Chunk` 
                    (id, document_id, session_id, user_id, course_id, tenant_id, chunk_index, page_number, content, embedding, embedding_model, embedding_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'gemini-embedding-001', 'v1')
                    """,
                    (chunk_id, doc_id, session_id, user_id, course_id, tenant_id, chunk_idx, page_num, content, str(vector))
                )
                
        # 6. Complete Job
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE `LMS Background Job Queue` SET status = 'completed' WHERE id = %s",
                (job_id,)
            )
            cursor.execute(
                "UPDATE `tabLMS Session Document` SET status = 'completed' WHERE name = %s",
                (doc_id,)
            )
        publish_status(doc_id, "completed")
        print(f"Job {job_id} completed successfully.")
        
    except Exception as err:
        print(f"Error processing job {job_id}: {err}")
        err_msg = str(err)
        with conn.cursor() as cursor:
            if attempts + 1 >= job["max_attempts"]:
                cursor.execute(
                    "UPDATE `LMS Background Job Queue` SET status = 'failed', error_message = %s WHERE id = %s",
                    (err_msg, job_id)
                )
                cursor.execute(
                    "UPDATE `tabLMS Session Document` SET status = 'failed' WHERE name = %s",
                    (doc_id,)
                )
                publish_status(doc_id, "failed", err_msg)
            else:
                cursor.execute(
                    "UPDATE `LMS Background Job Queue` SET status = 'queued', error_message = %s WHERE id = %s",
                    (err_msg, job_id)
                )
                publish_status(doc_id, "retrying", err_msg)
                
    finally:
        # Clean up local file
        if os.path.exists(local_pdf):
            try:
                os.remove(local_pdf)
            except Exception:
                pass

def main():
    print("🚀 TiDB Vector Ingestion Queue Worker started.")
    print(f"Configured DB: {DB_HOST}:{DB_PORT} (User={DB_USER})")
    
    while True:
        try:
            conn = get_db_connection()
            with conn:
                while True:
                    # 1. Fetch next queued job with SKIP LOCKED row-locking
                    job = None
                    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                        # Transaction block for row lock
                        conn.begin()
                        cursor.execute(
                            """
                            SELECT id, document_id, tenant_id, attempts, max_attempts 
                            FROM `LMS Background Job Queue`
                            WHERE status = 'queued'
                            ORDER BY created_at ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                            """
                        )
                        job = cursor.fetchone()
                        
                        if job:
                            # We got a job, process it
                            process_job(conn, job)
                            conn.commit()
                        else:
                            # Rollback/release empty search transaction
                            conn.rollback()
                            
                    if not job:
                        # Queue is empty, sleep for 3 seconds before next poll
                        time.sleep(3)
                        
        except pymysql.MySQLError as db_err:
            print(f"Database error: {db_err}. Reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected worker loop exception: {e}. Retrying in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()
