import streamlit as st
from db import supabase


# -------------------------------------
# AUTH HELPERS
# -------------------------------------
def get_current_user():
    """
    Always re-validate auth with Supabase.
    This prevents ghost sessions after sleep / reload.
    """
    try:
        res = supabase.auth.get_user()
        return res.user
    except Exception:
        return None


def logout():
    """
    Fully invalidate Supabase session
    """
    try:
        supabase.auth.sign_out()
    except Exception:
        pass


# -------------------------------------
# LOGIN UI
# -------------------------------------
def login_ui():
    st.title("🔐 Login")

    tab1, tab2 = st.tabs(["Login", "Create Account"])

    # --------------------
    # LOGIN
    # --------------------
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")

        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })

                if res.user:
                    st.session_state.user = res.user
                    st.session_state.user_id = res.user.id
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Login failed")

            except Exception as e:
                st.error("Invalid email or password")

    # --------------------
    # SIGN UP
    # --------------------
    with tab2:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_pw")

        if st.button("Create Account"):
            try:
                res = supabase.auth.sign_up({
                    "email": new_email,
                    "password": new_password
                })

                if res.user:
                    st.success("Account created. You may now log in.")
                else:
                    st.error("Sign-up failed")

            except Exception as e:
                st.error("Account creation error")
