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
        r = (
            supabase.table("user_settings")
            .select("value")
            .eq("user_id", user_id)
            .eq("key", key)
            .single()
            .execute()
        )
        return float(r.data["value"])
    except Exception:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
        on_conflict="user_id,key",
    ).execute()


def load_stock_holdings(user_id):
    base = {k: 0.0 for k in STOCK_MAP}
    try:
        r = (
            supabase.table("stock_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for row in r.data or []:
            base[row["symbol"]] = float(row["quantity"])
    except Exception:
        pass
    return base


def save_stock_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": s, "quantity": float(q)}
        for s, q in holdings.items()
    ]
    supabase.table("stock_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


def load_portfolio_history(user_id):
    try:
        r = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .order("timestamp")
            .execute()
        )
        return r.data or []
    except Exception:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


def stock_app():
    st.title("📊 Stock Portfolio Tracker")

    if "user_id" not in st.session_state:
        st.error("Session expired. Please log in again.")
        st.stop()

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    holdings = load_stock_holdings(user_id)

    # Sidebar
    st.sidebar.header("Stock Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested))

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in STOCK_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym, value=float(holdings.get(sym, 0.0)), step=1.0
        )

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, holdings)
        st.sidebar.success("Saved")

    # Prices (safe)
    try:
        prices = stock_live_prices(list(STOCK_MAP.keys())) or {}
    except Exception:
        prices = {}

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():
        usd_price = prices.get(sym, 0.0)
        value = usd_price * qty * rate
        total_value += value
        rows.append([sym, qty, usd_price, value])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    st.subheader("📘 Assets")
    st.dataframe(df, use_container_width=True)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    autosave_portfolio_value(user_id, total_value)
    history = load_portfolio_history(user_id)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=h["timestamp"], y=h["value_ghs"], mode="lines+markers"
        ))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portfolio history will appear after multiple snapshots.")

    # MTD / YTD
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    now = datetime.utcnow()
    mtd_start = total_value
    ytd_start = total_value

    if history:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h.sort_values("timestamp")

        mtd_rows = h[h["timestamp"].dt.month == now.month]
        ytd_rows = h[h["timestamp"].dt.year == now.year]

        if not mtd_rows.empty:
            mtd_start = mtd_rows.iloc[0]["value_ghs"]
        if not ytd_rows.empty:
            ytd_start = ytd_rows.iloc[0]["value_ghs"]

    mtd_pnl = total_value - mtd_start
    ytd_pnl = total_value - ytd_start

    c1, c2 = st.columns(2)
    c1.metric("MTD", fmt(mtd_pnl), pct((mtd_pnl / mtd_start * 100) if mtd_start else 0))
    c2.metric("YTD", fmt(ytd_pnl), pct((ytd_pnl / ytd_start * 100) if ytd_start else 0))

    st.markdown("---")
    st.subheader("🍕 Allocation")

    pie_df = df[df["Value (GHS)"] > 0]
    if not pie_df.empty:
        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
            tooltip=["Asset", "Value (GHS)"],
        )
        st.altair_chart(pie, use_container_width=True)
