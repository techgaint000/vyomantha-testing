import { NextResponse } from 'next/server';
import { verifyJwt } from '@/lib/auth';
import pool from '@/lib/db';

export async function GET(request) {
  try {
    const authHeader = request.headers.get('Authorization');
    const payload = verifyJwt(authHeader);
    if (!payload) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    const userId = payload.user_id;
    const tenantId = payload.tenant_id || 'default';

    // Fetch all documents uploaded by this user, grouping by file_key to avoid duplicates
    const [docs] = await pool.query(
      `SELECT name as id, file_name as name, file_key, status, creation 
       FROM test.\`tabLMS Session Document\` 
       WHERE owner = ? AND tenant_id = ? AND status = 'completed'
       GROUP BY file_key
       ORDER BY creation DESC`,
      [userId, tenantId]
    );

    return NextResponse.json({ documents: docs });
  } catch (error) {
    console.error("[Documents List API] Server exception:", error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
