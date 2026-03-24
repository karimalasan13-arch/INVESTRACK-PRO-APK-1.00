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
# 🔐 SESSION-BOUND CLIENT
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
# PRICE MEMORY (ANTI-ZERO FIX)
# -----------------------------------------
def safe_price(symbol, price):

    if "stock_price_memory" not in st.session_state:
        st.session_state.stock_price_memory = {}

    if price and price > 0:
        st.session_state.stock_price_memory[symbol] = price
        return price

    return st.session_state.stock_price_memory.get(symbol, 0)


# -----------------------------------------
# BUILD PnL HISTORY
# -----------------------------------------
def build_pnl_history(history, invested):

    if not history:
        return pd.DataFrame()

    h = pd.DataFrame(history)

    if h.empty:
        return pd.DataFrame()

    h["timestamp"] = pd.to_datetime(h["timestamp"])

    h = h[h["value_ghs"] > 0]

    h["pnl"] = h["value_ghs"] - invested

    return h.sort_values("timestamp")


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

    # -------------------------------------
    # LOAD DATA
    # -------------------------------------
    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    holdings = load_stock_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("📊 Stock Settings")

    rate = st.sidebar.number_input(
        "USD → GHS",
        value=float(rate),
        step=0.1,
        key="stock_rate_input",
    )

    invested = st.sidebar.number_input(
        "Total Invested (GHS)",
        value=float(invested),
        step=10.0,
        key="stock_investment_input",
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
            key=f"stock_{sym}",
        )

    if st.sidebar.button("💾 Save Holdings", key="stock_save_holdings"):

        save_stock_holdings(user_id, holdings)

        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES
    # -------------------------------------
    try:
        prices = stock_live_prices(list(STOCK_MAP.keys())) or {}
    except Exception:
        prices = {}

    if not prices:
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
        rows,
        columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"],
    )

    st.subheader("📘 Stock Assets")

    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # VALUE PROTECTION
    # -------------------------------------
    if "last_valid_stock_total" not in st.session_state:
        st.session_state.last_valid_stock_total = total_value

    if total_value <= 0:
        total_value = st.session_state.last_valid_stock_total
    else:
        st.session_state.last_valid_stock_total = total_value

    # -------------------------------------
    # SAVE SNAPSHOT
    # -------------------------------------
    if total_value > 0:
        autosave_portfolio_value(user_id, total_value, "stock")

    history = load_portfolio_history(user_id)
