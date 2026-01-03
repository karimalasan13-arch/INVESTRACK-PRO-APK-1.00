import streamlit as st
from db import supabase


def ensure_auth() -> bool:
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
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()


def login_ui():
    st.title("🔐 InvesTrack Pro")

    login_tab, signup_tab = st.tabs(["Login", "Create Account"])

    # ---------------- LOGIN ----------------
    with login_tab:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

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

    # ---------------- SIGNUP ----------------
    with signup_tab:
        email = st.text_input("New Email")
        password = st.text_input("New Password", type="password")

        if st.button("Create Account"):
            if len(password) < 6:
                st.error("Password must be at least 6 characters")
                return

            try:
                res = supabase.auth.sign_up({
                    "email": email.strip(),
                    "password": password,
                })

                if res.user:
                    st.success("Account created. Please log in.")
                else:
                    st.error("Signup failed")

            except Exception as e:
                st.error("Account creation failed. Contact support.")
                print("SIGNUP ERROR:", e)
