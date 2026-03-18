import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
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
# PRICE MEMORY (CRITICAL FIX)
# -----------------------------------------
def safe_price(symbol, price):
    if "stock_price_memory" not in st.session_state:
        st.session_state.stock_price_memory = {}

    if price and price > 0:
        st.session_state.stock_price_memory[symbol] = price
        return price

    return st.session_state.stock_price_memory.get(symbol, 0)


# -----------------------------------------
# SUPABASE HELPERS
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
        {"user_id": user_id, "key": key, "value": float(value)},
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
        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_stock_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": k, "quantity": float(v)}
        for k, v in holdings.items()
    ]
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


# -----------------------------------------
# FORMATTERS
# -----------------------------------------
def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():

    st.title("📊 Stock Portfolio Tracker")

    # SAFETY: prevent crash if session missing
    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    # -------------------------------------
    # LOAD DATA
    # -------------------------------------
    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    holdings = load_stock_holdings(user_id)

    # -------------------------------------
    # SIDEBAR (FORCED REFRESH FIX)
    # -------------------------------------
    st.sidebar.header("📊 Stock Settings")

    rate = st.sidebar.number_input(
        "USD → GHS",
        value=float(rate),
        step=0.1,
        key="stock_rate_input"
    )

    invested = st.sidebar.number_input(
        "Total Invested (GHS)",
        value=float(invested),
        step=10.0,
        key="stock_investment_input"
    )

    if st.sidebar.button("💾 Save Settings", key="stock_save_settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Stock Holdings")

    for sym in STOCK_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            step=1.0,
            key=f"stock_{sym}"
        )

    if st.sidebar.button("💾 Save Holdings", key="stock_save_holdings"):
        save_stock_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES (FIXED)
    # -------------------------------------
    try:
        prices = stock_live_prices(list(STOCK_MAP.keys())) or {}
    except Exception:
        prices = {}

    using_cache = not bool(prices)

    if using_cache:
        st.warning("⚠️ Using cached prices (API unavailable)")

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():

        raw_price = prices.get(sym, 0.0)
        usd_price = safe_price(sym, raw_price)

        value_ghs = usd_price * qty * rate
        total_value += value_ghs

        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(
        rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"]
    )

    st.subheader("📘 Stock Assets")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # PnL
    # -------------------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # CRITICAL FIX: don't save garbage
    if total_value > 0:
        autosave_portfolio_value(user_id, total_value)

    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:

        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        # REMOVE BAD DATA
        h = h[h["value_ghs"] > 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines+markers"
        ))

        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="Value (GHS)",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Portfolio history will appear after multiple updates.")

    # -------------------------------------
    # MTD / YTD
    # -------------------------------------
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    if history:

        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h[h["value_ghs"] > 0]
        h = h.sort_values("timestamp")

        now = datetime.utcnow()

        mtd = h[h["timestamp"].dt.month == now.month]
        ytd = h[h["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total_value
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total_value

        mtd_pnl = total_value - mtd_start
        ytd_pnl = total_value - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0.0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0.0

    else:
        mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0.0

    c1, c2 = st.columns(2)

    c1.metric("MTD", fmt(mtd_pnl), pct(mtd_pct))
    c2.metric("YTD", fmt(ytd_pnl), pct(ytd_pct))

    # -------------------------------------
    # ALLOCATION
    # -------------------------------------
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
    else:
        st.info("Allocation will appear once assets have value.")
