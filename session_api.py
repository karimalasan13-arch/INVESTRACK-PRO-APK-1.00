"""InvesTrack Pro STAGING session API.

Verifies Supabase JWTs and rotates a refresh token for the native Android app.
The API is stateless. It does NOT authenticate any Streamlit websocket or
session_state, does not enroll a device, and does not enable Quick Login by itself.

SECURITY:
- Use ONLY behind HTTPS on staging; no browser/JavaScript exposure of tokens.
- Do not log tokens, request bodies, or responses.
- Never put tokens in query strings, cookies, or Android deep links.
- The original /verify endpoint is retained.
"""

import json
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException, Request as FastAPIRequest
from fastapi.responses import JSONResponse


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_MAX_TOKEN_LENGTH = 8192
_MAX_BODY_BYTES = 10000


@app.middleware('http')
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store, private, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@app.get('/api/session/health')
def health():
    return {'status': 'ok', 'component': 'session-api'}


@app.post('/api/session/verify')
def verify(authorization: str | None = Header(default=None)):
    """Check a supplied access token with Supabase Auth; return verified user ID."""
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


def _safe_token(value) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= _MAX_TOKEN_LENGTH
            and value.isascii()
            and not any(ch.isspace() or ord(ch) < 33 or ord(ch) == 127
                        for ch in value))


def _configuration():
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    if not base.startswith('https://') or not key:
        raise HTTPException(503, 'Authentication service not configured')
    return base, key


def _supabase_json(req: Request):
    """Read bounded provider JSON, without ever logging token material."""
    try:
        with urlopen(req, timeout=8) as response:
            payload = response.read(_MAX_BODY_BYTES * 4 + 1)
        if len(payload) > _MAX_BODY_BYTES * 4:
            raise HTTPException(503, 'Authentication provider unavailable')
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise HTTPException(503, 'Authentication provider unavailable')
        return data
    except HTTPError as exc:
        if exc.code in (400, 401, 403, 422):
            raise HTTPException(401, 'Session not valid') from None
        raise HTTPException(503, 'Authentication provider unavailable') from None
    except (URLError, TimeoutError, ValueError, OSError, UnicodeError):
        raise HTTPException(503, 'Authentication provider unavailable') from None


@app.post('/api/session/refresh')
async def refresh_session(request: FastAPIRequest):
    """Native-only Supabase refresh-token rotation, with account-ID match.

    Request:  {"refresh_token": "...", "expected_user_id": "UUID"}
    Response: valid, user_id, access_token, refresh_token, expires_in.

    This endpoint MUST NOT be called from browser JavaScript or a WebView.
    Unlock of the Android Keystore vault must precede the native request.
    A successful response is NOT a Streamlit login; a separate server-only
    session attachment mechanism is required before exposing protected data.
    """
    media_type = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if media_type != 'application/json':
        raise HTTPException(415, 'JSON body required')

    # Stream, rather than unbounded request.body(), to cap attacker input.
    buffer = bytearray()
    async for chunk in request.stream():
        if len(buffer) + len(chunk) > _MAX_BODY_BYTES:
            raise HTTPException(413, 'Request too large')
        buffer.extend(chunk)

    try:
        payload = json.loads(buffer)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        buffer.clear()

    if not isinstance(payload, dict) or set(payload) != {'refresh_token', 'expected_user_id'}:
        raise HTTPException(400, 'Invalid request')

    supplied_token = payload['refresh_token']
    expected_id = payload['expected_user_id']
    if not _safe_token(supplied_token) or not isinstance(expected_id, str):
        raise HTTPException(400, 'Invalid request')
    try:
        expected_id = str(uuid.UUID(expected_id))
    except (ValueError, AttributeError):
        raise HTTPException(400, 'Invalid request') from None

    base, key = _configuration()
    # Supabase GoTrue refresh grant. The refresh token is never in the URL.
    exchange = Request(
        base + '/auth/v1/token?grant_type=refresh_token',
        data=json.dumps({'refresh_token': supplied_token}).encode('utf-8'),
        headers={'apikey': key, 'Content-Type': 'application/json',
                 'Accept': 'application/json'},
        method='POST',
    )
    session = _supabase_json(exchange)
    access = session.get('access_token')
    rotated = session.get('refresh_token')
    if not _safe_token(access) or not _safe_token(rotated):
        raise HTTPException(401, 'Session not valid')

    # Verify against Supabase, NOT against the user supplied by the Android app
    # and not merely the (unverified) user object in the refresh response.
    check = Request(base + '/auth/v1/user', headers={
        'apikey': key, 'Authorization': 'Bearer ' + access,
        'Accept': 'application/json',
    }, method='GET')
    verified_user = _supabase_json(check)
    verified_id = verified_user.get('id')
    try:
        verified_id = str(uuid.UUID(verified_id))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(401, 'Session not valid') from None
    if verified_id != expected_id:
        # The supplied refresh token was consumed by Supabase. The caller
        # must discard this response and fall back to manual sign-in.
        raise HTTPException(401, 'Account does not match')

    expires = session.get('expires_in')
    if not isinstance(expires, int) or isinstance(expires, bool) or expires <= 0:
        expires = None

    return JSONResponse(content={
        'valid': True,
        'user_id': verified_id,
        'access_token': access,
        'refresh_token': rotated,
        'expires_in': expires,
    })


@app.api_route('/api/session/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def unavailable(path: str):
    return JSONResponse(status_code=501, content={
        'error': 'Session persistence is not enabled'
    })
