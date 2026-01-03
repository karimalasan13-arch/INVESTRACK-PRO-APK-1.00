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
            try:
               res = supabase.auth.sign_up({
                   "email": new_email.strip(),
                   "password": new_password,
               })

               st.write("DEBUG RESPONSE:", res)

               if res.user:
                   st.success("User object created")
               else:
            st.error("No user returned")

            except Exception as e:
                st.error("RAW SIGNUP ERROR:")
                st.exception(e)
            
