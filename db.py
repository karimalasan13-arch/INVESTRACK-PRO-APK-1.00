import os
from supabase import create_client, Client
import streamlit as st

# Read secrets from Streamlit Cloud
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON PUBLIC_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
