import streamlit as st
from db import supabase

def login_ui():
    st.title("🔐 Login to InvesTrack Pro")

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

                st.write("RAW RESPONSE:", res)

                if res.user is None:
                    st.error("LOGIN FAILED")
                    st.error(res.error)
                    st.stop()

                st.success("LOGIN OK")
                st.write(res.user)

    with col2:
        if st.button("Create Account"):
            try:
                supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                st.success("Account created. You can log in now.")
            except:
                st.error("Signup failed")
