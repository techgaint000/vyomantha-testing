import { NextResponse } from 'next/server';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    
    // Retrieve the Frappe sid from cookies or query params
    const cookieHeader = request.headers.get('cookie') || '';
    let sid = searchParams.get('sid');
    
    if (!sid && cookieHeader) {
      const match = cookieHeader.match(/sid=([^;]+)/);
      if (match) sid = match[1];
    }
    
    if (!sid) {
      return NextResponse.json({ error: 'No active session identifier found.' }, { status: 401 });
    }
    
    const frappeUrl = process.env.FRAPPE_URL || 'https://vyomanta.onrender.com';
    const exchangeUrl = `${frappeUrl}/api/method/lms.lms.api.get_jwt`;
    
    console.warn(`[JWT Proxy] Requesting JWT from backend for session ${sid.slice(0, 10)}...`);
    
    const response = await fetch(exchangeUrl, {
      method: 'GET',
      headers: { 
        'Content-Type': 'application/json',
        'Cookie': `sid=${sid}`
      }
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[JWT Proxy] Frappe token exchange failed: ${response.status} - ${errorText}`);
      return NextResponse.json({ error: 'Failed to authenticate session with Frappe.' }, { status: response.status });
    }
    
    const data = await response.json();
    const token = data.message?.token;
    
    if (!token) {
      return NextResponse.json({ error: 'Failed to generate token on backend.' }, { status: 500 });
    }
    
    return NextResponse.json({ token });
  } catch (error) {
    console.error("[JWT Proxy API] Server exception:", error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
