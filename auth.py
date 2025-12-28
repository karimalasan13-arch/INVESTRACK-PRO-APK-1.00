import streamlit as st
from db import supabase


# -------------------------------------
# AUTH CORE
# -------------------------------------
def get_current_user():
    """
    Single source of truth for authenticated user.
    Always re-check Supabase session.
    """
    try:
        res = supabase.auth.get_user()
        if res and res.user:
            return res.user
    except Exception:
        pass
    return None


def ensure_auth():
    """
    Ensures session_state.user is always valid.
    Call this once at app startup.
    """
    user = get_current_user()

    if user:
        st.session_state.user = user
        st.session_state.user_id = user.id
        return True

    # Clean stale session
    st.session_state.pop("user", None)
    st.session_state.pop("user_id", None)
    return False


def logout():
    """
    Fully log out user (Supabase + Streamlit state).
    """
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.pop("user", None)
    st.session_state.pop("user_id", None)
    st.rerun()


# -------------------------------------
# LOGIN UI
# -------------------------------------
def login_ui():
    st.title("🔐 Login")

    tab_login, tab_signup = st.tabs(["Login", "Create Account"])

    # --------------------
    # LOGIN TAB
    # --------------------
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password(
                    {
                        "email": email,
                        "password": password,
                    }
                )

                if res and res.user:
                    st.session_state.user = res.user
                    st.session_state.user_id = res.user.id
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Login failed")

            except Exception:
                st.error("Invalid email or password")

    # --------------------
    # SIGNUP TAB
    # --------------------
    with tab_signup:
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password", type="password", key="signup_password")

        if st.button("Create Account", use_container_width=True):
            try:
                res = supabase.auth.sign_up(
                    {
                        "email": new_email,
                        "password": new_password,
                    }
                )

                if res and res.user:
                    st.success("Account created. You can now log in.")
                else:
                    st.error("Sign-up failed")

            except Exception as e:
                st.error("Account creation error")
