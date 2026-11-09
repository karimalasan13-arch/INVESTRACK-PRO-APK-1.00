"""InvesTrack Pro session API — Step 5I.43B transaction-ready guest restoration.

Verifies Supabase JWTs and rotates a refresh token for the native Android app.
The API is stateless. It does NOT authenticate any Streamlit websocket or
session_state, does not enroll a device, and does not enable Quick Login by itself.

SECURITY:
- Use ONLY behind HTTPS; no browser/JavaScript exposure of tokens.
- Do not log tokens, request bodies, or responses.
- Never put tokens in query strings, cookies, or Android deep links.
- The original /verify endpoint is retained.
"""

import hmac
import hashlib
import json
import logging
import secrets
import threading
import time
import os
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, Header, HTTPException, Request as FastAPIRequest
from fastapi.responses import JSONResponse, HTMLResponse


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
        # Step 5I.36: Diagnose failed Supabase refreshes without logging secrets.
        # Do not log the provider response, exception, URL, headers or tokens.
        if req.full_url.split('?', 1)[0].endswith('/auth/v1/token'):
            category = 'unknown'
            try:
                raw = exc.read(4096)
                error_data = json.loads(raw)
                if isinstance(error_data, dict):
                    # Explicit allowlist: arbitrary provider messages may contain
                    # sensitive details and must never reach application logs.
                    known_codes = {
                        'refresh_token_not_found', 'refresh_token_already_used',
                        'invalid_grant', 'invalid_refresh_token',
                        'session_not_found', 'session_expired',
                        'user_not_found', 'invalid_credentials',
                    }
                    code = error_data.get('error_code') or error_data.get('code')
                    if isinstance(code, str) and code in known_codes:
                        category = code
                    elif isinstance(error_data.get('error'), str):
                        # Supabase sometimes supplies an error label instead of
                        # error_code; accept only the same fixed categories.
                        label = error_data['error']
                        if label in known_codes:
                            category = label
            except (OSError, ValueError, UnicodeError):
                pass
            logging.getLogger('investrack.session').warning(
                'IV_REFRESH_DIAG provider_status=%s category=%s',
                exc.code if exc.code in (400, 401, 403, 404, 422, 429, 500, 502, 503, 504) else 'other',
                category,
            )
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
# Step 5I.43B: Opt-in, durable native guest refresh transactions.
# Existing /quick-login/start remains unchanged until Android is upgraded.
# Requires cryptography (AESGCM), IV_GUEST_REFRESH_ENCRYPTION_KEY, and
# the restricted public.iv_guest_refresh_transactions table.
# A pending record deliberately blocks replay after an uncertain exchange.
# ---------------------------------------------------------------------------

def _guest_tx_key():
    raw = os.environ.get('IV_GUEST_REFRESH_ENCRYPTION_KEY', '')
    if len(raw) != 64:
        raise HTTPException(503, 'Guest transaction encryption unavailable')
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        raise HTTPException(503, 'Guest transaction encryption unavailable') from None
    if len(key) != 32:
        raise HTTPException(503, 'Guest transaction encryption unavailable')
    return key


def _guest_tx_cipher():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise HTTPException(503, 'Guest transaction encryption unavailable') from None
    return AESGCM(_guest_tx_key())


def _guest_tx_fingerprint(token, account):
    # Keyed digest: raw refresh tokens and their unsalted hashes are not stored.
    return hmac.new(_guest_tx_key(),
                    (account + ':' + token).encode('utf-8'), hashlib.sha256).hexdigest()


def _guest_tx_encrypt(request_id, account, data):
    nonce = secrets.token_bytes(12)
    associated = (request_id + ':' + account).encode('ascii')
    ciphertext = _guest_tx_cipher().encrypt(
        nonce, json.dumps(data, separators=(',', ':')).encode('utf-8'), associated)
    import base64
    return base64.b64encode(nonce + ciphertext).decode('ascii')


def _guest_tx_decrypt(request_id, account, encoded):
    import base64
    try:
        packed = base64.b64decode(encoded, validate=True)
        if len(packed) < 29:
            raise ValueError('Invalid encrypted transaction')
        plain = _guest_tx_cipher().decrypt(
            packed[:12], packed[12:], (request_id + ':' + account).encode('ascii'))
        result = json.loads(plain)
        if not isinstance(result, dict):
            raise ValueError('Invalid transaction')
        return result
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(503, 'Guest transaction unavailable') from None
    except Exception:
        raise HTTPException(503, 'Guest transaction unavailable') from None


def _guest_tx_rest(method, path, body=None, *, prefer=None):
    base, _ = _configuration()
    role = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not role:
        raise HTTPException(503, 'Guest transaction storage unavailable')
    headers = {'apikey': role, 'Authorization': 'Bearer ' + role,
               'Accept': 'application/json', 'Content-Type': 'application/json'}
    if prefer:
        headers['Prefer'] = prefer
    req = Request(base + '/rest/v1/iv_guest_refresh_transactions' + path,
                  data=(json.dumps(body).encode('utf-8') if body is not None else None),
                  headers=headers, method=method)
    try:
        with urlopen(req, timeout=8) as response:
            raw = response.read(32769)
            if len(raw) > 32768:
                raise ValueError('Oversized transaction')
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        if exc.code == 409:
            raise HTTPException(409, 'Guest transaction already reserved') from None
        raise HTTPException(503, 'Guest transaction storage unavailable') from None
    except (URLError, TimeoutError, ValueError, OSError):
        raise HTTPException(503, 'Guest transaction storage unavailable') from None


