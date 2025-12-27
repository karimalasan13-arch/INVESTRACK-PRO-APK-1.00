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
    "USDT": "tether"
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LTC": "litecoin",
}


# -----------------------------------------
# SUPABASE HELPERS (USER-SAFE)
# -----------------------------------------
def load_settings(user_id):
    try:
        res = (
            supabase.table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if res.data:
            return res.data
    except:
        pass

    return {
        "crypto_rate": 14.5,
        "crypto_investment": 0.0,
    }


def save_settings(user_id, rate, invested):
    supabase.table("user_settings").upsert(
        {
            "user_id": user_id,
            "crypto_rate": rate,
            "crypto_investment": invested,
        }
    ).execute()


def load_crypto_holdings(user_id):
    holdings = {sym: 0.0 for sym in API_MAP}
    try:
        res = (
            supabase.table("crypto_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for row in res.data:
            holdings[row["symbol"]] = float(row["quantity"])
    except:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": sym, "quantity": qty}
        for sym, qty in holdings.items()
    ]
    supabase.table("crypto_holdings").upsert(
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
    except:
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
    user_id = st.session_state.user.id
    st.title("💰 Crypto Portfolio Tracker")

    settings = load_settings(user_id)
    rate = float(settings.get("crypto_rate", 14.5))
    invested = float(settings.get("crypto_investment", 0.0))
    holdings = load_crypto_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("Crypto Settings")

    rate = st.sidebar.number_input(
        "Crypto Exchange Rate (USD → GHS)", value=rate, step=0.1
    )
    invested = st.sidebar.number_input(
        "Total Crypto Investment (GHS)", value=invested, step=10.0
    )

    if st.sidebar.button("Save Settings"):
        save_settings(user_id, rate, invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Crypto Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            f"{sym} quantity",
            value=float(holdings.get(sym, 0.0)),
            step=0.0001,
            key=f"hold_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES
    # -------------------------------------
    prices = crypto_live_prices()

    rows = []
    total_value_ghs = 0.0

    for sym, qty in holdings.items():
        usd_price = prices.get(sym, 0.0)
        value_usd = usd_price * qty
        value_ghs = value_usd * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_usd, value_ghs])

    df = pd.DataFrame(
        rows,
        columns=["Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"]
    )

    st.subheader("📘 Crypto Asset Breakdown")
    st.dataframe(df, use_container_width=True)

    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    autosave_portfolio_value(user_id, total_value_ghs)
    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value (GHS)", fmt(total_value_ghs))
    c2.metric("Total Invested (GHS)", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[h["timestamp"] for h in history],
            y=[h["value_ghs"] for h in history],
            mode="lines+markers"
        ))

        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="Portfolio Value (GHS)",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portfolio history will appear as data is collected.")
