import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


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
# DB CLIENT
# -----------------------------------------
def db():
    supabase = get_supabase()

    if "access_token" in st.session_state:
        try:
            supabase.auth.set_session(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
            )
        except Exception:
            pass

    return supabase


# -----------------------------------------
# PRICE MEMORY
# -----------------------------------------
def safe_price(symbol, price):

    if "stock_price_memory" not in st.session_state:
        st.session_state.stock_price_memory = {}

    if price and price > 0:
        st.session_state.stock_price_memory[symbol] = price
        return price

    return st.session_state.stock_price_memory.get(symbol, 0)


# -----------------------------------------
# SETTINGS
# -----------------------------------------
def load_setting(user_id, key, default):

    try:
        res = (
            db()
            .table("user_settings")
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

    db().table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
        on_conflict="user_id,key",
    ).execute()


# -----------------------------------------
# HOLDINGS
# -----------------------------------------
def load_stock_holdings(user_id):

    holdings = {k: 0.0 for k in STOCK_MAP}

    try:
        res = (
            db()
            .table("stock_holdings")
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

    db().table("stock_holdings").upsert(
        rows,
        on_conflict="user_id,symbol",
    ).execute()


# -----------------------------------------
# HISTORY
# -----------------------------------------
def load_portfolio_history(user_id):

    try:
        res = (
            db()
            .table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "stock")
            .order("timestamp")
            .execute()
        )

        return res.data or []

    except Exception:
        return []


# -----------------------------------------
# FORMATTERS
# -----------------------------------------
def fmt(v):
    return f"GHS {v:,.2f}"


def pct(v):
    return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():

    st.title("📊 Stock Portfolio Tracker")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    cash = load_setting(user_id, "stock_cash", 0.0)

    holdings = load_stock_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("📊 Stock Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")

    st.sidebar.subheader("📦 Stock Holdings")

    for sym in STOCK_MAP:
        holdings[sym] = st.sidebar.number_input(sym, value=float(holdings.get(sym, 0.0)), step=1.0)

    cash = st.sidebar.number_input("💵 Cash (GHS)", value=float(cash), step=10.0)

    if st.sidebar.button("💾 Save Holdings"):

        save_stock_holdings(user_id, holdings)
        save_setting(user_id, "stock_cash", cash)

        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES
    # -------------------------------------
    try:
        prices = stock_live_prices(list(STOCK_MAP.keys())) or {}
    except Exception:
        prices = {}

    rows = []
    total_value = cash

    for sym, qty in holdings.items():

        raw_price = prices.get(sym, 0.0)
        usd_price = safe_price(sym, raw_price)

        value_ghs = usd_price * qty * rate
        total_value += value_ghs

        rows.append([sym, qty, usd_price, value_ghs])

    if cash > 0:
        rows.append(["CASH", "-", "-", cash])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    st.subheader("📘 Stock Assets")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # SNAPSHOT SAVE
    # -------------------------------------
    if total_value > 0:
        autosave_portfolio_value(user_id, total_value, "stock")

    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # VALUE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:

        h = pd.DataFrame(history)

        h["timestamp"] = pd.to_datetime(h["timestamp"], errors="coerce")

        h = h.dropna()

        h = h[h["value_ghs"] > 0]

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=h["timestamp"],
                y=h["value_ghs"],
                mode="lines",
                line=dict(shape="spline", smoothing=1.2, width=3),
                fill="tozeroy",
            )
        )

        fig.update_layout(height=350, hovermode="x unified")

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Waiting for data...")

    # ALL TIME PnL CHART (UPGRADED)
    # -------------------------------------
    st.subheader("📊 All-Time PnL")

    pnl_df = build_pnl_history(history, invested)

    if len(pnl_df) >= 2:

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=pnl_df["timestamp"],
                y=pnl_df["pnl"],
                mode="lines",
                line=dict(shape="spline", smoothing=1.2, width=3),
            )
        )

        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="PnL (GHS)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("PnL chart will appear soon.")

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
