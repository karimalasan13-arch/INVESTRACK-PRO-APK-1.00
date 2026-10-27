"""Staging-only Streamlit server-side Quick Login pairing transport.

This module never exposes Supabase credentials to browser components. The
challenge returned by create_pair is public *pairing metadata*, not a login
credential. Only call from a Streamlit script running for the owning session.
"""
import os
import re
import time

import requests

_BASE = 'http://127.0.0.1:8000'
_TIMEOUT = 3
_CHALLENGE = re.compile(r'^[A-Za-z0-9_-]{43}$')


def _headers():
    secret = os.environ.get('IV_QUICKLOGIN_BRIDGE_SECRET', '')
    if len(secret) < 40 or not secret.isascii():
        raise RuntimeError('Quick Login private bridge unavailable')
    return {'x-iv-quicklogin-bridge': secret,
            'Content-Type': 'application/json'}


def _post(path, payload):
    # Never log payload, response bodies, credentials or private bridge header.
    response = requests.post(_BASE + path, json=payload,
                             headers=_headers(), timeout=_TIMEOUT,
                             allow_redirects=False)
    if response.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError('Unexpected Quick Login redirect')
    return response


def create_pair():
    """Return (challenge, monotonic_expiry), or None on any failure."""
    try:
        response = _post('/api/session/quick-login/pair/create', {})
        if response.status_code != 200:
            return None
        data = response.json()
        challenge = data.get('challenge')
        ttl = data.get('expires_in')
        if not isinstance(challenge, str) or not _CHALLENGE.fullmatch(challenge):
            return None
        if type(ttl) is not int or not 1 <= ttl <= 60:
            return None
        return challenge, time.monotonic() + ttl
    except (requests.RequestException, ValueError, RuntimeError, TypeError):
        return None


def consume_pair(challenge):
    """Return ('pending', None), ('ready', credentials), or ('failed', None).

    Credentials are (access_token, refresh_token, user_id) and must be passed
    directly to auth.restore_verified_session within the same Streamlit script
    session. Never render them or put them in session query parameters.
    """
    if not isinstance(challenge, str) or not _CHALLENGE.fullmatch(challenge):
        return 'failed', None
    try:
        response = _post('/api/session/quick-login/pair/consume',
                         {'challenge': challenge})
        if response.status_code == 202:
            return 'pending', None
        if response.status_code != 200:
            return 'failed', None
        data = response.json()
        if data.get('valid') is not True:
            return 'failed', None
        access, refresh, user_id = (data.get('access_token'),
                                    data.get('refresh_token'), data.get('user_id'))
        if not all(isinstance(x, str) and 0 < len(x) <= 8192
                   for x in (access, refresh, user_id)):
            return 'failed', None
        return 'ready', (access, refresh, user_id)
    except (requests.RequestException, ValueError, RuntimeError, TypeError):
        return 'failed', None
