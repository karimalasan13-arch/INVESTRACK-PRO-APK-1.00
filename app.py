import streamlit as st
from auth import login_ui
from crypto_mode import crypto_app
from stock_mode import stock_app

if "user" not in st.session_state:
    login_ui()
    st.stop()

st.sidebar.success(f"Logged in as {st.session_state.user.email}")

mode = st.sidebar.radio("Select Mode", ["Crypto", "Stocks"])

if mode == "Crypto":
    crypto_app()
else:
    stock_app()
