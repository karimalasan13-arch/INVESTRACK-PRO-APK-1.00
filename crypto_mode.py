import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase


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


def crypto_app():
    user_id = st.session_state.user_id
    st.title("💰 Crypto Portfolio Tracker")

    # -----------------------------
    # LOAD SETTINGS
    # -----------------------------
    rate = 14.5
    invested = 0.0

    # -----------------------------
    # PRICE LOADING (SKELETON)
    # -----------------------------
    with st.spinner("Fetching live crypto prices…"):
        prices, api_ok = crypto_live_prices()

    if not api_ok:
        st.warning("⚠️ Live prices unavailable. Showing last known values.")

    # -----------------------------
    # HOLDINGS
    # -----------------------------
    holdings = {k: 0.0 for k in API_MAP}
    rows, total_value = [], 0.0

    for sym, qty in holdings.items():
        usd = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        ghs = usd * qty * rate
        total_value += ghs
        rows.append([sym, qty, usd, ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price USD", "Value GHS"])
    st.dataframe(df, use_container_width=True)

    # -----------------------------
    # AUTOSAVE (SAFE)
    # -----------------------------
    autosave_portfolio_value(user_id, total_value)

    # -----------------------------
    # HISTORY
    # -----------------------------
    history = []
    try:
        history = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .order("timestamp")
            .execute()
            .data
        )
    except Exception:
        pass

    # -----------------------------
    # SUMMARY
    # -----------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", f"GHS {total_value:,.2f}")
    c2.metric("Invested", f"GHS {invested:,.2f}")
    c3.metric("PnL", f"GHS {pnl:,.2f}", f"{pnl_pct:.2f}%")

    # -----------------------------
    # LINE CHART (SAFE)
    # -----------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if history and len(history) >= 2:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

        fig = go.Figure(
            go.Scatter(
                x=df_h["timestamp"],
                y=df_h["value_ghs"],
                mode="lines+markers",
            )
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📊 Portfolio history will appear after multiple saves.")

    # -----------------------------
    # MTD / YTD (SAFE)
    # -----------------------------
    now = datetime.utcnow()

    if history:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

        mtd_df = df_h[df_h["timestamp"].dt.month == now.month]
        ytd_df = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_start = mtd_df.iloc[0]["value_ghs"] if not mtd_df.empty else total_value
        ytd_start = ytd_df.iloc[0]["value_ghs"] if not ytd_df.empty else total_value

        mtd_pnl = total_value - mtd_start
        ytd_pnl = total_value - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0
    else:
        mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0.0

    c1, c2 = st.columns(2)
    c1.metric("MTD", f"GHS {mtd_pnl:,.2f}", f"{mtd_pct:.2f}%")
    c2.metric("YTD", f"GHS {ytd_pnl:,.2f}", f"{ytd_pct:.2f}%")