def _guest_tx_lookup(request_id):
    from urllib.parse import quote
    result = _guest_tx_rest('GET', '?request_id=eq.' + quote(request_id, safe='')
                            + '&select=request_id,user_id,request_fingerprint,status,encrypted_response,expires_at')
    if not isinstance(result, list) or len(result) > 1:
        raise HTTPException(503, 'Guest transaction storage unavailable')
    return result[0] if result else None


def _guest_tx_issue_ticket(account, access, rotated):
    _bridge_secret()
    if not (_safe_token(access) and _safe_token(rotated)):
        raise HTTPException(503, 'Guest transaction unavailable')
    with _pending_tickets_lock:
        now = time.monotonic()
        _remove_expired_locked(now)
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            raise HTTPException(429, 'Quick Login temporarily busy')
        ticket = secrets.token_urlsafe(32)
        _pending_tickets[ticket] = (now + _TICKET_TTL, account, access, rotated)
    return {'ticket': ticket, 'user_id': account,
            'rotated_refresh_token': rotated, 'ticket_expires_in': int(_TICKET_TTL)}


async def _guest_tx_payload(request, required):
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    if request.headers.get('origin'):
        raise HTTPException(403, 'Native client required')
    buffer = bytearray()
    async for chunk in request.stream():
        if len(buffer) + len(chunk) > _MAX_BODY_BYTES:
            raise HTTPException(413, 'Request too large')
        buffer.extend(chunk)
    try:
        data = json.loads(buffer)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        buffer.clear()
    if not isinstance(data, dict) or set(data) != required:
        raise HTTPException(400, 'Invalid request')
    try:
        data['request_id'] = str(uuid.UUID(data['request_id']))
        data['expected_user_id'] = str(uuid.UUID(data['expected_user_id']))
    except (ValueError, TypeError, AttributeError, KeyError):
        raise HTTPException(400, 'Invalid request') from None
    if not _safe_token(data['refresh_token']):
        raise HTTPException(400, 'Invalid request')
    return data


# Database primary-key reservation and conditional status updates coordinate requests.
# Never hold a Python mutex across network I/O: FastAPI is async and blocking
# network calls already need to run in a worker thread.

def _guest_tx_valid_record(record, request_id, account, fingerprint):
    if (record.get('user_id') != account or
            not hmac.compare_digest(record.get('request_fingerprint') or '', fingerprint)):
        raise HTTPException(409, 'Guest transaction mismatch')
    from datetime import datetime, timezone
    try:
        expires = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(503, 'Guest transaction unavailable') from None
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(409, 'Guest transaction expired')


def _guest_tx_start_sync(data):
    """Run blocking Supabase I/O off the event loop. DB reservation is authoritative."""
    request_id, account = data['request_id'], data['expected_user_id']
    supplied = data['refresh_token']
    fingerprint = _guest_tx_fingerprint(supplied, account)
    record = _guest_tx_lookup(request_id)
    if record is None:
        # Check handoff capacity before consuming a refresh token.
        _bridge_secret()
        with _pending_tickets_lock:
            _remove_expired_locked(time.monotonic())
            if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
                raise HTTPException(429, 'Quick Login temporarily busy')
        from datetime import datetime, timedelta, timezone
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        try:
            _guest_tx_rest('POST', '', [{
                'request_id': request_id, 'user_id': account,
                'request_fingerprint': fingerprint, 'status': 'pending',
                'expires_at': expiry,
            }], prefer='return=minimal')
        except HTTPException as exc:
            # Another request may have reserved this ID. It must never
            # trigger a second provider refresh.
            if exc.status_code != 409:
                raise
            record = _guest_tx_lookup(request_id)
            if record is None:
                raise HTTPException(503, 'Guest transaction unavailable')
        else:
            # Only the successful reserver is allowed to rotate the token.
            # A crash between Supabase rotation and durable PATCH remains
            # unrecoverable without provider-side idempotency support.
            base, key = _configuration()
            exchange = Request(base + '/auth/v1/token?grant_type=refresh_token',
                data=json.dumps({'refresh_token': supplied}).encode('utf-8'),
                headers={'apikey': key, 'Content-Type': 'application/json',
                         'Accept': 'application/json'}, method='POST')
            session = _supabase_json(exchange)
            access, rotated = session.get('access_token'), session.get('refresh_token')
            if not _safe_token(access) or not _safe_token(rotated):
                raise HTTPException(503, 'Guest transaction unavailable')
            check = Request(base + '/auth/v1/user', headers={
                'apikey': key, 'Authorization': 'Bearer ' + access,
                'Accept': 'application/json'}, method='GET')
            verified = _supabase_json(check)
            try:
                actual = str(uuid.UUID(verified.get('id')))
            except (TypeError, ValueError, AttributeError):
                raise HTTPException(401, 'Session not valid') from None
            if actual != account:
                raise HTTPException(401, 'Account does not match')
            encrypted = _guest_tx_encrypt(request_id, account,
                                          {'access_token': access, 'refresh_token': rotated})
            from urllib.parse import quote
            updated = _guest_tx_rest('PATCH', '?request_id=eq.' + quote(request_id, safe='')
                + '&status=eq.pending', {'status': 'completed', 'encrypted_response': encrypted},
                prefer='return=representation')
            if not isinstance(updated, list) or len(updated) != 1:
                raise HTTPException(503, 'Guest transaction storage unavailable')
            return _guest_tx_issue_ticket(account, access, rotated)
    _guest_tx_valid_record(record, request_id, account, fingerprint)
    if record['status'] == 'pending':
        raise HTTPException(409, 'Guest refresh outcome uncertain; do not retry')
    if record['status'] != 'completed' or not record.get('encrypted_response'):
        raise HTTPException(409, 'Guest transaction already acknowledged')
    recovered = _guest_tx_decrypt(request_id, account, record['encrypted_response'])
    return _guest_tx_issue_ticket(account, recovered.get('access_token'),
                                  recovered.get('refresh_token'))


