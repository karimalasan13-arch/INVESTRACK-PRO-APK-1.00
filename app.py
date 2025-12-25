import streamlit as st

# 🔐 AUTH GATE — MUST RUN FIRST
from auth import login_ui

if "user" not in st.session_state:
    login_ui()
    st.stop()

# 🚀 APP STARTS ONLY AFTER LOGIN
from crypto_mode import crypto_app
from stock_mode import stock_app

st.sidebar.success(f"Logged in as {st.session_state.user.email}")

mode = st.sidebar.radio("Select Mode", ["Crypto", "Stocks"])

if mode == "Crypto":
    crypto_app()
else:
    stock_app()
