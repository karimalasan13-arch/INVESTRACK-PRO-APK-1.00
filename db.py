# db.py
import os
import streamlit as st
from supabase import create_client, Client


# -----------------------------------------
# SAFE SECRET LOADER
# Works on:
# - Render environment variables
# - Streamlit Cloud secrets
# -----------------------------------------
def get_secret(key: str, default=None):
    env_value = os.getenv(key)
    if env_value:
        return env_value

    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


# -----------------------------------------
# LOAD KEYS
# -----------------------------------------
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("❌ Supabase credentials not found.")


# -----------------------------------------
# SESSION-ISOLATED CLIENT
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
# GLOBAL ACCESSOR
# -----------------------------------------
supabase: Client = get_supabase()


# -----------------------------------------
# ERROR LOGGER
# -----------------------------------------
def log_supabase_error(context: str, err: Exception):
    st.error(f"Supabase error in {context}")

    debug = get_secret("DEBUG", False)

    if str(debug).lower() in ["true", "1", "yes"]:
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
