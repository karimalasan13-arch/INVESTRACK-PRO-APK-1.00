# db.py
import os
import streamlit as st
from supabase import create_client, Client

# -----------------------------------------
# LOAD KEYS
# -----------------------------------------
SUPABASE_URL = (
    st.secrets.get("SUPABASE_URL")
    if hasattr(st, "secrets")
    else None
) or os.getenv("SUPABASE_URL")

SUPABASE_KEY = (
    st.secrets.get("SUPABASE_ANON_KEY")
    if hasattr(st, "secrets")
    else None
) or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "❌ Supabase credentials not found."
    )


# -----------------------------------------
# 🚨 CREATE FRESH CLIENT (NO CACHE)
# -----------------------------------------
def get_supabase() -> Client:
    """
    Returns a NEW Supabase client per request.
    Prevents session leakage between users.
    """
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------------------
# GLOBAL ACCESSOR (SAFE WRAPPER)
# -----------------------------------------
@property
def supabase() -> Client:
    return get_supabase()


# -----------------------------------------
# OPTIONAL: ERROR LOGGER
# -----------------------------------------
def log_supabase_error(context: str, err: Exception):
    st.error(f"Supabase error in {context}")
    if st.secrets.get("DEBUG", False):
        st.exception(err)


# -----------------------------------------
# OPTIONAL: HEALTH CHECK
# -----------------------------------------
def supabase_healthcheck() -> bool:
    try:
        get_supabase().table("user_settings").select("id").limit(1).execute()
        return True
    except Exception:
        return False
