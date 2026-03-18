import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase


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
# SETTINGS HELPERS
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
    except:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
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
            supabase.table("crypto_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])
    except:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": k, "quantity": float(v)}
        for k, v in holdings.items()
    ]
    supabase.table("crypto_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


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
# HISTORY
# -----------------------------------------
def load_portfolio_history(user_id):
    try:
        res = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "crypto")
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except:
        return []


# -----------------------------------------
# MAIN
# -----------------------------------------
def crypto_app():

    st.title("💰 Crypto Portfolio Tracker")

    user_id = st.session_state.user_id

    # SETTINGS
    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)

    holdings = load_crypto_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("⚙️ Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Investment (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Crypto Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")

    st.sidebar.subheader("🪙 Crypto Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            key=f"c_{sym}"
        )

    if st.sidebar.button("📥 Save Crypto Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Saved")

    # -------------------------------------
    # PRICES
    # -------------------------------------
    prices = crypto_live_prices() or {}

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():
        raw_price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        usd_price = safe_price(sym, raw_price)

        value_ghs = qty * usd_price * rate
        total_value += value_ghs

        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    # PROTECT VALUE
    if "last_valid_crypto_total" not in st.session_state:
        st.session_state.last_valid_crypto_total = total_value

    if total_value <= 0:
        total_value = st.session_state.last_valid_crypto_total
    else:
        st.session_state.last_valid_crypto_total = total_value

    autosave_portfolio_value(user_id, total_value, "crypto")

    history = load_portfolio_history(user_id)

    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h[h["value_ghs"] > 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h["timestamp"], y=h["value_ghs"], mode="lines"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Waiting for data...")
