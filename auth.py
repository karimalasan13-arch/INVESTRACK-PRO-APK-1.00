"""Supabase authentication for InvesTrack Pro (per Streamlit session)."""
import time
import streamlit as st
from db import get_supabase


def _attach_session():
    client = get_supabase()
    access = st.session_state.get('access_token')
    refresh = st.session_state.get('refresh_token')
    if not access or not refresh:
        return client
    # Avoid network-based set_session on every widget interaction.
    if st.session_state.get('_attached_access_token') != access:
        response = client.auth.set_session(access_token=access, refresh_token=refresh)
        st.session_state._attached_access_token = access
        if response and response.session:
            st.session_state.access_token = response.session.access_token
            st.session_state.refresh_token = response.session.refresh_token
            st.session_state._attached_access_token = response.session.access_token
    return client


def get_auth_client():
    return _attach_session()


def ensure_auth() -> bool:
    if not st.session_state.get('access_token'):
        return False
    # Avoid redundant get_user requests on each navigation click. Server-side
    # validation is repeated regularly and every Supabase query still uses RLS.
    if (st.session_state.get('user_id') and st.session_state.get('user')
            and time.monotonic() - st.session_state.get('_auth_checked_at', 0) < 30):
        return True
    try:
        client = _attach_session()
        result = client.auth.get_user()
        if result and result.user:
            st.session_state.user = result.user
            st.session_state.user_id = result.user.id
            session = client.auth.get_session()
            if session:
                st.session_state.access_token = session.access_token
                st.session_state.refresh_token = session.refresh_token
                st.session_state._attached_access_token = session.access_token
            st.session_state._auth_checked_at = time.monotonic()
            return True
    except Exception:
        # A network interruption must not erase the user's stored credentials.
        # Fail closed until Supabase authentication can be verified again.
        return False
    return False


def logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def login_ui():
    """Login-first authentication with sign-up and password recovery."""
    st.markdown("""
    <style>
    .block-container {max-width: 820px !important; padding-top: 1.1rem !important;}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) {
        background: #0f172a !important;
        border: 0 !important;
        border-radius: 13px !important;
        padding: 1.15rem 1rem !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) p,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) h1,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) h2,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) label {
        color: #f1f5f9 !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) input {
        background: #334155 !important; color: white !important;
        -webkit-text-fill-color: white !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) input::placeholder {
        color: #cbd5e1 !important; -webkit-text-fill-color: #cbd5e1 !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) [data-baseweb="input"] > div {
        background: #334155 !important; border-color: #475569 !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) button[kind="primary"] {
        background: #2563eb !important; color: white !important; border: none !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.iv-auth-marker) button[kind="secondary"] {
        color: #93c5fd !important; background: transparent !important;
        border: 0 !important; box-shadow: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if 'iv_auth_view' not in st.session_state:
        st.session_state.iv_auth_view = 'login'
    view = st.session_state.iv_auth_view

    with st.container(border=True):
        st.markdown('<span class="iv-auth-marker" style="display:none"></span>', unsafe_allow_html=True)
        st.markdown("""<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;padding-top:7px;">
          <div style="width:52px;height:52px;border-radius:15px;background:#1e3a8a;display:flex;align-items:center;justify-content:center;box-shadow:0 5px 18px rgba(37,99,235,.22);">
            <svg width="31" height="31" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="InvesTrack Pro chart icon" role="img">
              <path d="M5 25.5H27" stroke="#93C5FD" stroke-width="1.5" stroke-linecap="round"/>
              <path d="M8 22V17M14 22V12M20 22V15M26 22V8" stroke="#60A5FA" stroke-width="2.7" stroke-linecap="round"/>
              <path d="M6 14L13 7L19 11L26 4" stroke="#DBEAFE" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div style="color:#f8fafc;font-weight:750;font-size:21px;letter-spacing:-.35px;line-height:1.3;">InvesTrack Pro</div>
        </div>""", unsafe_allow_html=True)
        st.markdown('<div style="text-align:center;color:#f8fafc;font-weight:700;font-size:20px;margin-top:12px">Take control of your finances.</div>', unsafe_allow_html=True)
        st.markdown('<div style="text-align:center;color:#cbd5e1;font-size:14px;margin:10px 0 18px">Log in to monitor your cashflow, track your investments, and more.</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if view == 'login':
                with st.form('iv_login_form'):
                    email = st.text_input('Email address', placeholder='Email address', label_visibility='collapsed', key='login_email')
                    password = st.text_input('Password', type='password', placeholder='Password', label_visibility='collapsed', key='login_pass')
                    submit = st.form_submit_button('Log In', type='primary', use_container_width=True)
                if submit:
                    if not email.strip() or not password:
                        st.warning('Enter your email and password.')
                    else:
                        try:
                            result = get_supabase().auth.sign_in_with_password({'email': email.strip(), 'password': password})
                            if not result.user or not result.session:
                                st.error('Login failed.')
                            else:
                                st.session_state.access_token = result.session.access_token
                                st.session_state.refresh_token = result.session.refresh_token
                                st.session_state._attached_access_token = result.session.access_token
                                st.session_state.user = result.user
                                st.session_state.user_id = result.user.id
                                st.session_state._auth_checked_at = time.monotonic()
                                st.session_state.pending_public_page = 'Dashboard'
                                st.rerun()
                        except Exception:
                            st.error('Could not sign in. Check your credentials and connection.')
                if st.button('Forgot password?', use_container_width=True, key='iv_go_reset'):
                    st.session_state.iv_auth_view = 'reset'
                    st.rerun()
            elif view == 'signup':
                st.markdown('**Create an account**')
                with st.form('iv_signup_form'):
                    email = st.text_input('Email address', placeholder='Email address', label_visibility='collapsed', key='signup_email')
                    password = st.text_input('Password', type='password', placeholder='Password (at least 6 characters)', label_visibility='collapsed', key='signup_pass')
                    confirm = st.text_input('Confirm password', type='password', placeholder='Confirm password', label_visibility='collapsed', key='signup_confirm_pass')
                    submit = st.form_submit_button('Create Account', type='primary', use_container_width=True)
                if submit:
                    if not email.strip() or len(password) < 6 or password != confirm:
                        st.warning('Enter an email and matching passwords of at least 6 characters.')
                    else:
                        try:
                            result = get_supabase().auth.sign_up({'email': email.strip(), 'password': password})
                            if result.session and result.user:
                                st.session_state.access_token = result.session.access_token
                                st.session_state.refresh_token = result.session.refresh_token
                                st.session_state._attached_access_token = result.session.access_token
                                st.session_state.user = result.user
                                st.session_state.user_id = result.user.id
                                st.session_state._auth_checked_at = time.monotonic()
                                st.session_state.pending_public_page = 'Dashboard'
                                st.rerun()
                            else:
                                st.success('If confirmation is required, check your email to confirm your address, then sign in.')
                        except Exception:
                            st.error('Could not create account. Please try again.')
            else:
                st.markdown('**Reset your password**')
                st.caption('Enter your account email to receive a password reset link.')
                with st.form('iv_reset_form'):
                    email = st.text_input('Email address', placeholder='Email address', label_visibility='collapsed', key='iv_reset_email')
                    submit = st.form_submit_button('Send Reset Email', type='primary', use_container_width=True)
                if submit:
                    if not email.strip():
                        st.warning('Enter your email address.')
                    else:
                        try:
                            get_supabase().auth.reset_password_email(email.strip())
                            st.success('If an account exists for this email, password reset instructions will be sent.')
                        except Exception:
                            st.error('Unable to request a password reset right now. Please try again.')
        if view == 'login':
            st.markdown('<div style="text-align:center;color:#cbd5e1;font-size:14px;margin-top:12px">New to InvesTrack Pro?</div>', unsafe_allow_html=True)
            if st.button('Create an account', key='iv_go_signup', use_container_width=True):
                st.session_state.iv_auth_view = 'signup'
                st.rerun()
        else:
            if st.button('← Back to Log In', key='iv_go_login', use_container_width=True):
                st.session_state.iv_auth_view = 'login'
                st.rerun()
