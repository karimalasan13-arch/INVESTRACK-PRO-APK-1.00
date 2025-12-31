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


# -----------------------------------------
# SUPABASE HELPERS (USER-SCOPED)
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
        for r in res.data:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": s, "quantity": q}
        for s, q in holdings.items()
    ]
    supabase.table("crypto_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


@st.cache_data(ttl=60)
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


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def crypto_app():
    user_id = st.session_state.user_id
    st.title("💰 Crypto Portfolio Tracker")

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
    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            f"{sym} quantity",
            value=float(holdings[sym]),
            step=0.0001,
            key=f"crypto_{sym}",
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    prices = crypto_live_prices()

    rows, total = [], 0.0
    for sym, qty in holdings.items():
        usd = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        ghs = usd * qty * rate
        total += ghs
        rows.append([sym, qty, usd, usd * qty, ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value USD", "Value GHS"])
    st.dataframe(df, use_container_width=True)

    pnl = total - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    # Autosave (debounced)
    if not st.session_state.get("crypto_saved_today"):
        autosave_portfolio_value(user_id, total)
        st.session_state.crypto_saved_today = True

    history = load_portfolio_history(user_id)

    # Summary
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", f"GHS {total:,.2f}")
    c2.metric("Invested", f"GHS {invested:,.2f}")
    c3.metric("PnL", f"GHS {pnl:,.2f}", f"{pnl_pct:.2f}%")

    # Line Chart
    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        fig = go.Figure(go.Scatter(x=df_h["timestamp"], y=df_h["value_ghs"]))
        fig.update_layout(height=350, dragmode="zoom")
        st.plotly_chart(fig, use_container_width=True)

    # MTD / YTD
    if history:
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])
        now = datetime.utcnow()

        mtd = df_h[df_h["timestamp"].dt.month == now.month]
        ytd = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_pnl = total - mtd.iloc[0]["value_ghs"] if not mtd.empty else 0
        ytd_pnl = total - ytd.iloc[0]["value_ghs"] if not ytd.empty else 0

        st.markdown("---")
        c1, c2 = st.columns(2)
        c1.metric("MTD", f"GHS {mtd_pnl:,.2f}")
        c2.metric("YTD", f"GHS {ytd_pnl:,.2f}")

    # Allocation Pie
    pie_df = df[df["Value GHS"] > 0][["Asset", "Value GHS"]]
    if not pie_df.empty:
        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="Value GHS:Q", color="Asset:N"
        )
        st.altair_chart(pie, use_container_width=True)
