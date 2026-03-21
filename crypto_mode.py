import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


# -----------------------------------------
# CONFIG
# -----------------------------------------
API_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LTC": "litecoin",
    "USDT": "tether",
}


# -----------------------------------------
# 🔐 SESSION-BOUND CLIENT (CRITICAL FIX)
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
    if "crypto_price_memory" not in st.session_state:
        st.session_state.crypto_price_memory = {}

    if price and price > 0:
        st.session_state.crypto_price_memory[symbol] = price
        return price

    return st.session_state.crypto_price_memory.get(symbol, 0)


# -----------------------------------------
# PnL HISTORY
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
            db().table("user_settings")
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
def load_crypto_holdings(user_id):
    holdings = {k: 0.0 for k in API_MAP}
    try:
        res = (
            db().table("crypto_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": k, "quantity": float(v)}
        for k, v in holdings.items()
    ]
    db().table("crypto_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


# -----------------------------------------
# HISTORY
# -----------------------------------------
def load_portfolio_history(user_id):
    try:
        res = (
            db().table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "crypto")
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
def crypto_app():

    st.title("💰 Crypto Portfolio Tracker")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    # -------------------------------------
    # LOAD DATA
    # -------------------------------------
    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("💰 Crypto Settings")

    rate = st.sidebar.number_input(
        "USD → GHS", value=float(rate), step=0.1, key="crypto_rate_input"
    )

    invested = st.sidebar.number_input(
        "Total Invested (GHS)", value=float(invested), step=10.0, key="crypto_investment_input"
    )

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Crypto Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            step=0.0001,
            key=f"crypto_{sym}"
        )

    if st.sidebar.button("💾 Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # PRICES
    # -------------------------------------
    try:
        prices = crypto_live_prices() or {}
    except Exception:
        prices = {}

    if not prices:
        st.warning("⚠️ Using cached prices")

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():
        raw_price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        usd_price = safe_price(sym, raw_price)

        value_ghs = qty * usd_price * rate
        total_value += value_ghs

        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    st.subheader("📘 Crypto Assets")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # SAVE (FIXED)
    # -------------------------------------
    if total_value > 0:
        autosave_portfolio_value(user_id, total_value, "crypto")

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
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h[h["value_ghs"] > 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h["timestamp"], y=h["value_ghs"], mode="lines+markers"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Waiting for data...")

    # -------------------------------------
    # PnL CHART
    # -------------------------------------
    st.subheader("📊 All-Time PnL")

    pnl_df = build_pnl_history(history, invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pnl_df["timestamp"], y=pnl_df["pnl"], mode="lines+markers"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("PnL chart will appear soon.")

    # -------------------------------------
    # ALLOCATION PIE CHART
    # -------------------------------------
    st.markdown("---")
    st.subheader("🍕 Portfolio Allocation")

    pie_df = df.copy()
    pie_df = pie_df[pie_df["Value (GHS)"] > 0]

    if not pie_df.empty:

        pie = alt.Chart(pie_df).mark_arc(innerRadius=40).encode(
            theta=alt.Theta(field="Value (GHS)", type="quantitative"),
            color=alt.Color(field="Asset", type="nominal"),
            tooltip=["Asset", "Value (GHS)"]
        )

        st.altair_chart(pie, use_container_width=True)

    else:
        st.info("Allocation chart will appear once assets have value.")
