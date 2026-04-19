from datetime import datetime, timedelta
from db import get_supabase
import streamlit as st


# -----------------------------------------
# CONFIG
# -----------------------------------------
SNAPSHOT_INTERVAL_HOURS = 8

MIN_CHANGE_THRESHOLD = 0.5
MAX_DROP_RATIO = 0.5
MAX_SPIKE_RATIO = 2.5


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
# 🔥 MANUAL SNAPSHOT (NEW)
# -----------------------------------------
def force_snapshot(user_id: str, value_ghs: float, mode: str):

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
# MAIN AUTOSAVE FUNCTION (STABLE)
# -----------------------------------------
def autosave_portfolio_value(user_id: str, value_ghs: float, mode: str):

    if not user_id or not mode:
        return

    key = f"last_valid_{mode}_value"

    if key not in st.session_state:
        st.session_state[key] = value_ghs

    # ZERO PROTECTION
    if value_ghs <= 0:
        value_ghs = st.session_state[key]
    else:
        st.session_state[key] = value_ghs

    now = datetime.utcnow()
    today = now.date()

    try:
        res = (
            db().table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", mode)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        # FIRST SNAPSHOT
        if not res.data:
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        last_row = res.data[0]

        # ✅ SAFE TIMESTAMP PARSE (CRITICAL FIX)
        try:
            last_ts = datetime.fromisoformat(
                last_row["timestamp"].replace("Z", "")
            )
        except Exception:
            last_ts = now - timedelta(hours=SNAPSHOT_INTERVAL_HOURS + 1)

        last_value = float(last_row["value_ghs"])
        last_date = last_ts.date()

        # -------------------------------------
        # SAVE RULES (REORDERED FOR RELIABILITY)
        # -------------------------------------

        # INTERVAL SNAPSHOT (PRIMARY DRIVER)
        if now - last_ts >= timedelta(hours=SNAPSHOT_INTERVAL_HOURS):
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        # NEW DAY SNAPSHOT
        if today != last_date:
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        # DROP PROTECTION
        if value_ghs < last_value * MAX_DROP_RATIO:
            return

        # SPIKE PROTECTION
        if value_ghs > last_value * MAX_SPIKE_RATIO:
            return

        # NOISE FILTER
        if abs(last_value - value_ghs) < MIN_CHANGE_THRESHOLD:
            return

        # SIGNIFICANT MOVE SNAPSHOT
        _insert_snapshot(user_id, now, value_ghs, mode)

    except Exception as e:
        print("Autosave skipped:", e)


# -----------------------------------------
# INSERT SNAPSHOT
# -----------------------------------------
def _insert_snapshot(user_id: str, timestamp: datetime, value_ghs: float, mode: str):

    try:
        db().table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": timestamp.isoformat(),
                "value_ghs": round(float(value_ghs), 2),
                "mode": mode,
            }
        ).execute()

    except Exception as e:
        print("Insert failed:", e)
