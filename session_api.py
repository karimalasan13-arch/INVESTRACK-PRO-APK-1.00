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

import hmac
import json
import secrets
import threading
import time
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



# ---------------------------------------------------------------------------
# Step 4C: SHORT-LIVED, SINGLE-USE HANDOFF (STAGING ONLY)
# ---------------------------------------------------------------------------
# Supabase credentials never cross into Streamlit's browser document. A native
# client may obtain a bearer *ticket*, not an access token. Only Streamlit's
# backend can redeem it over the private loopback connection.
#
# This is intentionally in-memory: FastAPI and Streamlit run as two processes
# in ONE supervised Render staging container. This configuration MUST use one
# uvicorn worker, and does not support multiple replica containers. A restart
# invalidates unused tickets safely. The existing /refresh endpoint is kept.
_TICKET_TTL = 30.0
_MAX_PENDING_TICKETS = 256
_pending_tickets: dict[str, tuple[float, str, str, str]] = {}
_pending_tickets_lock = threading.Lock()


def _bridge_secret() -> str:
    value = os.environ.get('IV_QUICKLOGIN_BRIDGE_SECRET', '')
    if len(value) < 40 or not value.isascii():
        raise HTTPException(503, 'Quick Login handoff not configured')
    return value


def _remove_expired_locked(now: float):
    for ticket, record in tuple(_pending_tickets.items()):
        if record[0] <= now:
            del _pending_tickets[ticket]


@app.post('/api/session/quick-login/start')
async def start_quick_login(request: FastAPIRequest):
    """Android native HTTPS request AFTER a successful Keystore unlock.

    Accepts exactly the existing /refresh payload:
       {"refresh_token": "...", "expected_user_id": "UUID"}
    Returns ONLY a short-lived one-time ticket and the rotated refresh token
    for the Android secure vault. The Supabase access token is retained within
    this private Python process, NEVER returned to the Android WebView.

    The native client MUST securely update its vault with the rotated token
    before proceeding with ticket delivery; otherwise require password login.
    """
    _bridge_secret()  # Fail before rotating Supabase token when unconfigured.
    with _pending_tickets_lock:
        _remove_expired_locked(time.monotonic())
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            raise HTTPException(429, 'Quick Login temporarily busy')

    # Reuse the already-tested refresh validation and Supabase identity check.
    refreshed = await refresh_session(request)
    data = json.loads(refreshed.body)
    account = data['user_id']
    access = data['access_token']
    rotated = data['refresh_token']

    with _pending_tickets_lock:
        now = time.monotonic()
        _remove_expired_locked(now)
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            # Refresh token was rotated but the ticket could not be issued;
            # return no credentials and require normal password login.
            raise HTTPException(429, 'Quick Login temporarily busy')
        ticket = secrets.token_urlsafe(32)  # 256 bits, URL-safe but NEVER put in URL.
        _pending_tickets[ticket] = (now + _TICKET_TTL, account, access, rotated)

    return JSONResponse(content={
        'ticket': ticket,
        'user_id': account,
        'rotated_refresh_token': rotated,
        'ticket_expires_in': int(_TICKET_TTL),
    })


@app.post('/api/session/quick-login/claim')
async def claim_quick_login(request: FastAPIRequest):
    """STREAMLIT SERVER-ONLY via http://127.0.0.1:8502. Not a WebView API.

    Requires a Render environment secret and rejects requests forwarded by
    the nginx public proxy. The nonce is single-use, expires in 30 seconds,
    and returns credentials only to the trusted server-side Streamlit code.
    A successful claim does NOT by itself sign anybody into Streamlit: the
    caller MUST invoke auth.restore_verified_session and verify the user ID.
    """
    secret = _bridge_secret()
    # The existing nginx staging proxy always appends X-Forwarded-For on
    # publicly routed requests. Private Streamlit -> FastAPI calls do not.
    if 'x-forwarded-for' in request.headers or 'forwarded' in request.headers:
        raise HTTPException(404, 'Not found')
    supplied = request.headers.get('x-iv-quicklogin-bridge', '')
    if not supplied or not hmac.compare_digest(supplied, secret):
        raise HTTPException(404, 'Not found')
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')

    body = await request.body()
    if len(body) > 512:
        raise HTTPException(413, 'Request too large')
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    if not isinstance(data, dict) or set(data) != {'ticket'}:
        raise HTTPException(400, 'Invalid request')
    ticket = data['ticket']
    if not (isinstance(ticket, str) and len(ticket) == 43
            and all(c.isalnum() or c in '-_' for c in ticket)):
        raise HTTPException(400, 'Invalid request')

    with _pending_tickets_lock:
        now = time.monotonic()
        record = _pending_tickets.pop(ticket, None)  # Consume atomically.
        _remove_expired_locked(now)
    if record is None or now >= record[0]:
        raise HTTPException(401, 'Quick Login ticket invalid or expired')
    _, account, access, rotated = record
    return JSONResponse(content={
        'valid': True,
        'user_id': account,
        'access_token': access,
        'refresh_token': rotated,
    })


