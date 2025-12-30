import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices  # 🔒 cached (3.2.1)
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
        on_conflict="user_id,key"
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
        rows,
        on_conflict="user_id,symbol"
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

    # -------------------------------------
    # LOAD USER DATA
    # -------------------------------------
    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # -------------------------------------
    # SIDEBAR — SETTINGS
    # -------------------------------------
    st.sidebar.header("Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS Rate", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Investment (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            step=0.0001,
            key=f"crypto_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES (CACHED)
    # -------------------------------------
    prices = crypto_live_prices()

    rows = []
    total_value_ghs = 0.0

    for sym, qty in holdings.items():
        usd_price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        value_ghs = usd_price * qty * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # AUTOSAVE (8H)
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value_ghs)
    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value_ghs))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])
        st.plotly_chart(
            go.Figure(go.Scatter(
                x=df_h["timestamp"],
                y=df_h["value_ghs"],
                mode="lines+markers"
            )),
            use_container_width=True
        )

    # -------------------------------------
    # MTD / YTD
    # -------------------------------------
    if history:
        now = datetime.utcnow()
        mtd = df_h[df_h["timestamp"].dt.month == now.month]
        ytd = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total_value_ghs
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total_value_ghs

        c1, c2 = st.columns(2)
        c1.metric("MTD", fmt(total_value_ghs - mtd_start),
                  pct((total_value_ghs - mtd_start) / mtd_start * 100 if mtd_start else 0))
        c2.metric("YTD", fmt(total_value_ghs - ytd_start),
                  pct((total_value_ghs - ytd_start) / ytd_start * 100 if ytd_start else 0))

    # -------------------------------------
    # ALLOCATION PIE
    # -------------------------------------
    df_pie = df[df["Value (GHS)"] > 0]
    if not df_pie.empty:
        st.altair_chart(
            alt.Chart(df_pie).mark_arc().encode(
                theta="Value (GHS):Q",
                color="Asset:N"
            ),
            use_container_width=True
        )
