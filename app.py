import streamlit as st
from auth import login_ui, ensure_auth, logout

st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide",
)

# ------------------------------------
# HARD AUTH GATE
# ------------------------------------
if not ensure_auth():
    login_ui()
    st.stop()

# Normalize session ONCE
if "user" not in st.session_state:
    st.session_state.user = st.session_state.user
    st.session_state.user_id = st.session_state.user.id

user = st.session_state.user

# ------------------------------------
# SIDEBAR
# ------------------------------------
st.sidebar.success(f"Logged in as\n{user.email}")

if st.sidebar.button("🚪 Logout"):
    logout()
    st.stop()

mode = st.sidebar.radio(
    "Select Mode",
    ["Crypto", "Stocks"],
)

# ------------------------------------
# LAZY LOAD MODES
# ------------------------------------
try:
    if mode == "Crypto":
        from crypto_mode import crypto_app
        crypto_app()
    else:
        from stock_mode import stock_app
        stock_app()
except Exception:
    st.error("Something went wrong. Please refresh the app.")