# ---------------------------------------------------------------------------
# Step 4F: STAGING-ONLY PAIRING FOUNDATION (not wired to Android/Streamlit yet)
# ---------------------------------------------------------------------------
# Streamlit server creates a random challenge for its own session and renders
# ONLY that challenge in the trusted login page. Android reads the challenge,
# obtains a ticket using the existing biometric/native flow, and sends both
# directly to /pair/attach over HTTPS (never through JavaScript). Streamlit
# polls /pair/consume using its private server-side challenge. The challenge
# alone never grants access: a valid native ticket must also be attached.
#
# This in-memory pairing store requires a single FastAPI worker/replica.
_PAIR_TTL = 45.0
_MAX_PAIRS = 256
_pairings: dict[str, dict] = {}
_pair_lock = threading.Lock()


def _private_bridge(request: FastAPIRequest):
    secret = _bridge_secret()
    # Defense in depth: the bridge is only available on loopback, and public
    # reverse-proxy requests are rejected even if they know the bridge secret.
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(404, 'Not found')
    if 'x-forwarded-for' in request.headers or 'forwarded' in request.headers:
        raise HTTPException(404, 'Not found')
    supplied = request.headers.get('x-iv-quicklogin-bridge', '')
    if not supplied or not hmac.compare_digest(supplied, secret):
        raise HTTPException(404, 'Not found')


def _pair_cleanup(now):
    for challenge, record in tuple(_pairings.items()):
        if record['expires'] <= now:
            del _pairings[challenge]


def _valid_pair_challenge(value):
    return isinstance(value, str) and len(value) == 43 and all(
        c.isalnum() or c in '-_' for c in value)


async def _bounded_pair_json(request: FastAPIRequest):
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 512:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        body.clear()
    if not isinstance(data, dict):
        raise HTTPException(400, 'Invalid request')
    return data


@app.post('/api/session/quick-login/pair/create')
async def create_quick_login_pair(request: FastAPIRequest):
    """Streamlit server ONLY. Keep challenge in that Streamlit session_state."""
    _private_bridge(request)
    data = await _bounded_pair_json(request)
    if data != {}:
        raise HTTPException(400, 'Invalid request')
    with _pair_lock:
        now = time.monotonic()
        _pair_cleanup(now)
        if len(_pairings) >= _MAX_PAIRS:
            raise HTTPException(429, 'Quick Login temporarily busy')
        challenge = secrets.token_urlsafe(32)
        _pairings[challenge] = {'expires': now + _PAIR_TTL, 'ticket': None}
    return JSONResponse({'challenge': challenge, 'expires_in': int(_PAIR_TTL)})


@app.post('/api/session/quick-login/pair/attach')
async def attach_quick_login_pair(request: FastAPIRequest):
    """Android native HTTPS ONLY; no credentials in JS, URL or Intents.

    A ticket is accepted only once and only for an existing pending challenge.
    The ticket is not consumed until the owning Streamlit server claims it.
    """
    _bridge_secret()
    data = await _bounded_pair_json(request)
    if set(data) != {'challenge', 'ticket'}:
        raise HTTPException(400, 'Invalid request')
    challenge, ticket = data['challenge'], data['ticket']
    if not _valid_pair_challenge(challenge) or not _valid_pair_challenge(ticket):
        raise HTTPException(400, 'Invalid request')
    # Serialize both stores to prevent two pairings claiming the same ticket.
    with _pair_lock:
        with _pending_tickets_lock:
            now = time.monotonic()
            _pair_cleanup(now)
            _remove_expired_locked(now)
            record = _pairings.get(challenge)
            if record is None or record['ticket'] is not None:
                raise HTTPException(401, 'Pairing invalid or unavailable')
            if ticket not in _pending_tickets:
                raise HTTPException(401, 'Ticket invalid or expired')
            if any(p['ticket'] == ticket for p in _pairings.values()):
                raise HTTPException(401, 'Ticket already attached')
            record['ticket'] = ticket
    return JSONResponse({'attached': True})


@app.post('/api/session/quick-login/pair/consume')
async def consume_quick_login_pair(request: FastAPIRequest):
    """Streamlit server ONLY. Caller must restore and verify user identity."""
    _private_bridge(request)
    data = await _bounded_pair_json(request)
    if set(data) != {'challenge'} or not _valid_pair_challenge(data['challenge']):
        raise HTTPException(400, 'Invalid request')
    with _pair_lock:
        with _pending_tickets_lock:
            now = time.monotonic()
            _pair_cleanup(now)
            record = _pairings.get(data['challenge'])
            if record is None:
                raise HTTPException(401, 'Pairing expired or invalid')
            ticket = record['ticket']
            if ticket is None:
                return JSONResponse({'status': 'pending'}, status_code=202)
            del _pairings[data['challenge']]
            credentials = _pending_tickets.pop(ticket, None)
            _remove_expired_locked(now)
    if credentials is None or credentials[0] <= now:
        raise HTTPException(401, 'Ticket expired or invalid')
    _, account, access, rotated = credentials
    return JSONResponse({'valid': True, 'user_id': account,
                         'access_token': access, 'refresh_token': rotated})


@app.api_route('/api/session/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def unavailable(path: str):
    return JSONResponse(status_code=501, content={
        'error': 'Session persistence is not enabled'
    })
