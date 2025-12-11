import streamlit as st
from crypto_mode import crypto_app
from stock_mode import stock_app

st.set_page_config(page_title="InvesTrack Pro", layout="wide")
st.sidebar.title("InvesTrack Pro")

# Only mode selector here. Exchange rates are managed inside each mode to avoid duplication.
mode = st.sidebar.radio("Choose Mode", ["Crypto", "Stocks"])

if mode == "Crypto":
    crypto_app()
else:
    stock_app()
