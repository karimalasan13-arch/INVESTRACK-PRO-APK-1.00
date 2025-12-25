import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase
from user_session import get_user_id


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
            .select(key) \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        if res.data and key in res.data:
            return float(res.data[key])
    except:
        pass
    return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert({
        "user_id": user_id,
        key: value
    }).execute()


def load_stock_holdings(user_id):
    holdings = {sym: 0.0 for sym in STOCK_MAP}
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
    rows = [
        {"user_id": user_id, "symbol": s, "quantity": q}
        for s, q in holdings.items()
    ]
    supabase.table("stock_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


def load_history(user_id):
    try:
        res = supabase.table("portfolio_history") \
            .select("date,value_ghs") \
            .eq("user_id", user_id) \
            .order("date") \
            .execute()
        return res.data or []
    except:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():
    user_id = get_user_id()
    if not user_id:
        st.warning("Please log in to view your portfolio.")
        return

    st.title("📊 Stock Portfolio Tracker")

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    assets = load_stock_holdings(user_id)

    # -------- Sidebar --------
    st.sidebar.header("Stock Settings")

    rate = st.sidebar.number_input(
        "USD → GHS Rate", value=rate, step=0.1
    )
    invested = st.sidebar.number_input(
        "Total Investment (GHS)", value=invested, step=10.0
    )

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in STOCK_MAP:
        assets[sym] = st.sidebar.number_input(
            f"{sym} quantity",
            value=float(assets.get(sym, 0)),
            step=1.0,
            key=f"stk_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, assets)
        st.sidebar.success("Holdings saved")

    # -------- Prices --------
    prices = stock_live_prices(symbols=list(STOCK_MAP.keys()))

    rows, total_value = [], 0.0
    for sym, qty in assets.items():
        price = prices.get(sym, 0)
        value = price * qty * rate
        total_value += value
        rows.append([sym, qty, price, value])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price USD", "Value GHS"])
    st.dataframe(df, use_container_width=True)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    autosave_portfolio_value(user_id, total_value)

    history = load_history(user_id)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    # -------- Line Chart --------
    st.subheader("📈 Portfolio Value Over Time")
    if len(history) >= 2:
        fig = go.Figure(go.Scatter(
            x=[h["date"] for h in history],
            y=[h["value_ghs"] for h in history],
            mode="lines+markers"
        ))
        fig.update_layout(dragmode="zoom", height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("History will appear as data is collected.")

    # -------- Allocation --------
    st.subheader("🍕 Allocation")
    df_pie = df[df["Value GHS"] > 0][["Asset", "Value GHS"]]
    if not df_pie.empty:
        st.altair_chart(
            alt.Chart(df_pie).mark_arc().encode(
                theta="Value GHS:Q",
                color="Asset:N"
            ),
            use_container_width=True
        )

