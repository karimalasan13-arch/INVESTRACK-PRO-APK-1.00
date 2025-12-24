from supabase_client import supabase
from datetime import datetime, timedelta

# ---------- SETTINGS ----------
def save_setting(key, value):
    supabase.table("user_settings").upsert({
        "key": key,
        "value": value,
        "updated_at": datetime.utcnow().isoformat()
    }).execute()

def load_setting(key, default):
    res = supabase.table("user_settings").select("value").eq("key", key).execute()
    return res.data[0]["value"] if res.data else default


# ---------- HOLDINGS ----------
def save_holdings(table, holdings: dict):
    for sym, qty in holdings.items():
        supabase.table(table).upsert({
            "symbol": sym,
            "quantity": qty,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

def load_holdings(table):
    res = supabase.table(table).select("*").execute()
    return {r["symbol"]: float(r["quantity"]) for r in res.data}


# ---------- PORTFOLIO HISTORY (8H SNAPSHOT) ----------
def autosave_portfolio_value(value):
    now = datetime.utcnow()

    res = supabase.table("portfolio_history") \
        .select("timestamp") \
        .order("timestamp", desc=True) \
        .limit(1) \
        .execute()

    if res.data:
        last = datetime.fromisoformat(res.data[0]["timestamp"])
        if now - last < timedelta(hours=8):
            return

    supabase.table("portfolio_history").insert({
        "timestamp": now.isoformat(),
        "value_ghs": value
    }).execute()

def load_portfolio_history():
    res = supabase.table("portfolio_history").select("*").order("timestamp").execute()
    return res.data
