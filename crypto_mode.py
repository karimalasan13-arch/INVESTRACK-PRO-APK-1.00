import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from db import (
    load_setting, save_setting,
    load_holdings, save_holdings,
    autosave_portfolio_value, load_portfolio_history
)

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
}

def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"

def crypto_app():
    st.title("💰 Crypto Portfolio Tracker")

    # ----- Load persisted state -----
    rate = float(load_setting("crypto_rate", 14.5))
    invested = float(load_setting("crypto_invested", 0))
    holdings = load_holdings("crypto_holdings")

    for s in API_MAP:
        holdings.setdefault(s, 0.0)

    # ----- Sidebar -----
    st.sidebar.header("Crypto Settings")
    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting("crypto_rate", rate)
        save_setting("crypto_invested", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for s in API_MAP:
        holdings[s] = st.sidebar.number_input(
            f"{s} qty", value=float(holdings[s]), step=0.0001
        )

    if st.sidebar.button("Save Holdings"):
        save_holdings("crypto_holdings", holdings)
        st.sidebar.success("Holdings saved")

    # ----- Prices -----
    prices = crypto_live_prices()

    rows = []
    total_value = 0.0
    for s, q in holdings.items():
        p = prices.get(s, 0)
        v_usd = p * q
        v_ghs = v_usd * rate
        total_value += v_ghs
        rows.append([s, q, p, v_usd, v_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price USD", "Value USD", "Value GHS"])
    st.dataframe(df, use_container_width=True)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    autosave_portfolio_value(total_value)

    # ----- Summary -----
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    # ----- Charts -----
    hist = load_portfolio_history()
    if len(hist) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[h["timestamp"] for h in hist],
            y=[h["value_ghs"] for h in hist],
            mode="lines+markers"
        ))
        fig.update_layout(dragmode="zoom")
        st.plotly_chart(fig, use_container_width=True)

    # ----- Allocation -----
    df_pie = df[df["Value GHS"] > 0][["Asset", "Value GHS"]]
    if not df_pie.empty:
        pie = alt.Chart(df_pie).mark_arc().encode(
            theta="Value GHS:Q",
            color="Asset:N"
        )
        st.altair_chart(pie, use_container_width=True)
