# portfolio_tracker.py

from datetime import datetime
from db import get_supabase
import streamlit as st


# -----------------------------------------
# SESSION-BOUND CLIENT
# -----------------------------------------
def db():
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
# ✅ MANUAL SNAPSHOT (NEW - RELIABLE)
# -----------------------------------------
def manual_snapshot(user_id: str, value_ghs: float, mode: str):

    if not user_id or value_ghs <= 0:
        return False

    try:
        db().table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "value_ghs": round(float(value_ghs), 2),
                "mode": mode,
            }
        ).execute()

        return True

    except Exception as e:
        print("Manual snapshot failed:", e)
        return False


# -----------------------------------------
# ⚡ LIGHT AUTOSAVE (NON-BLOCKING)
# -----------------------------------------
def autosave_portfolio_value(user_id: str, value_ghs: float, mode: str):

    if not user_id or value_ghs <= 0:
        return

    try:
        db().table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "value_ghs": round(float(value_ghs), 2),
                "mode": mode,
            }
        ).execute()

    except Exception:
        pass
