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
    h = {k: 0.0 for k in STOCK_MAP}
    try:
        res = (
            supabase.table("stock_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for r in res.data or []:
            h[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return h


def save_stock_holdings(user_id, holdings):
    rows = [{"user_id": user_id, "symbol": s, "quantity": q} for s, q in holdings.items()]
    supabase.table("stock_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


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


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


def stock_app():
    user_id = st.session_state.user.id
    st.title("📊 Stock Portfolio")

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    assets = load_stock_holdings(user_id)

    st.sidebar.header("Stock Settings")
    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Invested (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)

    for s in STOCK_MAP:
        assets[s] = st.sidebar.number_input(
            f"{s} qty", assets[s], step=1.0, key=f"s_{s}"
        )

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, assets)

    prices = stock_live_prices(list(STOCK_MAP.keys()))
    if not isinstance(prices, dict):
        prices = {}

    rows, total = [], 0.0
    for s, q in assets.items():
        p = prices.get(s, 0.0)
        v = p * q * rate
        total += v
        rows.append([s, q, p, v])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "USD", "GHS Value"])
    st.dataframe(df, use_container_width=True)

    autosave_portfolio_value(user_id, total)
    history = load_portfolio_history(user_id)

    pnl = total - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total", fmt(total))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h["timestamp"], y=df_h["value_ghs"], mode="lines+markers"
        ))
        fig.update_layout(dragmode="zoom")
        st.plotly_chart(fig, use_container_width=True)

        now = datetime.utcnow()
        mtd = df_h[df_h["timestamp"].dt.month == now.month]
        ytd = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total

        c1, c2 = st.columns(2)
        c1.metric("MTD", fmt(total - mtd_start),
                  pct((total - mtd_start) / mtd_start * 100 if mtd_start else 0))
        c2.metric("YTD", fmt(total - ytd_start),
                  pct((total - ytd_start) / ytd_start * 100 if ytd_start else 0))
