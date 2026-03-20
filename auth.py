import streamlit as st
from db import get_supabase


# -----------------------------------------
# AUTH SESSION ATTACHER (CRITICAL)
# -----------------------------------------
def get_auth_client():
    """
    Returns a Supabase client bound to THIS user's session.
    """
    supabase = get_supabase()

    if "access_token" in st.session_state:
        try:
            supabase.auth.set_session(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
            )
        except Exception:
            pass

    return supabase


# -----------------------------------------
# ENSURE AUTH (STABLE + ISOLATED)
# -----------------------------------------
def ensure_auth() -> bool:

    if "access_token" not in st.session_state:
        return False

    supabase = get_auth_client()

    try:
        res = supabase.auth.get_user()

        if res and res.user:
            st.session_state.user = res.user
            st.session_state.user_id = res.user.id
            return True

    except Exception:
        pass

    return False


# -----------------------------------------
# LOGOUT (FULL HARD RESET)
# -----------------------------------------
def logout():

    supabase = get_auth_client()

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    # 🔥 FULL WIPE
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

            supabase = get_supabase()  # 🔥 fresh client

            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password,
                })

                if res.user and res.session:

                    # ✅ STORE TOKENS (PER SESSION)
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

            supabase = get_supabase()

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

    # -----------------------------------------
    # DELETE NOTICE
    # -----------------------------------------
    st.markdown(
        """
        ---
        🗑 **Request Account Deletion**

        Email **delete@investrackpro.app**
        """
    )
