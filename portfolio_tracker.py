from datetime import datetime, timedelta
from db import supabase

SNAPSHOT_INTERVAL_HOURS = 8


def autosave_portfolio_value(user_id: str, value_ghs: float):
    if not user_id:
        return

    now = datetime.utcnow()

    try:
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
            if now - last_ts < timedelta(hours=SNAPSHOT_INTERVAL_HOURS):
                return

        supabase.table("portfolio_history").insert(
            {
                "user_id": user_id,
                "timestamp": now.isoformat(),
                "value_ghs": float(value_ghs),
            }
        ).execute()

    except Exception:
        # Never crash UI
        pass
