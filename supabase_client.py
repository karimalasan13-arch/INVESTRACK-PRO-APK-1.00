from supabase import create_client
import streamlit as st

# Create Supabase client
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_KEY"]
)

# Initialize auth state
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None


def get_current_user():
    """Check Supabase session"""
    try:
        session = supabase.auth.get_session()
        if session and session.user:
            st.session_state.auth_user = session.user
            return session.user
    except Exception:
        pass
    return None


def logout():
    """Secure logout"""
    supabase.auth.sign_out()
    st.session_state.auth_user = None
