"""Step 4C.3 staging API: verifies Supabase access JWTs; does not persist sessions.

No credentials are logged or returned. Persistence/refresh/logout endpoints remain disabled.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware('http')
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response

@app.get('/api/session/health')
def health():
    return {'status': 'ok', 'component': 'session-api'}

@app.post('/api/session/verify')
def verify(authorization: str | None = Header(default=None)):
    """Check a supplied Supabase access token with Supabase Auth; return only verified user id."""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Bearer token required')
    token = authorization[7:].strip()
    if not token or len(token) > 8192 or any(c.isspace() for c in token):
        raise HTTPException(401, 'Invalid bearer token')
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    if not base.startswith('https://') or not key:
        raise HTTPException(503, 'Authentication service not configured')
    req = Request(base + '/auth/v1/user', headers={
        'apikey': key, 'Authorization': 'Bearer ' + token,
        'Accept': 'application/json',
    })
    try:
        with urlopen(req, timeout=8) as response:
            data = json.load(response)
    except HTTPError as exc:
        if exc.code in (400, 401, 403):
            raise HTTPException(401, 'Session not valid') from None
        raise HTTPException(503, 'Authentication provider unavailable') from None
    except (URLError, TimeoutError, ValueError, OSError):
        raise HTTPException(503, 'Authentication provider unavailable') from None
    uid = data.get('id') if isinstance(data, dict) else None
    if not isinstance(uid, str) or not uid:
        raise HTTPException(401, 'Session not valid')
    return {'valid': True, 'user_id': uid}

@app.api_route('/api/session/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def unavailable(path: str):
    return JSONResponse(status_code=501, content={'error': 'Session persistence is not enabled'})
