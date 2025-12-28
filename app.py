import streamlit as st
from auth import login_ui, ensure_auth, logout

# ------------------------------------
# APP CONFIG (MUST BE FIRST)
# ------------------------------------
st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide",
)

# ------------------------------------
# HARD AUTH GATE (PRODUCTION-GRADE)
# ------------------------------------
if not ensure_auth():
    login_ui()
    st.stop()

# At this point auth is guaranteed
user = st.session_state.user
user_id = st.session_state.user_id

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
    key="mode_select",
)

# ------------------------------------
# LAZY IMPORTS (CRITICAL FOR STABILITY)
# ------------------------------------
if mode == "Crypto":
    from crypto_mode import crypto_app
    crypto_app()
else:
    from stock_mode import stock_app
    stock_app()
