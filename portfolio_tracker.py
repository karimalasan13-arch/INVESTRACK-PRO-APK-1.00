# portfolio_tracker.py

from datetime import datetime, timedelta, date
from db import supabase
import streamlit as st

# -----------------------------------------
# CONFIG
# -----------------------------------------
SNAPSHOT_INTERVAL_HOURS = 8


def autosave_portfolio_value(user_id: str, value_ghs: float, mode: str):
    """
    Production-grade autosave with:
    ✔ Mode separation (crypto / stocks)
    ✔ Zero-value protection
    ✔ Duplicate prevention
    ✔ Interval control
    ✔ Crash-safe execution
    """

    if not user_id or not mode:
        return

    # 🚫 Prevent bad values
    if value_ghs <= 0:
        return

    now = datetime.utcnow()
    today = date.today()

    try:
        # -------------------------------------
        # Fetch last snapshot (PER MODE)
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
        # First snapshot
        # -------------------------------------
        if not res.data:
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        last_row = res.data[0]
        last_ts = datetime.fromisoformat(last_row["timestamp"])
        last_value = float(last_row["value_ghs"])
        last_date = last_ts.date()

        # -------------------------------------
        # 🚫 Prevent duplicate values
        # -------------------------------------
        if abs(last_value - value_ghs) < 0.01:
            return

        # -------------------------------------
        # 🚫 Prevent extreme drops (API glitch)
        # -------------------------------------
        if value_ghs < last_value * 0.5:
            return

        # -------------------------------------
        # Save if new day
        # -------------------------------------
        if today != last_date:
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

        # -------------------------------------
        # Save if interval passed
        # -------------------------------------
        if now - last_ts >= timedelta(hours=SNAPSHOT_INTERVAL_HOURS):
            _insert_snapshot(user_id, now, value_ghs, mode)
            return

    except Exception as e:
        print("Portfolio autosave skipped:", e)


def _insert_snapshot(user_id: str, timestamp: datetime, value_ghs: float, mode: str):
    """
    Safe insert
    """
    supabase.table("portfolio_history").insert(
        {
            "user_id": user_id,
            "timestamp": timestamp.isoformat(),
            "value_ghs": float(value_ghs),
            "mode": mode,
        }
    ).execute()
