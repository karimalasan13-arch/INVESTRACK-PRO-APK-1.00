import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase


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
        on_conflict="user_id,key",
    ).execute()


def load_stock_holdings(user_id):
    holdings = {k: 0.0 for k in STOCK_MAP}
    try:
        res = (
            supabase.table("stock_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for r in res.data:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_stock_holdings(user_id, holdings):
    rows = [{"user_id": user_id, "symbol": s, "quantity": q} for s, q in holdings.items()]
    supabase.table("stock_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


@st.cache_data(ttl=60)
def load_portfolio_history(user_id):
    try:
        res = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def stock_app():
    user_id = st.session_state.user_id
    st.title("📊 Stock Portfolio Tracker")

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    assets = load_stock_holdings(user_id)

    st.sidebar.header("Stock Settings")
    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Invested", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Saved")

    for sym in STOCK_MAP:
        assets[sym] = st.sidebar.number_input(
            f"{sym} quantity", value=assets[sym], step=1.0, key=f"stk_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, assets)
        st.sidebar.success("Holdings saved")

    prices = stock_live_prices(list(STOCK_MAP.keys()))

    rows, total = [], 0.0
    for sym, qty in assets.items():
        usd = prices.get(sym, 0.0)
        ghs = usd * qty * rate
        total += ghs
        rows.append([sym, qty, usd, usd * qty, ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price USD", "Value USD", "Value GHS"])
    st.dataframe(df, use_container_width=True)

    pnl = total - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    if not st.session_state.get("stock_saved_today"):
        autosave_portfolio_value(user_id, total)
        st.session_state.stock_saved_today = True

    history = load_portfolio_history(user_id)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", f"GHS {total:,.2f}")
    c2.metric("Invested", f"GHS {invested:,.2f}")
    c3.metric("PnL", f"GHS {pnl:,.2f}", f"{pnl_pct:.2f}%")

    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        fig = go.Figure(go.Scatter(x=df_h["timestamp"], y=df_h["value_ghs"]))
        fig.update_layout(height=350, dragmode="zoom")
        st.plotly_chart(fig, use_container_width=True)
