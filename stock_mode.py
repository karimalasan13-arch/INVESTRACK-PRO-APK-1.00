import streamlit as st
import pandas as pd
import altair as alt
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


def session_cache(key, loader):
    if key not in st.session_state:
        st.session_state[key] = loader()
    return st.session_state[key]


def load_setting(user_id, key, default):
    try:
        res = supabase.table("user_settings").select("value").eq("user_id", user_id).eq("key", key).single().execute()
        return float(res.data["value"]) if res.data else default
    except Exception:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": value},
        on_conflict="user_id,key",
    ).execute()


def load_holdings(user_id):
    h = {s: 0.0 for s in STOCK_MAP}
    try:
        res = supabase.table("stock_holdings").select("symbol,quantity").eq("user_id", user_id).execute()
        for r in res.data or []:
            h[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return h


def save_holdings(user_id, h):
    supabase.table("stock_holdings").upsert(
        [{"user_id": user_id, "symbol": s, "quantity": q} for s, q in h.items()],
        on_conflict="user_id,symbol",
    ).execute()


def load_history(user_id):
    try:
        res = supabase.table("portfolio_history").select("timestamp,value_ghs").eq("user_id", user_id).order("timestamp").execute()
        return res.data or []
    except Exception:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


def stock_app():
    user_id = st.session_state.user.id
    st.title("📊 Stock Portfolio Tracker")

    rate = session_cache("stock_rate", lambda: load_setting(user_id, "stock_rate", 14.5))
    invested = session_cache("stock_inv", lambda: load_setting(user_id, "stock_investment", 0.0))
    holdings = session_cache("stock_holdings", lambda: load_holdings(user_id))

    st.sidebar.header("Stock Settings")
    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Investment (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.session_state.pop("stock_rate", None)
        st.session_state.pop("stock_inv", None)
        st.rerun()

    st.sidebar.markdown("---")
    for s in STOCK_MAP:
        holdings[s] = st.sidebar.number_input(s, value=float(holdings[s]), step=1.0)

    if st.sidebar.button("Save Holdings"):
        save_holdings(user_id, holdings)
        st.session_state.pop("stock_holdings", None)
        st.rerun()

    prices = stock_live_prices(symbols=list(STOCK_MAP.keys()))

    rows, total = [], 0.0
    for s, q in holdings.items():
        usd = prices.get(s, 0.0)
        v = usd * q * rate
        total += v
        rows.append([s, q, usd, v])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    pnl = total - invested
    autosave_portfolio_value(user_id, total)

    hist = session_cache("stock_hist", lambda: load_history(user_id))

    c1, c2, c3 = st.columns(3)
    c1.metric("Total", fmt(total))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct((pnl / invested * 100) if invested else 0))

    if len(hist) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[h["timestamp"] for h in hist],
            y=[h["value_ghs"] for h in hist],
            mode="lines+markers",
        ))
        st.plotly_chart(fig, use_container_width=True)

    pie_df = df[df["Value (GHS)"] > 0][["Asset", "Value (GHS)"]]
    if not pie_df.empty:
        st.altair_chart(
            alt.Chart(pie_df).mark_arc().encode(
                theta="Value (GHS):Q",
                color="Asset:N",
                tooltip=["Asset", "Value (GHS)"],
            ),
            use_container_width=True,
        )
