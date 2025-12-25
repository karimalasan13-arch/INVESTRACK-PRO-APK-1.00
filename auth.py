import streamlit as st
from supabase import create_client, Client


# --------------------------------------------------
# Supabase client (from Streamlit secrets)
# --------------------------------------------------
def get_supabase() -> Client:
    if "SUPABASE_URL" not in st.secrets or "SUPABASE_ANON_KEY" not in st.secrets:
        raise RuntimeError("Supabase credentials not found in Streamlit secrets")

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"]
    )


supabase = get_supabase()


# --------------------------------------------------
# Session helpers
# --------------------------------------------------
def is_logged_in() -> bool:
    return "user" in st.session_state and st.session_state["user"] is not None


def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.clear()
    st.rerun()


# --------------------------------------------------
# Login / Signup UI
# --------------------------------------------------
def auth_ui():
    st.title("🔐 InvesTrack Login")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    # ---------------- LOGIN ----------------
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", use_container_width=True):
            if not email or not password:
                st.error("Please enter email and password")
                st.stop()

            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                # 🔴 IMPORTANT: explicit failure check
                if res.user is None:
                    st.error(res.error.message if res.error else "Login failed")
                    st.stop()

                # ✅ Success
                st.session_state["user"] = res.user
                st.session_state["access_token"] = res.session.access_token
                st.success("Login successful")
                st.rerun()

            except Exception as e:
                st.error(str(e))

    # ---------------- SIGNUP ----------------
    with tab_signup:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")

        if st.button("Create Account", use_container_width=True):
            if not new_email or not new_password:
                st.error("Please enter email and password")
                st.stop()

            try:
                res = supabase.auth.sign_up({
                    "email": new_email,
                    "password": new_password
                })

                if res.user is None:
                    st.error(res.error.message if res.error else "Signup failed")
                    st.stop()

                st.success("Account created. You can now log in.")
            except Exception as e:
                st.error(str(e))


# --------------------------------------------------
# Guard function (use this in app.py)
# --------------------------------------------------
def require_auth():
    if not is_logged_in():
        auth_ui()
        st.stop()


# --------------------------------------------------
# Optional header widget
# --------------------------------------------------
def auth_header():
    if is_logged_in():
        user = st.session_state["user"]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.caption(f"Logged in as **{user.email}**")
        with col2:
            if st.button("Logout"):
                logout()
