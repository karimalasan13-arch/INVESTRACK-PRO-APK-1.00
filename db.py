# db.py
import os
import streamlit as st
from supabase import create client, Client

ALPHA_VANTAGE_API_KEY = (
    st.secrets.get("ALPHA_VANTAGE_API_KEY")
    or os.getenv("ALPHA_VANTAGE_API_KEY")
)

# --------------------------------------------------
# LOAD SUPABASE CREDENTIALS (Streamlit + Env safe)
# --------------------------------------------------
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
        "❌ Supabase credentials not found.\n"
        "Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in Streamlit secrets."
    )

# --------------------------------------------------
# CREATE SINGLETON SUPABASE CLIENT
# --------------------------------------------------
@st.cache_resource(show_spinner=False)
def _create_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = _create_supabase()

# --------------------------------------------------
# OPTIONAL: DEBUG HELPER (SAFE)
# --------------------------------------------------
def log_supabase_error(context: str, err: Exception):
    """
    Centralized error logging.
    Does NOT expose secrets.
    """
    st.error(f"Supabase error in {context}")
    if st.secrets.get("DEBUG", False):
        st.exception(err)

# --------------------------------------------------
# OPTIONAL: HEALTH CHECK (PRODUCTION SAFE)
# --------------------------------------------------
def supabase_healthcheck() -> bool:
    """
    Lightweight connectivity test.
    """
    try:
        supabase.table("user_settings").select("id").limit(1).execute()
        return True
    except Exception:
        return False
