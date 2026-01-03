import streamlit as st
from auth import login_ui, ensure_auth, logout
import traceback

# ------------------------------------
# APP CONFIG (MUST BE FIRST)
# ------------------------------------
st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide",
)

# ------------------------------------
# GLOBAL ERROR BOUNDARY (PLAY STORE SAFE)
# ------------------------------------
def safe_run(fn):
    try:
        fn()
    except Exception as e:
        st.error("Something went wrong. Please refresh the app.")
        st.caption("If the issue persists, contact support.")
        print("APP ERROR:")
        traceback.print_exc()


# ------------------------------------
# MAIN APP LOGIC
# ------------------------------------
def main():
    # HARD AUTH GATE
    if not ensure_auth():
        login_ui()
        return

    user = st.session_state.user
    user_id = st.session_state.user_id

    # SIDEBAR
    st.sidebar.success(f"Logged in as\n{user.email}")

    if st.sidebar.button("🚪 Logout"):
        logout()
        st.stop()

    mode = st.sidebar.radio(
        "Select Mode",
        ["Crypto", "Stocks"],
        key="mode_select",
    )

    # LAZY LOAD MODES
    if mode == "Crypto":
        from crypto_mode import crypto_app
        crypto_app()
    else:
        from stock_mode import stock_app
        stock_app()


# ------------------------------------
# SAFE EXECUTION
# ------------------------------------
safe_run(main)