@app.post('/api/session/quick-login/transaction/start')
async def guest_transaction_start(request: FastAPIRequest):
    """Native opt-in endpoint; retries never repeat the Supabase rotation."""
    _bridge_secret()
    data = await _guest_tx_payload(request, {'request_id', 'expected_user_id', 'refresh_token'})
    from starlette.concurrency import run_in_threadpool
    return JSONResponse(await run_in_threadpool(_guest_tx_start_sync, data))


def _guest_tx_ack_sync(data):
    request_id, account = data['request_id'], data['expected_user_id']
    record = _guest_tx_lookup(request_id)
    if record is None or record.get('user_id') != account:
        raise HTTPException(401, 'Guest transaction unavailable')
    from datetime import datetime, timezone
    try:
        expires = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(503, 'Guest transaction unavailable') from None
    if expires <= datetime.now(timezone.utc):
        raise HTTPException(409, 'Guest transaction expired')
    if record.get('status') == 'acknowledged':
        # The rotated token was deliberately erased at acknowledgment.
        # We can no longer verify possession, so do not report success.
        raise HTTPException(409, 'Guest transaction already acknowledged')
    if record.get('status') != 'completed' or not record.get('encrypted_response'):
        raise HTTPException(409, 'Guest transaction not completed')
    recovered = _guest_tx_decrypt(request_id, account, record['encrypted_response'])
    if not hmac.compare_digest(recovered.get('refresh_token', ''), data['refresh_token']):
        raise HTTPException(401, 'Guest transaction mismatch')
    from urllib.parse import quote
    updated = _guest_tx_rest('PATCH', '?request_id=eq.' + quote(request_id, safe='')
        + '&status=eq.completed', {
            'status': 'acknowledged', 'encrypted_response': None,
            'acknowledged_at': datetime.now(timezone.utc).isoformat()},
        prefer='return=representation')
    if not isinstance(updated, list) or len(updated) != 1:
        # Another valid acknowledgement may have completed first.
        latest = _guest_tx_lookup(request_id)
        if latest is None or latest.get('status') != 'acknowledged':
            raise HTTPException(503, 'Guest transaction storage unavailable')
    return {'acknowledged': True}


@app.post('/api/session/quick-login/transaction/ack')
async def guest_transaction_ack(request: FastAPIRequest):
    """Acknowledge only after Android has durably saved the rotated token."""
    data = await _guest_tx_payload(request, {'request_id', 'expected_user_id', 'refresh_token'})
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(_guest_tx_ack_sync, data)


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


# Conservative, process-local creation throttle for the staging guest endpoint.
# Global rather than client-IP keyed: proxy headers are not a trustworthy identity.
# This limits accidental bursts but MUST be supplemented by an upstream shared
# rate limit before public activation, especially with multiple workers/replicas.
_GUEST_WINDOW_SECONDS = 60.0
_GUEST_MAX_PER_WINDOW = 3
_GUEST_DAILY_SECONDS = 86400.0
_GUEST_MAX_PER_DAY = 30
_guest_attempts: list[float] = []
_guest_attempts_lock = threading.Lock()


def _reserve_guest_creation_slot():
    now = time.monotonic()
    with _guest_attempts_lock:
        _guest_attempts[:] = [t for t in _guest_attempts
                             if now - t < _GUEST_DAILY_SECONDS]
        recent = sum(1 for t in _guest_attempts
                     if now - t < _GUEST_WINDOW_SECONDS)
        if recent >= _GUEST_MAX_PER_WINDOW or len(_guest_attempts) >= _GUEST_MAX_PER_DAY:
            raise HTTPException(429, 'Guest sign-in temporarily busy')
        # Charge attempts, not just successes, to avoid unlimited provider calls.
        _guest_attempts.append(now)


