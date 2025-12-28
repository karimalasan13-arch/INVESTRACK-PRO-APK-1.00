from datetime import datetime, timedelta, timezone
from db import supabase


SAVE_INTERVAL_HOURS = 8


def autosave_portfolio_value(user_id: str, value_ghs: float):
    """
    Save portfolio value at most once every 8 hours per user.
    Safe for Streamlit Cloud sleep/restart.
    """

    if not user_id:
        return

    now = datetime.now(timezone.utc)

    try:
        # Fetch last saved snapshot
        res = (
            supabase.table("portfolio_history")
            .select("timestamp")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if res.data:
            last_ts = datetime.fromisoformat(res.data[0]["timestamp"])
            if now - last_ts < timedelta(hours=SAVE_INTERVAL_HOURS):
                return  # too soon → skip save

        # Insert new snapshot
        supabase.table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": now.isoformat(),
                "value_ghs": float(value_ghs),
            }
        ).execute()

    except Exception as e:
        # Never crash the app
        print("⚠️ Portfolio autosave failed:", e)
