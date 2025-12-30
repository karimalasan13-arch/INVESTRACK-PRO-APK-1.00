import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices  # 🔒 cached (3.2.1)
from portfolio_tracker import autosave_portfolio_value
from db import supabase


# -----------------------------------------
# CONFIG
# -----------------------------------------
STOCK_MAP = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "TSLA": "TSLA",
    "META": "META",
    "NVDA": "NVDA",
    "JPM": "JPM",
    "V": "V",
    "BRK-B": "BRK.B",
}


# -----------------------------------------
# HELPERS
# -----------------------------------------
def load_setting(user_id, key, default):
    try:
        res = (
            supabase.table("user_settings")
            .select("value")
            .eq("user_id", user_id)
            .eq("key", key)
            .single()
            .execute()
        )
        return float(res.data["value"])
    except Exception:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": value},
        on_conflict="user_id,key"
    ).execute()


def load_stock_holdings(user_id):
    holdings = {s: 0.0 for s in STOCK_MAP}
    try:
        res = supabase.table("stock_holdings").select("symbol,quantity").eq("user_id", user_id).execute()
        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_stock_holdings(user_id, holdings):
    rows = [{"user_id": user_id, "symbol": s, "quantity": q} for s, q in holdings.items()]
    supabase.table("stock_holdings").upsert(rows, on_conflict="user_id,symbol").execute()


def load_portfolio_history(user_id):
    try:
        res = supabase.table("portfolio_history").select("timestamp,value_ghs").eq("user_id", user_id).order("timestamp").execute()
        return res.data or []
    except Exception:
        return []


# -----------------------------------------
# MAIN
# -----------------------------------------
def stock_app():
    user_id = st.session_state.user.id
    st.title("📊 Stock Portfolio Tracker")

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    holdings = load_stock_holdings(user_id)

    # Sidebar
    rate = st.sidebar.number_input("USD → GHS Rate", value=rate)
    invested = st.sidebar.number_input("Total Investment (GHS)", value=invested)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)

    for s in STOCK_MAP:
        holdings[s] = st.sidebar.number_input(s, value=float(holdings[s]), step=1.0)

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, holdings)

    prices, status = stock_live_prices(list(STOCK_MAP.keys()))

    if status == "cached":
        st.warning("⚠ Using cached stock prices")
    elif status == "offline":
        st.error("❌ Market data unavailable — showing last known prices")

    rows, total = [], 0
    for s, q in holdings.items():
        v = prices.get(s, 0) * q * rate
        total += v
        rows.append([s, q, prices.get(s, 0), v])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    autosave_portfolio_value(user_id, total)
    history = load_portfolio_history(user_id)

    pnl = total - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    st.metric("Total Value", fmt(total), pct(pnl_pct))
