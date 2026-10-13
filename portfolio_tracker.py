"""InvesTrack Pro portfolio history helpers.

Hourly autosave is opportunistic: a mode must be evaluated by a signed-in
user. It is NOT a background scheduler. Existing portfolio_history schema is
preserved for compatibility with previously saved charts.
"""
from datetime import datetime, timezone
import math
import streamlit as st
from db import get_supabase

VALID_MODES = frozenset({'overview', 'crypto', 'stock', 'etf', 'bond'})


def db():
    client = get_supabase()
    if 'access_token' in st.session_state:
        try:
            client.auth.set_session(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
            )
        except Exception:
            pass
    return client


def _valid(user_id, value, mode):
    try:
        number = float(value)
        return bool(user_id) and mode in VALID_MODES and math.isfinite(number) and number > 0
    except (TypeError, ValueError):
        return False


def _parse_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _insert(client, user_id, value, mode, now):
    client.table('portfolio_history').insert({
        'user_id': user_id,
        'timestamp': now.isoformat(),
        'value_ghs': round(float(value), 2),
        'mode': mode,
    }).execute()


def manual_snapshot(user_id: str, value_ghs: float, mode: str):
    """Save an explicit user-requested snapshot immediately."""
    if not _valid(user_id, value_ghs, mode):
        return False
    try:
        _insert(db(), user_id, value_ghs, mode, datetime.now(timezone.utc))
        return True
    except Exception as exc:
        print('Manual snapshot failed:', exc)
        return False


def autosave_portfolio_value(user_id: str, value_ghs: float, mode: str):
    """Save at most once per UTC clock hour on normal sequential page loads.

    This read-then-write operation is not atomic across concurrent sessions.
    A DB unique constraint or transactional RPC is needed for strict deduping.
    """
    if not _valid(user_id, value_ghs, mode):
        return False
    try:
        client = db()
        now = datetime.now(timezone.utc)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        last = (
            client.table('portfolio_history')
            .select('timestamp')
            .eq('user_id', user_id)
            .eq('mode', mode)
            .gte('timestamp', hour_start.isoformat())
            .order('timestamp', desc=True)
            .limit(1)
            .execute()
        )
        if last.data:
            return False
        _insert(client, user_id, value_ghs, mode, now)
        return True
    except Exception as exc:
        print('Hourly portfolio autosave failed:', exc)
        return False
