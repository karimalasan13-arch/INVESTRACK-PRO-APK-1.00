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
# PRICE MEMORY (ANTI-ZERO)
# -----------------------------------------
def safe_price(symbol, price):
    if "crypto_price_memory" not in st.session_state:
        st.session_state.crypto_price_memory = {}

    if price and price > 0:
        st.session_state.crypto_price_memory[symbol] = price
        return price

    return st.session_state.crypto_price_memory.get(symbol, 0)


# -----------------------------------------
# HISTORY LOADER (MODE SAFE)
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
    except Exception:
        return []


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def crypto_app():

    st.title("💰 Crypto Portfolio Tracker")

    user_id = st.session_state.user_id

    rate = 14.5
    invested = 0.0

    # -------------------------------------
    # LOAD HOLDINGS
    # -------------------------------------
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

    df = pd.DataFrame(
        rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"]
    )

    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # FINAL VALUE PROTECTION
    # -------------------------------------
    if "last_valid_crypto_total" not in st.session_state:
        st.session_state.last_valid_crypto_total = total_value

    if total_value <= 0:
        total_value = st.session_state.last_valid_crypto_total
    else:
        st.session_state.last_valid_crypto_total = total_value

    # -------------------------------------
    # SAVE (MODE SAFE)
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value, "crypto")

    history = load_portfolio_history(user_id)

    # -------------------------------------
    # CHART (CLEAN)
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:

        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        # Remove bad data
        h = h[h["value_ghs"] > 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines"
        ))

        fig.update_layout(height=350)

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Waiting for data...")
