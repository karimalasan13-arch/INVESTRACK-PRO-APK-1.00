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


# ---------------- SETTINGS ----------------
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


# ---------------- HOLDINGS ----------------
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
        {"user_id": user_id, "symbol": s, "quantity": q}
        for s, q in holdings.items()
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


# ---------------- FORMAT ----------------
def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# ---------------- MAIN APP ----------------
def crypto_app():
    user_id = st.session_state.user.id
    st.title("💰 Crypto Portfolio")

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    st.sidebar.header("Crypto Settings")
    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Invested (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            f"{sym} qty", holdings[sym], step=0.0001, key=f"c_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Saved")

    prices = crypto_live_prices()
    if not isinstance(prices, dict):
        prices = {}
    prices.setdefault("USDT", 1.0)

    rows, total = [], 0.0
    for s, q in holdings.items():
        p = prices.get(s, 0.0)
        v_usd = p * q
        v_ghs = v_usd * rate
        total += v_ghs
        rows.append([s, q, p, v_usd, v_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "USD", "USD Value", "GHS Value"])
    st.dataframe(df, use_container_width=True)

    autosave_portfolio_value(user_id, total)
    history = load_portfolio_history(user_id)

    pnl = total - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total", fmt(total))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h["timestamp"],
            y=df_h["value_ghs"],
            mode="lines+markers"
        ))
        fig.update_layout(dragmode="zoom", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        now = datetime.utcnow()
        mtd = df_h[df_h["timestamp"].dt.month == now.month]
        ytd = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total

        mtd_pnl = total - mtd_start
        ytd_pnl = total - ytd_start

        c1, c2 = st.columns(2)
        c1.metric("MTD", fmt(mtd_pnl), pct(mtd_pnl / mtd_start * 100 if mtd_start else 0))
        c2.metric("YTD", fmt(ytd_pnl), pct(ytd_pnl / ytd_start * 100 if ytd_start else 0))

    pie_df = df[df["GHS Value"] > 0][["Asset", "GHS Value"]]
    if not pie_df.empty:
        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="GHS Value:Q", color="Asset:N"
        )
        st.altair_chart(pie, use_container_width=True)
