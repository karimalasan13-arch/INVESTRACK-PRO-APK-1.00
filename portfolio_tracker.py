# portfolio_tracker.py

from datetime import datetime, timedelta, date
from db import supabase

# -----------------------------------------
# CONFIG
# -----------------------------------------
SNAPSHOT_INTERVAL_HOURS = 8


def autosave_portfolio_value(user_id: str, value_ghs: float):
    """
    Saves portfolio value safely with:
    - Minimum 1 snapshot per calendar day
    - Additional snapshots only if interval elapsed
    - Fully idempotent
    - Production & Play Store safe
    """

    if not user_id:
        return

    now = datetime.utcnow()
    today = date.today()

    try:
        # -------------------------------------
        # Fetch last snapshot
        # -------------------------------------
        res = (
            supabase.table("portfolio_history")
            .select("timestamp")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        # -------------------------------------
        # No snapshot exists → save immediately
        # -------------------------------------
        if not res.data:
            _insert_snapshot(user_id, now, value_ghs)
            return

        last_ts = datetime.fromisoformat(res.data[0]["timestamp"])
        last_date = last_ts.date()

        # -------------------------------------
        # Save if new calendar day
        # -------------------------------------
        if today != last_date:
            _insert_snapshot(user_id, now, value_ghs)
            return

        # -------------------------------------
        # Save if interval elapsed
        # -------------------------------------
        if now - last_ts >= timedelta(hours=SNAPSHOT_INTERVAL_HOURS):
            _insert_snapshot(user_id, now, value_ghs)
            return

        # Otherwise: skip safely
        return

    except Exception as e:
        # Never crash app
        print("Portfolio autosave skipped:", e)


def _insert_snapshot(user_id: str, timestamp: datetime, value_ghs: float):
    """
    Internal helper to insert snapshot safely.
    """
    supabase.table("portfolio_history").insert(
        {
            "user_id": user_id,
            "timestamp": timestamp.isoformat(),
            "value_ghs": float(value_ghs),
        }
    ).execute()
