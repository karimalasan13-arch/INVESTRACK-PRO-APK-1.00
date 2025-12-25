from datetime import datetime
from db import supabase


def autosave_portfolio_value(user_id: str, value_ghs: float):
    """
    Saves a portfolio snapshot for a specific user.
    Safe to call multiple times per day.
    """

    if not user_id:
        return

    today = datetime.utcnow().date().isoformat()

    supabase.table("portfolio_history").upsert(
        {
            "user_id": user_id,
            "date": today,
            "value_ghs": float(value_ghs),
            "updated_at": datetime.utcnow().isoformat()
        },
        on_conflict="user_id,date"
    ).execute()


def load_history(user_id: str):
    """
    Load portfolio history for a user.
    """

    if not user_id:
        return []

    res = (
        supabase.table("portfolio_history")
        .select("date,value_ghs")
        .eq("user_id", user_id)
        .order("date")
        .execute()
    )

    return res.data or []
