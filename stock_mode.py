import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase


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


def stock_app():
    user_id = st.session_state.user_id
    st.title("📊 Stock Portfolio Tracker")

    with st.spinner("Fetching stock prices…"):
        prices, api_ok = stock_live_prices(list(STOCK_MAP.keys()))

    if not api_ok:
        st.warning("⚠️ Live prices unavailable.")

    holdings = {k: 0.0 for k in STOCK_MAP}
    rows, total_value = [], 0.0
    rate, invested = 14.5, 0.0

    for sym, qty in holdings.items():
        usd = prices.get(sym, 0.0)
        ghs = usd * qty * rate
        total_value += ghs
        rows.append([sym, qty, usd, ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price USD", "Value GHS"])
    st.dataframe(df, use_container_width=True)

    autosave_portfolio_value(user_id, total_value)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", f"GHS {total_value:,.2f}")
    c2.metric("Invested", f"GHS {invested:,.2f}")
    c3.metric("PnL", f"GHS {pnl:,.2f}", f"{pnl_pct:.2f}%")
