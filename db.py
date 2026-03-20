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
    raise RuntimeError("❌ Supabase credentials not found.")


# -----------------------------------------
# ✅ SESSION-ISOLATED CLIENT (FINAL FIX)
# -----------------------------------------
def get_supabase() -> Client:
    """
    Creates ONE Supabase client per user session.
    Fixes:
    - Account leakage
    - Random logout
    - Save failures
    """

    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

    return st.session_state.supabase_client


# -----------------------------------------
# GLOBAL ACCESSOR (SAFE)
# -----------------------------------------
supabase: Client = get_supabase()


# -----------------------------------------
# ERROR LOGGER
# -----------------------------------------
def log_supabase_error(context: str, err: Exception):
    st.error(f"Supabase error in {context}")
    if st.secrets.get("DEBUG", False):
        st.exception(err)


# -----------------------------------------
# HEALTH CHECK
# -----------------------------------------
def supabase_healthcheck() -> bool:
    try:
        get_supabase().table("user_settings").select("id").limit(1).execute()
        return True
    except Exception:
        return False
