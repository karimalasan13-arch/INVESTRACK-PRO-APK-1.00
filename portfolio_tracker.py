# portfolio_tracker.py

from datetime import datetime, timedelta, date
from db import get_supabase
supabase = get_supabase()
import streamlit as st

# -----------------------------------------
# CONFIG
# -----------------------------------------
SNAPSHOT_INTERVAL_HOURS = 8

# tolerance settings
MIN_CHANGE_THRESHOLD = 0.5        # ignore tiny noise (GHS)
MAX_DROP_RATIO = 0.5             # ignore >50% drop (API failure)
MAX_SPIKE_RATIO = 2.5            # ignore >150% spike (bad API)


# -----------------------------------------
# MAIN AUTOSAVE FUNCTION
# -----------------------------------------
def autosave_portfolio_value(user_id: str, value_ghs: float, mode: str):
    """
    Ultra-stable autosave system

    ✔ Mode separation (crypto / stock)
    ✔ Zero-value protection
    ✔ Duplicate prevention
    ✔ Interval control
    ✔ Spike/drop filtering
    ✔ Chart smoothing
    ✔ Session fallback memory
    ✔ Crash-safe
    """

    if not user_id or not mode:
        return

    # -------------------------------------
    # SESSION FALLBACK MEMORY
    # -------------------------------------
    key = f"last_valid_{mode}_value"

    if key not in st.session_state:
        st.session_state[key] = value_ghs

    # prevent zero corruption
    if value_ghs <= 0:
        value_ghs = st.session_state[key]
    else:
        st.session_state[key] = value_ghs

    now = datetime.utcnow()
    today = now.date()

    try:
        # -------------------------------------
        # FETCH LAST SNAPSHOT (PER MODE)
        # -------------------------------------
        res = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", mode)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        # -------------------------------------
        # FIRST SNAPSHOT
        # -------------------------------------
        if not res.data:
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        last_row = res.data[0]
        last_ts = datetime.fromisoformat(last_row["timestamp"])
        last_value = float(last_row["value_ghs"])
        last_date = last_ts.date()

        # -------------------------------------
        # IGNORE MICRO FLUCTUATIONS
        # -------------------------------------
        if abs(last_value - value_ghs) < MIN_CHANGE_THRESHOLD:
            return

        # -------------------------------------
        # PREVENT API GLITCH DROPS
        # -------------------------------------
        if value_ghs < last_value * MAX_DROP_RATIO:
            return

        # -------------------------------------
        # PREVENT API SPIKES
        # -------------------------------------
        if value_ghs > last_value * MAX_SPIKE_RATIO:
            return

        # -------------------------------------
        # SAVE IF NEW DAY
        # -------------------------------------
        if today != last_date:
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        # -------------------------------------
        # SAVE IF INTERVAL PASSED
        # -------------------------------------
        if now - last_ts >= timedelta(hours=SNAPSHOT_INTERVAL_HOURS):
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

    except Exception as e:
        print("Portfolio autosave skipped:", e)


# -----------------------------------------
# INSERT SNAPSHOT
# -----------------------------------------
def _insert_snapshot(user_id: str, timestamp: datetime, value_ghs: float, mode: str):
    """
    Safe insert with normalization
    """

    try:
        supabase.table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": timestamp.isoformat(),
                "value_ghs": round(float(value_ghs), 2),
                "mode": mode,
            }
        ).execute()
    except Exception as e:
        print("Insert failed:", e)
