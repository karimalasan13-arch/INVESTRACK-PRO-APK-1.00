import streamlit as st
from auth import require_auth, auth_header

# ------------------------------------
# AUTH GATE
# ------------------------------------
if "user" not in st.session_state:
    require_auth()
    auth_header()

# ------------------------------------
# NORMALIZE USER SESSION (CRITICAL)
# ------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = st.session_state.user.id

# ------------------------------------
# POST-LOGIN APP
# ------------------------------------
from crypto_mode import crypto_app
from stock_mode import stock_app

st.sidebar.success(f"Logged in as {st.session_state.user.email}")

mode = st.sidebar.radio("Select Mode", ["Crypto", "Stocks"])

if mode == "Crypto":
    crypto_app()
else:
    stock_app()
