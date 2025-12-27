import streamlit as st
from auth import login_ui, get_current_user, logout

# ------------------------------------
# APP CONFIG
# ------------------------------------
st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide"
)

# ------------------------------------
# HARD AUTH GATE (CRITICAL)
# ------------------------------------
user = get_current_user()

if not user:
    login_ui()
    st.stop()

# ------------------------------------
# NORMALIZE SESSION (SINGLE SOURCE)
# ------------------------------------
st.session_state.user = user
st.session_state.user_id = user.id

# ------------------------------------
# SIDEBAR
# ------------------------------------
st.sidebar.success(f"Logged in as\n{user.email}")

if st.sidebar.button("🚪 Logout"):
    logout()
    st.session_state.clear()
    st.rerun()

mode = st.sidebar.radio(
    "Select Mode",
    ["Crypto", "Stocks"],
    key="mode_select"
)

# ------------------------------------
# LAZY IMPORTS (PREVENT LOAD ISSUES)
# ------------------------------------
if mode == "Crypto":
    from crypto_mode import crypto_app
    crypto_app()
else:
    from stock_mode import stock_app
    stock_app()
