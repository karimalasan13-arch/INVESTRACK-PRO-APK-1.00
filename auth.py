import streamlit as st
from db import supabase


# -----------------------------------------
# ENSURE AUTH (SESSION ISOLATED)
# -----------------------------------------
def ensure_auth() -> bool:
    """
    Ensures user is authenticated using session-local token.
    Prevents cross-user leakage.
    """

    # No session → not logged in
    if "access_token" not in st.session_state:
        return False

    try:
        # Set auth for THIS session only
        supabase.auth.set_session(
            access_token=st.session_state.access_token,
            refresh_token=st.session_state.refresh_token,
        )

        res = supabase.auth.get_user()

        if res and res.user:
            st.session_state.user = res.user
            st.session_state.user_id = res.user.id
            return True

    except Exception:
        pass

    return False


# -----------------------------------------
# LOGOUT (FULL CLEAN)
# -----------------------------------------
def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    # 🔥 CRITICAL: full session wipe
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()


# -----------------------------------------
# LOGIN / SIGNUP UI
# -----------------------------------------
def login_ui():
    st.title("🔐 InvesTrack Pro")

    login_tab, signup_tab = st.tabs(["Login", "Create Account"])

    # ---------------- LOGIN ----------------
    with login_tab:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Login", key="login_btn"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password,
                })

                if res.user and res.session:

                    # ✅ STORE SESSION LOCALLY (CRITICAL FIX)
                    st.session_state.access_token = res.session.access_token
                    st.session_state.refresh_token = res.session.refresh_token

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
        email = st.text_input("New Email", key="signup_email")
        password = st.text_input("New Password", type="password", key="signup_pass")

        if st.button("Create Account", key="signup_btn"):

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
                st.error("Account creation failed.")
                print("SIGNUP ERROR:", e)

    st.markdown(
        """
        ---
        🗑 **Request Account Deletion**

        Email **delete@investrackpro.app**
        """
    )
