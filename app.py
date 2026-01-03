import streamlit as st
from auth import login_ui, ensure_auth, logout

# ------------------------------------
# APP CONFIG
# ------------------------------------
st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide",
)

# ------------------------------------
# AUTH GATE
# ------------------------------------
if not ensure_auth():
    login_ui()
    st.stop()

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
# SAFE MODE LOADER (CRITICAL)
# ------------------------------------
try:
    if mode == "Crypto":
        from crypto_mode import crypto_app
        crypto_app()
    else:
        from stock_mode import stock_app
        stock_app()

except Exception as e:
    # Production-safe fallback
    st.error("⚠️ Something went wrong. The app is running in safe mode.")
    st.info("Please refresh the app. If the issue persists, try again later.")

    # Optional debug log (not user-facing)
    print("APP SAFE MODE ERROR:", e)
