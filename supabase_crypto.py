from supabase_client import supabase
from datetime import datetime

# -----------------------------
# CRYPTO HOLDINGS
# -----------------------------
def load_crypto_holdings(user_id):
    res = supabase.table("crypto_holdings").select("*").eq("user_id", user_id).execute()
    return {r["symbol"]: float(r["quantity"]) for r in res.data}

def save_crypto_holdings(user_id, holdings):
    supabase.table("crypto_holdings").delete().eq("user_id", user_id).execute()

    rows = [
        {"user_id": user_id, "symbol": sym, "quantity": qty}
        for sym, qty in holdings.items()
    ]
    if rows:
        supabase.table("crypto_holdings").insert(rows).execute()

# -----------------------------
# CRYPTO HISTORY
# -----------------------------
def save_crypto_value(user_id, value_ghs):
    supabase.table("portfolio_history").insert({
        "user_id": user_id,
        "asset_type": "crypto",
        "value_ghs": value_ghs,
        "timestamp": datetime.utcnow().isoformat()
    }).execute()

def load_crypto_history(user_id):
    res = supabase.table("portfolio_history") \
        .select("timestamp,value_ghs") \
        .eq("user_id", user_id) \
        .eq("asset_type", "crypto") \
        .order("timestamp") \
        .execute()
    return res.data
