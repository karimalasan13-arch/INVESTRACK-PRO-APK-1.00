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
    st.title('InvesTrack Pro')
    st.caption('Sign in to manage your money and investments.')
    login_tab, signup_tab = st.tabs(['Login', 'Create Account'])
    with login_tab:
        email = st.text_input('Email', key='login_email')
        password = st.text_input('Password', type='password', key='login_pass')
        if st.button('Login', type='primary', use_container_width=True, key='login_btn'):
            if not email.strip() or not password:
                st.warning('Enter your email and password.')
            else:
                try:
                    result = get_supabase().auth.sign_in_with_password(
                        {'email': email.strip(), 'password': password})
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
    with signup_tab:
        email = st.text_input('New Email', key='signup_email')
        password = st.text_input('New Password', type='password', key='signup_pass')
        confirm = st.text_input('Confirm Password', type='password', key='signup_confirm_pass')
        if st.button('Create Account', type='primary', key='signup_btn', use_container_width=True):
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
                        st.success('Account created. Check your email to confirm your address, then sign in.')
                except Exception:
                    st.error('Could not create account. Please try again.')