# ---------------------------------------------------------------------------
# Step 5I.2: restricted, activation-gated anonymous guest bootstrap.
# Only NEW guest creation requires a one-time code. Existing guest identities
# continue through /quick-login/start with their stored refresh credentials.
# ---------------------------------------------------------------------------
def _redeem_guest_activation(code: str) -> bool:
    """Consume an activation code atomically using the service-role-only RPC."""
    if not isinstance(code, str) or not code.isascii() or not __import__('re').fullmatch(r'[A-Fa-f0-9]{48}', code):
        return False
    base, _ = _configuration()
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not service_key:
        raise HTTPException(503, 'Guest activation not configured')
    # Codes are generated as uppercase 24-byte hex in the administrator SQL.
    # The exact uppercase string is hashed, matching the SQL generator.
    code_hash = hashlib.sha256(code.upper().encode('ascii')).hexdigest()
    req = Request(
        base + '/rest/v1/rpc/iv_redeem_guest_activation',
        data=json.dumps({'p_code_hash': code_hash}).encode('utf-8'),
        headers={'apikey': service_key,
                 'Authorization': 'Bearer ' + service_key,
                 'Content-Type': 'application/json',
                 'Accept': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(req, timeout=8) as response:
            raw = response.read(128)
        result = json.loads(raw)
        if not isinstance(result, bool):
            raise HTTPException(503, 'Guest activation unavailable')
        return result
    except HTTPError:
        raise HTTPException(503, 'Guest activation unavailable') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(503, 'Guest activation unavailable') from None


@app.post('/api/session/guest/start')
async def start_anonymous_guest(request: FastAPIRequest):
    """Create a new anonymous identity only after one-time code redemption.

    Native request: {"activation_code": "48 uppercase hex characters"}.
    Native response: user_id, refresh_token, ticket, ticket_expires_in.
    This endpoint must never be invoked from browser JavaScript.
    """
    if os.environ.get('IV_GUEST_SIGNIN_ENABLED', '').lower() != 'true':
        raise HTTPException(404, 'Not found')
    _bridge_secret()
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    if request.headers.get('origin'):
        raise HTTPException(403, 'Native client required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 256:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid JSON') from None
    finally:
        body.clear()
    if not isinstance(data, dict) or set(data) != {'activation_code'}:
        raise HTTPException(400, 'Activation code required')
    code = data['activation_code']
    if not isinstance(code, str) or len(code) != 48 or not code.isascii() or any(c not in '0123456789abcdefABCDEF' for c in code):
        raise HTTPException(400, 'Invalid activation code')
    with _pending_tickets_lock:
        _remove_expired_locked(time.monotonic())
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            raise HTTPException(429, 'Guest sign-in temporarily busy')
    _reserve_guest_creation_slot()
    # A redeemed code is irrevocably spent, including if Supabase signup fails.
    # This prevents replay but requires a new code after transient failures.
    if not _redeem_guest_activation(code):
        raise HTTPException(401, 'Activation code invalid, expired or already used')
    base, key = _configuration()
    signup = Request(base + '/auth/v1/signup',
                     data=b'{}',
                     headers={'apikey': key, 'Content-Type': 'application/json',
                              'Accept': 'application/json'}, method='POST')
    session = _supabase_json(signup)
    access, refresh = session.get('access_token'), session.get('refresh_token')
    if not _safe_token(access) or not _safe_token(refresh):
        raise HTTPException(503, 'Anonymous sign-in unavailable')
    user_request = Request(base + '/auth/v1/user', headers={
        'apikey': key, 'Authorization': 'Bearer ' + access,
        'Accept': 'application/json'}, method='GET')
    user = _supabase_json(user_request)
    try:
        account = str(uuid.UUID(user.get('id')))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(503, 'Anonymous identity verification failed') from None
    if user.get('is_anonymous') is not True:
        raise HTTPException(503, 'Anonymous identity verification failed')
    with _pending_tickets_lock:
        now = time.monotonic()
        _remove_expired_locked(now)
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            raise HTTPException(429, 'Guest sign-in temporarily busy')
        ticket = secrets.token_urlsafe(32)
        _pending_tickets[ticket] = (now + _TICKET_TTL, account, access, refresh)
    return JSONResponse({
        'user_id': account, 'refresh_token': refresh,
        'ticket': ticket, 'ticket_expires_in': int(_TICKET_TTL),
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


# ---------------------------------------------------------------------------
# Step 4H.3: BIOMETRIC ENROLLMENT HANDOFF (STAGING ONLY)
# ---------------------------------------------------------------------------
# Native Android generates BOTH a public challenge and a private secret.
# Only the public challenge may be rendered in the WebView. The native secret
# never enters JavaScript, query parameters, logs or the Streamlit document.
# A verified Streamlit backend authorizes enrollment through the private bridge.
# The native app then claims the refresh token directly over HTTPS, proving
# possession of its private secret. Nothing here enrolls a device automatically.
_ENROLL_TTL = 90.0
_MAX_ENROLLMENTS = 128
_enrollments: dict[str, dict] = {}
_enroll_lock = threading.Lock()
# A one-use intent is created by the authenticated Streamlit backend.
# Android reads ONLY this random public intent from the Profile DOM.
_enroll_intents: dict[str, dict] = {}


def _enroll_auth_payload(request_data):
    """Validate session tokens with Supabase; return (verified user id, refresh)."""
    if not isinstance(request_data, dict) or set(request_data) != {
            'access_token', 'refresh_token', 'expected_user_id'}:
        raise HTTPException(400, 'Invalid request')
    access = request_data['access_token']
    refresh = request_data['refresh_token']
    if not _safe_token(access) or not _safe_token(refresh):
        raise HTTPException(400, 'Invalid request')
    try:
        expected = str(uuid.UUID(request_data['expected_user_id']))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(400, 'Invalid request') from None
    base, key = _configuration()
    check = Request(base + '/auth/v1/user', headers={
        'apikey': key, 'Authorization': 'Bearer ' + access,
        'Accept': 'application/json'}, method='GET')
    user = _supabase_json(check)
    try:
        actual = str(uuid.UUID(user.get('id')))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(401, 'Session not valid') from None
    if actual != expected:
        raise HTTPException(401, 'Account does not match')
    return actual, refresh


@app.post('/api/session/quick-login/enroll/intent')
async def create_biometric_enrollment_intent(request: FastAPIRequest):
    """Private Streamlit-only authorization after an explicit Profile opt-in.

    The response contains only a random one-use intent, NEVER credentials.
    """
    _private_bridge(request)
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_BODY_BYTES:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        body.clear()
    account, refresh = _enroll_auth_payload(data)
    with _enroll_lock:
        now = time.monotonic()
        _enroll_cleanup(now)
        if len(_enroll_intents) + len(_enrollments) >= _MAX_ENROLLMENTS:
            raise HTTPException(429, 'Enrollment temporarily busy')
        intent = secrets.token_urlsafe(32)
        _enroll_intents[intent] = {
            'expires': now + _ENROLL_TTL, 'credentials': (account, refresh)}
    return JSONResponse({'intent': intent, 'expires_in': int(_ENROLL_TTL)})




def _enroll_cleanup(now: float):
    for challenge, record in tuple(_enrollments.items()):
        if record['expires'] <= now:
            del _enrollments[challenge]
    for intent, record in tuple(_enroll_intents.items()):
        if record['expires'] <= now:
            del _enroll_intents[intent]


@app.post('/api/session/quick-login/enroll/prepare')
async def prepare_biometric_enrollment(request: FastAPIRequest):
    """Native HTTPS only. Supply a random public challenge and secret verifier.

    Body: {"challenge": "43-char random", "verifier": "64-char SHA256 hex",
           "intent": "43-char one-use intent from authenticated Profile"}
    The secret itself stays in native memory; only its SHA256 digest is sent.
    """
    _bridge_secret()
    data = await _bounded_pair_json(request)
    if set(data) != {'challenge', 'verifier', 'intent'}:
        raise HTTPException(400, 'Invalid request')
    challenge, verifier, intent = data['challenge'], data['verifier'], data['intent']
    if not _valid_pair_challenge(challenge) or not _valid_pair_challenge(intent) or not (isinstance(verifier, str)
            and len(verifier) == 64 and all(c in '0123456789abcdef' for c in verifier)):
        raise HTTPException(400, 'Invalid request')
    with _enroll_lock:
        now = time.monotonic()
        _enroll_cleanup(now)
        if len(_enrollments) >= _MAX_ENROLLMENTS:
            raise HTTPException(429, 'Enrollment temporarily busy')
        if challenge in _enrollments:
            raise HTTPException(409, 'Enrollment already pending')
        authorized_intent = _enroll_intents.pop(intent, None)
        if authorized_intent is None:
            raise HTTPException(401, 'Enrollment intent unavailable')
        _enrollments[challenge] = {'expires': min(now + _ENROLL_TTL, authorized_intent['expires']),
                                   'verifier': verifier, 'credentials': authorized_intent['credentials']}
    return JSONResponse({'prepared': True, 'expires_in': int(_ENROLL_TTL)})


@app.post('/api/session/quick-login/enroll/authorize')
async def authorize_biometric_enrollment(request: FastAPIRequest):
    """Private Streamlit backend ONLY, after explicit authenticated opt-in.

    The caller MUST obtain credentials from its own authenticated session,
    not from browser input. This endpoint independently verifies the access
    token with Supabase and checks the expected user ID before authorization.
    """
    _private_bridge(request)
    # Larger bounded body than pairing: this private request carries tokens.
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _MAX_BODY_BYTES:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        body.clear()
    if not isinstance(data, dict) or set(data) != {
            'challenge', 'access_token', 'refresh_token', 'expected_user_id'}:
        raise HTTPException(400, 'Invalid request')
    challenge = data['challenge']
    access, refresh = data['access_token'], data['refresh_token']
    if not _valid_pair_challenge(challenge) or not _safe_token(access) or not _safe_token(refresh):
        raise HTTPException(400, 'Invalid request')
    try:
        expected = str(uuid.UUID(data['expected_user_id']))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(400, 'Invalid request') from None
    with _enroll_lock:
        now = time.monotonic()
        _enroll_cleanup(now)
        record = _enrollments.get(challenge)
        if record is None or record['credentials'] is not None:
            raise HTTPException(401, 'Enrollment unavailable')
    base, key = _configuration()
    check = Request(base + '/auth/v1/user', headers={
        'apikey': key, 'Authorization': 'Bearer ' + access,
        'Accept': 'application/json'}, method='GET')
    user = _supabase_json(check)
    try:
        actual = str(uuid.UUID(user.get('id')))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(401, 'Session not valid') from None
    if actual != expected:
        raise HTTPException(401, 'Account does not match')
    with _enroll_lock:
        now = time.monotonic()
        _enroll_cleanup(now)
        record = _enrollments.get(challenge)
        if record is None or record['credentials'] is not None:
            raise HTTPException(401, 'Enrollment unavailable')
        record['credentials'] = (actual, refresh)
    return JSONResponse({'authorized': True})


@app.post('/api/session/quick-login/enroll/claim')
async def claim_biometric_enrollment(request: FastAPIRequest):
    """Native HTTPS only; single-use claim using the native private secret."""
    _bridge_secret()
    data = await _bounded_pair_json(request)
    if set(data) != {'challenge', 'secret'}:
        raise HTTPException(400, 'Invalid request')
    challenge, secret = data['challenge'], data['secret']
    if not _valid_pair_challenge(challenge) or not _valid_pair_challenge(secret):
        raise HTTPException(400, 'Invalid request')
    import hashlib
    verifier = hashlib.sha256(secret.encode('ascii')).hexdigest()
    with _enroll_lock:
        now = time.monotonic()
        _enroll_cleanup(now)
        record = _enrollments.get(challenge)
        if record is None or not hmac.compare_digest(record['verifier'], verifier):
            raise HTTPException(401, 'Enrollment unavailable')
        if record['credentials'] is None:
            return JSONResponse({'status': 'pending'}, status_code=202)
        account, refresh = record['credentials']
        del _enrollments[challenge]
    return JSONResponse({'valid': True, 'user_id': account,
                         'refresh_token': refresh})




# ---------------------------------------------------------------------------
# Password recovery: isolated from Streamlit and native Quick Login.
# Recovery token is carried in a URL fragment (never sent in HTTP GET), then
# sent in a bounded same-origin POST. Supabase sessions stay server-side.
# ---------------------------------------------------------------------------
_RECOVERY_PATH = '/api/session/password-reset'
_RECOVERY_MAX_BYTES = 4096

_RECOVERY_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reset password | InvesTrack Pro</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color-scheme:light}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f3f6fa;color:#14233b}
main{box-sizing:border-box;width:min(420px,calc(100% - 32px));padding:30px;border-radius:14px;background:white;box-shadow:0 8px 32px #152b4818}
h1{font-size:1.55rem;margin:0 0 10px}p{line-height:1.5;color:#4a596b}label{display:block;font-weight:600;margin:18px 0 6px}
input,button{box-sizing:border-box;width:100%;padding:12px;border-radius:8px;font:inherit}
input{border:1px solid #abb7c8}button{margin-top:22px;border:0;background:#1559b5;color:white;cursor:pointer}
button:disabled{opacity:.65;cursor:wait}#status{min-height:1.5em}a{color:#1559b5}
</style></head><body><main><h1>Reset your password</h1>
<p>Enter a new password for your InvesTrack Pro account.</p>
<form id="reset" hidden>
<label for="password">New password</label><input id="password" type="password" minlength="8" maxlength="256" autocomplete="new-password" required>
<label for="confirm">Confirm new password</label><input id="confirm" type="password" minlength="8" maxlength="256" autocomplete="new-password" required>
<button id="submit" type="submit">Update password</button></form>
<p id="status" role="status" aria-live="polite"></p>
<p><a href="/">Return to login</a></p></main>
<script>
(function(){
  'use strict';
  const status=document.getElementById('status'), form=document.getElementById('reset');
  let token='';
  try {
    const fragment=new URLSearchParams(window.location.hash.slice(1));
    token=fragment.get('recovery_token')||'';
    // Remove sensitive fragment before user submits anything or navigates.
    history.replaceState(null,'',window.location.pathname);
  } catch (_) { token=''; }
  if (!/^[A-Za-z0-9_-]{1,2048}$/.test(token)) {
    status.textContent='This reset link is missing or invalid. Please request a new link from the login page.';
    return;
  }
  form.hidden=false;
  form.addEventListener('submit',async function(event){
    event.preventDefault();
    const password=document.getElementById('password').value;
    const confirm=document.getElementById('confirm').value;
    if(password!==confirm){status.textContent='Passwords do not match.';return;}
    if(password.length<8){status.textContent='Use at least 8 characters.';return;}
    const submit=document.getElementById('submit');submit.disabled=true;
    status.textContent='Updating password…';
    try {
      const response=await fetch('/api/session/password-reset',{
        method:'POST',credentials:'same-origin',cache:'no-store',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({token_hash:token,password:password})
      });
      const result=await response.json();
      if(!response.ok) throw new Error(result.detail||'Unable to reset password.');
      token=''; form.hidden=true;
      status.textContent='Password updated successfully. Return to login and sign in with your new password.';
    } catch(e) {status.textContent=e.message||'Unable to reset password.';}
    finally {submit.disabled=false;}
  });
})();
</script></body></html>"""


@app.get(_RECOVERY_PATH, response_class=HTMLResponse)
def password_reset_page():
    return HTMLResponse(_RECOVERY_HTML, headers={
        'Content-Security-Policy': "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        'X-Frame-Options': 'DENY',
    })


@app.post(_RECOVERY_PATH)
async def reset_password(request: FastAPIRequest):
    # Browser-only same-origin form. Reject cross-origin requests without
    # relying on cookies, and never accept the token in a query string.
    origin = request.headers.get('origin')
    if not origin or origin != 'https://' + request.headers.get('host', ''):
        raise HTTPException(403, 'Request origin not allowed')
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    if request.url.query:
        raise HTTPException(400, 'Invalid request')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > _RECOVERY_MAX_BYTES:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        body.clear()
    if not isinstance(data, dict) or set(data) != {'token_hash', 'password'}:
        raise HTTPException(400, 'Invalid request')
    token, password = data['token_hash'], data['password']
    if not (isinstance(token, str) and 1 <= len(token) <= 2048
            and token.isascii() and all(c.isalnum() or c in '-_' for c in token)):
        raise HTTPException(400, 'Invalid reset link')
    if not isinstance(password, str) or not (8 <= len(password) <= 256):
        raise HTTPException(400, 'Password must be 8–256 characters')

    base, key = _configuration()
    verify = Request(base + '/auth/v1/verify',
                     data=json.dumps({'token_hash': token, 'type': 'recovery'}).encode('utf-8'),
                     headers={'apikey': key, 'Content-Type': 'application/json',
                              'Accept': 'application/json'}, method='POST')
    try:
        session = _supabase_json(verify)
    except HTTPException as exc:
        if exc.status_code == 401:
            raise HTTPException(400, 'Reset link expired or invalid. Request a new link.') from None
        raise
    access = session.get('access_token')
    if not _safe_token(access):
        raise HTTPException(400, 'Reset link expired or invalid. Request a new link.')
    update = Request(base + '/auth/v1/user',
                     data=json.dumps({'password': password}).encode('utf-8'),
                     headers={'apikey': key, 'Authorization': 'Bearer ' + access,
                              'Content-Type': 'application/json', 'Accept': 'application/json'},
                     method='PUT')
    try:
        _supabase_json(update)
    except HTTPException as exc:
        if exc.status_code == 401:
            raise HTTPException(400, 'Password was not accepted. Request a new link if needed.') from None
        raise
    return {'updated': True}


# ---------------------------------------------------------------------------
# Step 5I.43D.60P: Google Play Integrity Standard API guest onboarding.
# Feature-flagged OFF until Android integration and end-to-end verification.
# The legacy activation-code route and all saved guest restoration paths remain.
# Requires the restricted Supabase migration iv_integrity_onboarding_*.
# ---------------------------------------------------------------------------
_IV_INTEGRITY_PACKAGE = 'com.investrackpro.app'
_IV_INTEGRITY_TTL_SECONDS = 120
_IV_INTEGRITY_MAX_BODY = 32768
_IV_INTEGRITY_PROJECT = '82972562008'


def _integrity_enabled():
    if os.environ.get('IV_PLAY_INTEGRITY_GUEST_ENABLED', '').lower() != 'true':
        raise HTTPException(404, 'Not found')


def _integrity_rpc(function, params):
    base, _ = _configuration()
    role = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not role:
        raise HTTPException(503, 'Integrity storage unavailable')
    req = Request(base + '/rest/v1/rpc/' + function,
                  data=json.dumps(params).encode('utf-8'),
                  headers={'apikey': role, 'Authorization': 'Bearer ' + role,
                           'Content-Type': 'application/json', 'Accept': 'application/json'},
                  method='POST')
    try:
        with urlopen(req, timeout=8) as response:
            raw = response.read(1025)
        if len(raw) > 1024:
            raise ValueError('Oversized RPC response')
        result = json.loads(raw)
        if type(result) is not bool:
            raise ValueError('Unexpected RPC response')
        return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(503, 'Integrity storage unavailable') from None


def _integrity_store_challenge(digest):
    from datetime import datetime, timedelta, timezone
    base, _ = _configuration()
    role = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not role:
        raise HTTPException(503, 'Integrity storage unavailable')
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=_IV_INTEGRITY_TTL_SECONDS)).isoformat()
    req = Request(base + '/rest/v1/iv_integrity_onboarding_challenges',
                  data=json.dumps({'challenge_hash': digest, 'expires_at': expiry}).encode('utf-8'),
                  headers={'apikey': role, 'Authorization': 'Bearer ' + role,
                           'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
                  method='POST')
    try:
        with urlopen(req, timeout=8) as response:
            if response.status not in (200, 201, 204):
                raise ValueError('Storage rejected challenge')
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(503, 'Integrity storage unavailable') from None


def _integrity_request_hash(challenge):
    # Contract for native Android: SHA-256 of this ASCII string, lowercase hex.
    return hashlib.sha256(('iv-guest-v1:' + challenge).encode('ascii')).hexdigest()


async def _integrity_json(request, expected, max_bytes):
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON body required')
    if request.headers.get('origin') or request.url.query:
        raise HTTPException(403, 'Native client required')
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > max_bytes:
            raise HTTPException(413, 'Request too large')
        body.extend(chunk)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError):
        raise HTTPException(400, 'Invalid request') from None
    finally:
        body.clear()
    if not isinstance(payload, dict) or set(payload) != expected:
        raise HTTPException(400, 'Invalid request')
    return payload


def _integrity_google_decode(token):
    # Service account credentials are never sent to the Android client.
    try:
        import google.auth.transport.requests
        from google.oauth2 import service_account
        credentials_data = json.loads(os.environ.get('IV_PLAY_INTEGRITY_CREDENTIALS_JSON', ''))
        if not isinstance(credentials_data, dict) or credentials_data.get('type') != 'service_account':
            raise ValueError('Invalid service account configuration')
        credentials = service_account.Credentials.from_service_account_info(
            credentials_data, scopes=['https://www.googleapis.com/auth/playintegrity'])
        credentials.refresh(google.auth.transport.requests.Request())
        import requests
        response = requests.post(
            'https://playintegrity.googleapis.com/v1/' + _IV_INTEGRITY_PACKAGE + ':decodeIntegrityToken',
            headers={'Authorization': 'Bearer ' + credentials.token,
                     'Content-Type': 'application/json'},
            json={'integrity_token': token}, timeout=10)
        if response.status_code != 200 or len(response.content) > 32768:
            raise ValueError('Google verification failed')
        result = response.json()
        payload = result.get('tokenPayloadExternal') if isinstance(result, dict) else None
        if not isinstance(payload, dict):
            raise ValueError('Invalid Google verdict')
        return payload
    except Exception:
        # Never log token, credential, response body or provider exception.
        raise HTTPException(503, 'Integrity verification unavailable') from None


def _integrity_validate(verdict, request_hash):
    details = verdict.get('requestDetails')
    app_integrity = verdict.get('appIntegrity')
    device = verdict.get('deviceIntegrity')
    if not all(isinstance(v, dict) for v in (details, app_integrity, device)):
        raise HTTPException(403, 'Integrity verification rejected')
    if (details.get('requestPackageName') != _IV_INTEGRITY_PACKAGE or
            not hmac.compare_digest(str(details.get('requestHash', '')), request_hash) or
            app_integrity.get('appRecognitionVerdict') != 'PLAY_RECOGNIZED' or
            'MEETS_DEVICE_INTEGRITY' not in device.get('deviceRecognitionVerdict', [])):
        raise HTTPException(403, 'Integrity verification rejected')
    try:
        timestamp_ms = int(details['timestampMillis'])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(403, 'Integrity verification rejected') from None
    age_ms = int(time.time() * 1000) - timestamp_ms
    if age_ms < -30000 or age_ms > _IV_INTEGRITY_TTL_SECONDS * 1000:
        raise HTTPException(403, 'Integrity verification rejected')


def _integrity_signup_sync(challenge, token):
    # Verify with Google first; no account is created on an invalid verdict.
    digest = hashlib.sha256(challenge.encode('ascii')).hexdigest()
    verdict = _integrity_google_decode(token)
    _integrity_validate(verdict, _integrity_request_hash(challenge))
    if not _integrity_rpc('iv_consume_integrity_challenge', {'p_challenge_hash': digest}):
        raise HTTPException(409, 'Onboarding challenge expired or already used')
    if not _integrity_rpc('iv_reserve_integrity_signup_slot',
                          {'p_max_minute': 10, 'p_max_day': 1000}):
        raise HTTPException(429, 'Guest onboarding temporarily busy')
    _bridge_secret()
    with _pending_tickets_lock:
        _remove_expired_locked(time.monotonic())
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            raise HTTPException(429, 'Guest onboarding temporarily busy')
    base, key = _configuration()
    signup = Request(base + '/auth/v1/signup', data=b'{}',
                     headers={'apikey': key, 'Content-Type': 'application/json',
                              'Accept': 'application/json'}, method='POST')
    session = _supabase_json(signup)
    access, refresh = session.get('access_token'), session.get('refresh_token')
    if not _safe_token(access) or not _safe_token(refresh):
        raise HTTPException(503, 'Anonymous sign-in unavailable')
    check = Request(base + '/auth/v1/user', headers={
        'apikey': key, 'Authorization': 'Bearer ' + access,
        'Accept': 'application/json'}, method='GET')
    user = _supabase_json(check)
    try:
        account = str(uuid.UUID(user.get('id')))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(503, 'Anonymous identity verification failed') from None
    if user.get('is_anonymous') is not True:
        raise HTTPException(503, 'Anonymous identity verification failed')
    with _pending_tickets_lock:
        now = time.monotonic()
        _remove_expired_locked(now)
        if len(_pending_tickets) >= _MAX_PENDING_TICKETS:
            raise HTTPException(429, 'Guest onboarding temporarily busy')
        ticket = secrets.token_urlsafe(32)
        _pending_tickets[ticket] = (now + _TICKET_TTL, account, access, refresh)
    return {'user_id': account, 'refresh_token': refresh,
            'ticket': ticket, 'ticket_expires_in': int(_TICKET_TTL)}


@app.post('/api/session/guest/integrity/challenge')
async def integrity_guest_challenge(request: FastAPIRequest):
    _integrity_enabled()
    await _integrity_json(request, set(), 128)
    challenge = secrets.token_urlsafe(32)
    _integrity_store_challenge(hashlib.sha256(challenge.encode('ascii')).hexdigest())
    return JSONResponse({'challenge': challenge,
                         'request_hash': _integrity_request_hash(challenge),
                         'expires_in': _IV_INTEGRITY_TTL_SECONDS})


@app.post('/api/session/guest/integrity/start')
async def integrity_guest_start(request: FastAPIRequest):
    _integrity_enabled()
    payload = await _integrity_json(request, {'challenge', 'integrity_token'}, _IV_INTEGRITY_MAX_BODY)
    challenge, token = payload['challenge'], payload['integrity_token']
    if not _valid_pair_challenge(challenge) or not (isinstance(token, str) and
            1 <= len(token) <= 24000 and token.isascii() and
            all(ch.isalnum() or ch in '-_.' for ch in token)):
        raise HTTPException(400, 'Invalid request')
    from starlette.concurrency import run_in_threadpool
    return JSONResponse(await run_in_threadpool(_integrity_signup_sync, challenge, token))


@app.api_route('/api/session/{path:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
def unavailable(path: str):
    return JSONResponse(status_code=501, content={
        'error': 'Session persistence is not enabled'
    })
