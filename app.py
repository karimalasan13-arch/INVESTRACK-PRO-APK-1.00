import streamlit as st
import time
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

# ------------------------------------
# AUTO REFRESH (SAFE)
# ------------------------------------
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh > 60:
    st.session_state.last_refresh = time.time()
    st.rerun()

# ------------------------------------
# SESSION
# ------------------------------------
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
)

st.sidebar.markdown(
    """
    ---
    🗑 **Delete Account**

    Email **delete@investrackpro.app**
    """
)

# ------------------------------------
# LAZY LOAD MODES
# ------------------------------------
try:

    if mode == "Crypto":
        from crypto_mode import crypto_app
        crypto_app()

    elif mode == "Stocks":
        from stock_mode import stock_app
        stock_app()

except Exception as e:
    st.error("Something went wrong. Please refresh the app.")
    print("APP ERROR:", e)
