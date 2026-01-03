import streamlit as st
from db import supabase


# -------------------------------------
# AUTH STATE MANAGEMENT
# -------------------------------------
def ensure_auth() -> bool:
    """
    Ensures user session is valid and synced.
    Returns True if authenticated.
    """
    try:
        res = supabase.auth.get_user()
        if res and res.user:
            st.session_state.user = res.user
            st.session_state.user_id = res.user.id
            return True
    except Exception:
        pass

    return False


def logout():
    """
    Fully logs out user
    """
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.clear()


# -------------------------------------
# LOGIN / SIGNUP UI
# -------------------------------------
def login_ui():
    st.title("🔐 InvesTrack Pro")

    tab_login, tab_signup = st.tabs(["Login", "Create Account"])

    # -----------------------------
    # LOGIN TAB
    # -----------------------------
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")

        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password,
                })

                if res.user:
                    st.session_state.user = res.user
                    st.session_state.user_id = res.user.id
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Login failed")

            except Exception:
                st.error("Invalid email or password")

    # -----------------------------
    # SIGN UP TAB
    # -----------------------------
    with tab_signup:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input(
            "Password (min 6 chars)",
            type="password",
            key="signup_pw",
        )

        if st.button("Create Account"):
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters")
                return

            try:
                # 1️⃣ Create account
                res = supabase.auth.sign_up({
                    "email": new_email.strip(),
                    "password": new_password,
                })

                if not res.user:
                    st.error("Account creation failed")
                    return

                # 2️⃣ Auto-login immediately
                res_login = supabase.auth.sign_in_with_password({
                    "email": new_email.strip(),
                    "password": new_password,
                })

                if res_login.user:
                    st.session_state.user = res_login.user
                    st.session_state.user_id = res_login.user.id
                    st.success("Account created & logged in")
                    st.rerun()
                else:
                    st.success("Account created. Please log in.")

            except Exception as e:
                st.error("Account creation error")
