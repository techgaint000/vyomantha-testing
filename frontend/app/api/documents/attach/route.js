import { NextResponse } from 'next/server';
import { verifyJwt } from '@/lib/auth';
import pool from '@/lib/db';
import crypto from 'crypto';

export async function POST(request) {
  try {
    const authHeader = request.headers.get('Authorization');
    const payload = verifyJwt(authHeader);
    if (!payload) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = payload.user_id;
    const tenantId = payload.tenant_id || 'default';

    const { file_name, file_key, sessionId } = await request.json();
    if (!file_name || !file_key || !sessionId) {
      return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
    }

    const docUuid = crypto.randomUUID();

    const connection = await pool.getConnection();
    try {
      await connection.beginTransaction();

      // 1. Verify that the requesting user owns at least one upload of this file_key
      const [ownership] = await connection.query(
        `SELECT name FROM test.\`tabLMS Session Document\` 
         WHERE file_key = ? AND owner = ? AND tenant_id = ? LIMIT 1`,
        [file_key, userId, tenantId]
      );

      if (ownership.length === 0) {
        await connection.rollback();
        return NextResponse.json({ error: 'Forbidden: You do not own this document.' }, { status: 403 });
      }

      // 2. Check if this document is already attached to this session
      const [existing] = await connection.query(
        `SELECT name FROM test.\`tabLMS Session Document\` 
         WHERE session_id = ? AND file_key = ? LIMIT 1`,
        [sessionId, file_key]
      );

      if (existing.length > 0) {
        return NextResponse.json({ 
          message: 'Document already attached to this session', 
          documentId: existing[0].name,
          status: 'completed'
        });
      }

      // Insert new document association
      await connection.query(
        `INSERT INTO test.\`tabLMS Session Document\` 
         (name, file_name, file_key, session_id, course_id, tenant_id, status, owner, docstatus, idx)
         VALUES (?, ?, ?, ?, 'general', ?, 'completed', ?, 0, 0)`,
        [docUuid, file_name, file_key, sessionId, tenantId, userId]
      );

      await connection.commit();
      
      return NextResponse.json({ 
        message: 'Attachment successful', 
        documentId: docUuid,
        status: 'completed'
      });
    } catch (err) {
      await connection.rollback();
      throw err;
    } finally {
      connection.release();
    }
  } catch (error) {
    console.error("[Documents Attach API] Server exception:", error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
