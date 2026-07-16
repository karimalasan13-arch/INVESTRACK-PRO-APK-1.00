import streamlit as st

from db import get_supabase


# -----------------------------------------
# AUTH SESSION ATTACHER
# -----------------------------------------
def get_auth_client():
    """
    Return the session-isolated Supabase client and attach
    the stored authentication session.
    """
    supabase = get_supabase()

    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if access_token and refresh_token:
        try:
            supabase.auth.set_session(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        except Exception:
            pass

    return supabase


# -----------------------------------------
# ENSURE AUTH
# -----------------------------------------
def ensure_auth() -> bool:
    """
    Confirm that the current Streamlit session contains
    a valid authenticated Supabase user.
    """
    if "access_token" not in st.session_state:
        return False

    supabase = get_auth_client()

    try:
        response = supabase.auth.get_user()

        if response and response.user:
            st.session_state.user = response.user
            st.session_state.user_id = response.user.id
            return True

    except Exception:
        pass

    return False


# -----------------------------------------
# LOGOUT
# -----------------------------------------
def logout():
    """
    Sign out and clear the entire Streamlit session.
    """
    try:
        get_auth_client().auth.sign_out()
    except Exception:
        pass

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()


# -----------------------------------------
# LOGIN / SIGNUP UI
# -----------------------------------------
def login_ui():
    st.markdown(
        """
        <div style="
            max-width:760px;
            padding:1.3rem 1.4rem;
            border-radius:20px;
            background:linear-gradient(135deg,#0f172a,#172554);
            color:white;
            margin-bottom:1rem;
        ">
            <h1 style="margin:0 0 0.4rem;">Welcome to InvesTrack Pro</h1>
            <p style="margin:0;color:#cbd5e1;">
                Track cash holdings, cryptocurrency and stocks in one secure portfolio.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_tab, signup_tab = st.tabs(
        ["Login", "Create Account"]
    )

    with login_tab:
        email = st.text_input(
            "Email",
            key="login_email",
            placeholder="you@example.com",
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_pass",
        )

        if st.button(
            "Login",
            key="login_btn",
            type="primary",
            use_container_width=True,
        ):
            clean_email = email.strip()

            if not clean_email or not password:
                st.warning(
                    "Enter your email address and password."
                )
                return

            supabase = get_supabase()

            try:
                response = supabase.auth.sign_in_with_password(
                    {
                        "email": clean_email,
                        "password": password,
                    }
                )

                if response.user and response.session:
                    st.session_state.access_token = (
                        response.session.access_token
                    )
                    st.session_state.refresh_token = (
                        response.session.refresh_token
                    )
                    st.session_state.user = response.user
                    st.session_state.user_id = response.user.id
                    st.session_state.profile_panel_open = False
                    st.session_state.pending_public_page = "Dashboard"

                    st.success("Login successful.")
                    st.rerun()

                else:
                    st.error(
                        "Login failed. Please try again."
                    )

            except Exception:
                st.error("Invalid email or password.")

    with signup_tab:
        email = st.text_input(
            "New Email",
            key="signup_email",
            placeholder="you@example.com",
        )

        password = st.text_input(
            "New Password",
            type="password",
            key="signup_pass",
            help="Use at least 6 characters.",
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            key="signup_confirm_pass",
        )

        if st.button(
            "Create Account",
            key="signup_btn",
            type="primary",
            use_container_width=True,
        ):
            clean_email = email.strip()

            if not clean_email:
                st.warning(
                    "Enter a valid email address."
                )
                return

            if len(password) < 6:
                st.error(
                    "Password must be at least 6 characters."
                )
                return

            if password != confirm_password:
                st.error("The passwords do not match.")
                return

            supabase = get_supabase()

            try:
                response = supabase.auth.sign_up(
                    {
                        "email": clean_email,
                        "password": password,
                    }
                )

                if response.user:
                    if response.session:
                        st.session_state.access_token = (
                            response.session.access_token
                        )
                        st.session_state.refresh_token = (
                            response.session.refresh_token
                        )
                        st.session_state.user = response.user
                        st.session_state.user_id = response.user.id
                        st.session_state.profile_panel_open = False
                        st.session_state.pending_public_page = "Dashboard"

                        st.success(
                            "Account created successfully."
                        )
                        st.rerun()

                    else:
                        st.success(
                            "Account created. Check your email if "
                            "confirmation is required, then log in."
                        )

                else:
                    st.error("Account creation failed.")

            except Exception as error:
                st.error(
                    "Account creation failed. The email may "
                    "already be registered."
                )

                print(
                    "SIGNUP ERROR:",
                    type(error).__name__,
                    error,
                )
