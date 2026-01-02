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
    except Exception:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": value},
        on_conflict="user_id,key",
    ).execute()


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
    except Exception:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": k, "quantity": v}
        for k, v in holdings.items()
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
    except Exception:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


def crypto_app():
    st.title("💰 Crypto Portfolio Tracker")
    user_id = st.session_state.user_id

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # Sidebar
    st.sidebar.header("Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym, value=float(holdings.get(sym, 0.0)), step=0.0001, key=f"c_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Saved")

    prices = crypto_live_prices()

    rows, total = [], 0.0
    for sym, qty in holdings.items():
        price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        value = qty * price * rate
        total += value
        rows.append([sym, qty, price, value])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    st.subheader("📘 Assets")
    st.dataframe(df, use_container_width=True)

    pnl = total - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    autosave_portfolio_value(user_id, total)
    history = load_portfolio_history(user_id)

    st.markdown("---")
    st.subheader("📈 Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    st.subheader("📈 Portfolio History")

    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h["timestamp"], y=h["value_ghs"], mode="lines+markers"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portfolio history will appear after multiple snapshots.")

    st.subheader("🍕 Allocation")

    pie_df = df.copy()
    pie_df["Value (GHS)"] = pd.to_numeric(pie_df["Value (GHS)"], errors="coerce").fillna(0)
    pie_df = pie_df[pie_df["Value (GHS)"] > 0]

    if pie_df.empty:
        st.info("Allocation will appear once assets have value.")
    else:
        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
            tooltip=["Asset", "Value (GHS)"],
        )
        st.altair_chart(pie, use_container_width=True)
