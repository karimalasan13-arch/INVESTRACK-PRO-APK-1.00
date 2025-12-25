import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase
from user_session import get_user_id   # 🔑 REQUIRED


# -----------------------------------------
# CONFIG
# -----------------------------------------
API_MAP = {
    "USDT": "tether",
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
def load_setting(user_id: str, key: str, default):
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


def save_setting(user_id: str, key: str, value):
    supabase.table("user_settings").upsert({
        "user_id": user_id,
        key: value
    }).execute()


def load_crypto_holdings(user_id: str):
    holdings = {sym: 0.0 for sym in API_MAP}
    try:
        res = supabase.table("crypto_holdings") \
            .select("symbol,quantity") \
            .eq("user_id", user_id) \
            .execute()

        for row in res.data:
            holdings[row["symbol"]] = float(row["quantity"])
    except:
        pass

    return holdings


def save_crypto_holdings(user_id: str, holdings: dict):
    rows = [
        {
            "user_id": user_id,
            "symbol": sym,
            "quantity": qty
        }
        for sym, qty in holdings.items()
    ]

    supabase.table("crypto_holdings").upsert(
        rows,
        on_conflict="user_id,symbol"
    ).execute()


def load_portfolio_history(user_id: str):
    try:
        res = supabase.table("portfolio_history") \
            .select("timestamp,value_ghs") \
            .eq("user_id", user_id) \
            .order("timestamp") \
            .execute()

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
    user_id = get_user_id()   # 🔑 SINGLE SOURCE OF TRUTH
    st.title("💰 Crypto Portfolio Tracker")

    # -------------------------------------
    # LOAD USER DATA
    # -------------------------------------
    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
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
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Crypto Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            f"{sym} quantity",
            value=float(holdings.get(sym, 0)),
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
        usd_price = prices.get(sym, 0)
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

    # -------------------------------------
    # PnL
    # -------------------------------------
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    # -------------------------------------
    # 8-HOUR SNAPSHOT SAVE (SAFE)
    # -------------------------------------
    from auth import get_current_user

user = get_current_user()
if user:
    autosave_portfolio_value(user["id"], total_value_ghs)

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
        dates = [h["timestamp"] for h in history]
        values = [h["value_ghs"] for h in history]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
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

    # -------------------------------------
    # ALLOCATION PIE
    # -------------------------------------
    st.markdown("---")
    st.subheader("🍕 Allocation (by Value)")

    df_pie = df[df["Value (GHS)"] > 0][["Asset", "Value (GHS)"]]
    if not df_pie.empty:
        pie = alt.Chart(df_pie).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
            tooltip=["Asset", "Value (GHS)"]
        )
        st.altair_chart(pie, use_container_width=True)
