# portfolio_tracker.py

from datetime import datetime, timedelta
from db import supabase


def autosave_portfolio_value(user_id: str, value_ghs: float):
    """
    Saves portfolio value once per day per user.
    Uses UPSERT to avoid unique constraint crashes.
    """

    if not user_id:
        return

    today = datetime.utcnow().date().isoformat()

    try:
        supabase.table("portfolio_history").upsert(
            {
                "user_id": user_id,
                "date": today,
                "value_ghs": float(value_ghs),
            },
            on_conflict="user_id,date"
        ).execute()

    except Exception as e:
        # Do NOT crash the app — log instead
        print("Portfolio autosave failed:", e)
