import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase
from user_session import get_user_id

supabase = get_supabase()
supabase.table("user_settings")...


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
# SUPABASE HELPERS
# -----------------------------------------
def load_setting(user_id, key, default):
    try:
        res = supabase.table("user_settings") \
            .select("value") \
            .eq("user_id", user_id) \
            .eq("key", key) \
            .single() \
            .execute()

        if res.data:
            return float(res.data["value"])
    except:
        pass

    return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert({
        "user_id": user_id,
        "key": key,
        "value": value
    }).execute()



def load_stock_holdings(user_id):
    holdings = {k: 0.0 for k in STOCK_MAP}
    try:
        res = supabase.table("stock_holdings") \
            .select("symbol,quantity") \
            .eq("user_id", user_id) \
            .execute()
        for row in res.data:
            holdings[row["symbol"]] = float(row["quantity"])
    except:
        pass
    return holdings


def save_stock_holdings(user_id, holdings):
    rows = [{
        "user_id": user_id,
        "symbol": sym,
        "quantity": qty
    } for sym, qty in holdings.items()]

    supabase.table("stock_holdings").upsert(
        rows,
        on_conflict="user_id,symbol"
    ).execute()


def load_portfolio_history(user_id):
    try:
        res = supabase.table("portfolio_history") \
            .select("timestamp,value_ghs") \
            .eq("user_id", user_id) \
            .order("timestamp") \
            .execute()
        return res.data or []
    except:
        return []


# -----------------------------------------
# FORMATTERS
# -----------------------------------------
def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():
    user_id = get_user_id()
    if not user_id:
        st.error("User not authenticated")
        return

    st.title("📊 Stock Portfolio Tracker")

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    assets = load_stock_holdings(user_id)

    st.sidebar.header("Stock Settings")

    rate = st.sidebar.number_input(
        "USD → GHS Rate",
        value=rate,
        step=0.1
    )

    invested = st.sidebar.number_input(
        "Total Stock Investment (GHS)",
        value=invested,
        step=10.0
    )

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in STOCK_MAP:
        assets[sym] = st.sidebar.number_input(
            f"{sym} quantity",
            value=float(assets.get(sym, 0)),
            step=1.0,
            key=f"stock_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, assets)
        st.sidebar.success("Holdings saved")

    prices = stock_live_prices(
        symbols=[s for s, q in assets.items() if q > 0] or list(STOCK_MAP)
    )

    rows = []
    total_value_ghs = 0.0

    for sym, qty in assets.items():
        usd = prices.get(sym, 0)
        ghs = usd * qty * rate
        total_value_ghs += ghs
        rows.append([sym, qty, usd, usd * qty, ghs])

    df = pd.DataFrame(rows, columns=[
        "Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"
    ])

    st.subheader("📘 Asset Breakdown")
    st.dataframe(df, use_container_width=True)

    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    autosave_portfolio_value(user_id, total_value_ghs)

    history = load_portfolio_history(user_id)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value_ghs))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    st.subheader("📈 Portfolio Value Over Time")
    if len(history) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[h["timestamp"] for h in history],
            y=[h["value_ghs"] for h in history],
            mode="lines+markers"
        ))
        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("History will appear after snapshots are saved.")
