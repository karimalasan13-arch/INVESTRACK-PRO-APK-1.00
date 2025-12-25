import streamlit as st
st.error("APP.PY IS RUNNING")
st.stop()

import streamlit as st
from auth import login_ui

# 🔐 HARD GATE
if "user" not in st.session_state:
    login_ui()
    st.stop()

# ---- App starts ONLY after login ----
from crypto_mode import crypto_app
from stock_mode import stock_app

st.sidebar.success(f"Logged in as {st.session_state.user.email}")

mode = st.sidebar.radio("Select Mode", ["Crypto", "Stocks"])

if mode == "Crypto":
    crypto_app()
else:
    stock_app()
