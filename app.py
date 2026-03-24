import streamlit as st
import time
from auth import login_ui, ensure_auth, logout

# ------------------------------------
# PAGE CONFIG
# ------------------------------------
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
# SESSION VALIDATION
# ------------------------------------
if "user" not in st.session_state or "user_id" not in st.session_state:
    st.error("Session expired. Please login again.")
    logout()
    st.stop()

user = st.session_state.user
user_id = st.session_state.user_id


# ------------------------------------
# SAFE AUTO REFRESH (60s)
# ------------------------------------
REFRESH_INTERVAL = 60

now = time.time()

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = now

elif now - st.session_state.last_refresh > REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    st.rerun()


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

    # Print full error to server logs
    print("APP ERROR:", type(e).__name__, e)
