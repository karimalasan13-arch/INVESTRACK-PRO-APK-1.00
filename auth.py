import streamlit as st
from db import supabase


# -------------------------------------
# AUTH STATE
# -------------------------------------
def ensure_auth() -> bool:
    """
    Hard auth gate.
    """
    try:
        res = supabase.auth.get_user()
        if res and res.user:
            st.session_state.user = res.user
            st.session_state.user_id = res.user.id
            return True
    except Exception as e:
        print("AUTH CHECK ERROR:", e)

    return False


def logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print("LOGOUT ERROR:", e)

    st.session_state.clear()


# -------------------------------------
# LOGIN / SIGNUP UI (DIAGNOSTIC MODE)
# -------------------------------------
def login_ui():
    st.title("🔐 InvesTrack Pro — Auth Debug Mode")

    login_tab, signup_tab = st.tabs(["Login", "Create Account"])

    # =====================
    # LOGIN
    # =====================
    with login_tab:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")

        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password,
                })

                st.write("🔎 LOGIN RESPONSE OBJECT:")
                st.write(res)

                if res.user:
                    st.session_state.user = res.user
                    st.session_state.user_id = res.user.id
                    st.success("Login successful")
                    st.rerun()
                else:
                    st.error("Login failed — no user returned")

            except Exception as e:
                st.error("❌ LOGIN EXCEPTION")
                st.exception(e)

    # =====================
    # SIGNUP (FULL DEBUG)
    # =====================
    with signup_tab:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password (min 6 chars)", type="password", key="signup_pw")

        if st.button("Create Account"):
            st.markdown("### 🧪 Signup Debug Output")

            if len(password) < 6:
                st.error("Password must be at least 6 characters")
                return

            try:
                res = supabase.auth.sign_up({
                    "email": email.strip(),
                    "password": password,
                })

                # 1️⃣ Raw response
                st.write("📦 RAW SIGNUP RESPONSE:")
                st.write(res)

                # 2️⃣ User object
                if hasattr(res, "user"):
                    st.write("👤 USER OBJECT:")
                    st.write(res.user)
                else:
                    st.warning("No user attribute on response")

                # 3️⃣ Session object
                if hasattr(res, "session"):
                    st.write("🔐 SESSION OBJECT:")
                    st.write(res.session)

                if not res.user:
                    st.error("❌ Signup failed — Supabase returned NO user")
                else:
                    st.success("✅ Signup request accepted by Supabase")

            except Exception as e:
                st.error("🔥 SIGNUP EXCEPTION (RAW)")
                st.exception(e)

                # Attempt to extract deeper info
                if hasattr(e, "args"):
                    st.write("📛 Exception args:")
                    st.write(e.args)

                if hasattr(e, "__dict__"):
                    st.write("📛 Exception dict:")
                    st.write(e.__dict__)
