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
# SUPABASE HELPERS
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
        if res.data and "value" in res.data:
            return float(res.data["value"])
    except Exception:
        pass
    return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
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
        {"user_id": user_id, "symbol": k, "quantity": float(v)}
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


# -----------------------------------------
# FORMATTERS
# -----------------------------------------
def fmt(v): 
    return f"GHS {v:,.2f}"

def pct(v): 
    return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def crypto_app():
    st.title("💰 Crypto Portfolio Tracker")
    user_id = st.session_state.user_id

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

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input(
        "Total Invested (GHS)", value=float(invested), step=10.0
    )

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    # -------------------------------------
    # SIDEBAR — HOLDINGS
    # -------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("Crypto Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            step=0.0001,
            key=f"c_{sym}",
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES
    # -------------------------------------
    prices = crypto_live_prices()

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():
        usd_price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        value_ghs = qty * usd_price * rate
        total_value += value_ghs
        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(
        rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"]
    )

    st.subheader("📘 Crypto Assets")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # PnL
    # -------------------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # -------------------------------------
    # AUTOSAVE + HISTORY
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value)
    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=h["timestamp"],
                y=h["value_ghs"],
                mode="lines+markers",
            )
        )
        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="Value (GHS)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portfolio history will appear after multiple snapshots.")

    # -------------------------------------
    # MTD / YTD PERFORMANCE ✅ FIX
    # -------------------------------------
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    if history:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h.sort_values("timestamp")

        now = datetime.utcnow()

        mtd_df = h[h["timestamp"].dt.month == now.month]
        ytd_df = h[h["timestamp"].dt.year == now.year]

        mtd_start = mtd_df.iloc[0]["value_ghs"] if not mtd_df.empty else total_value
        ytd_start = ytd_df.iloc[0]["value_ghs"] if not ytd_df.empty else total_value

        mtd_pnl = total_value - mtd_start
        ytd_pnl = total_value - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0.0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0.0
    else:
        mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0.0

    c1, c2 = st.columns(2)
    c1.metric("MTD", fmt(mtd_pnl), pct(mtd_pct))
    c2.metric("YTD", fmt(ytd_pnl), pct(ytd_pct))

    # -------------------------------------
    # ALLOCATION PIE
    # -------------------------------------
    st.markdown("---")
    st.subheader("🍕 Allocation")

    pie_df = df.copy()
    pie_df["Value (GHS)"] = pd.to_numeric(
        pie_df["Value (GHS)"], errors="coerce"
    ).fillna(0)
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
