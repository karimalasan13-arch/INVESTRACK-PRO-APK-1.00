import streamlit as st
from db import supabase


def login_ui():
    st.title("🔐 Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error("Invalid login credentials")

    with col2:
        if st.button("Register"):
            try:
                res = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.success("Account created. Please log in.")
            except Exception as e:
                st.error("Failed to create user")
