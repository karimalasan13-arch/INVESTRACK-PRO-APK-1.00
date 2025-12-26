import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

def get_supabase():
    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(
            SUPABASE_URL,
            SUPABASE_ANON_KEY
        )
    return st.session_state.supabase
