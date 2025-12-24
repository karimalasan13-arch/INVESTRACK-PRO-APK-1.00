from supabase_client import supabase
from datetime import datetime

def load_stock_holdings(user_id):
    res = supabase.table("stock_holdings").select("*").eq("user_id", user_id).execute()
    return {r["symbol"]: float(r["quantity"]) for r in res.data}

def save_stock_holdings(user_id, holdings):
    supabase.table("stock_holdings").delete().eq("user_id", user_id).execute()
    rows = [
        {"user_id": user_id, "symbol": sym, "quantity": qty}
        for sym, qty in holdings.items()
    ]
    if rows:
        supabase.table("stock_holdings").insert(rows).execute()

def save_stock_value(user_id, value_ghs):
    supabase.table("portfolio_history").insert({
        "user_id": user_id,
        "asset_type": "stock",
        "value_ghs": value_ghs,
        "timestamp": datetime.utcnow().isoformat()
    }).execute()

def load_stock_history(user_id):
    res = supabase.table("portfolio_history") \
        .select("timestamp,value_ghs") \
        .eq("user_id", user_id) \
        .eq("asset_type", "stock") \
        .order("timestamp") \
        .execute()
    return res.data
