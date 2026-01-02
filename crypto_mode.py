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
CRYPTO_MAP = {
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
def load_setting(user_id: str, key: str, default: float):
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


def save_setting(user_id: str, key: str, value: float):
    supabase.table("user_settings").upsert(
        {
            "user_id": user_id,
            "key": key,
            "value": float(value),
        },
        on_conflict="user_id,key",
    ).execute()


def load_holdings(user_id: str):
    holdings = {sym: 0.0 for sym in CRYPTO_MAP}
    try:
        res = (
            supabase.table("crypto_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for row in res.data or []:
            holdings[row["symbol"]] = float(row["quantity"])
    except Exception:
        pass
    return holdings


def save_holdings(user_id: str, holdings: dict):
    rows = [
        {
            "user_id": user_id,
            "symbol": sym,
            "quantity": float(qty),
        }
        for sym, qty in holdings.items()
    ]

    supabase.table("crypto_holdings").upsert(
        rows,
        on_conflict="user_id,symbol",
    ).execute()


def load_portfolio_history(user_id: str):
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
    user_id = st.session_state.user_id
    st.title("💰 Crypto Portfolio Tracker")

    # -------------------------------------
    # LOAD DATA (NO SIDE EFFECTS)
    # -------------------------------------
    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_holdings(user_id)

    # -------------------------------------
    # SIDEBAR (MUST RENDER FIRST)
    # -------------------------------------
    with st.sidebar:
        st.header("Crypto Settings")

        rate = st.number_input(
            "USD → GHS Rate",
            value=rate,
            step=0.1,
            key="crypto_rate_input",
        )

        invested = st.number_input(
            "Total Invested (GHS)",
            value=invested,
            step=10.0,
            key="crypto_invested_input",
        )

        if st.button("Save Settings", key="save_crypto_settings"):
            save_setting(user_id, "crypto_rate", rate)
            save_setting(user_id, "crypto_investment", invested)
            st.success("Settings saved")

        st.markdown("---")
        st.subheader("Crypto Holdings")

        for sym in CRYPTO_MAP:
            holdings[sym] = st.number_input(
                f"{sym} quantity",
                value=float(holdings[sym]),
                step=0.0001,
                key=f"crypto_qty_{sym}",
            )

        if st.button("Save Holdings", key="save_crypto_holdings"):
            save_holdings(user_id, holdings)
            st.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES
    # -------------------------------------
    prices = crypto_live_prices()

    rows = []
    total_value_ghs = 0.0

    for sym, qty in holdings.items():
        usd_price = 1.0 if sym == "USDT" else prices.get(sym, 0.0)
        value_usd = usd_price * qty
        value_ghs = value_usd * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_usd, value_ghs])

    df = pd.DataFrame(
        rows,
        columns=["Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"],
    )

    st.subheader("📘 Crypto Asset Breakdown")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # PnL
    # -------------------------------------
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # -------------------------------------
    # AUTOSAVE SNAPSHOT
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value_ghs)
    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value_ghs))
    c2.metric("Total Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_h["timestamp"],
                y=df_h["value_ghs"],
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
        st.info("Portfolio history will appear as data is collected.")

    # -------------------------------------
    # MTD / YTD
    # -------------------------------------
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    if history:
        now = datetime.utcnow()
        mtd_df = df_h[df_h["timestamp"].dt.month == now.month]
        ytd_df = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_start = mtd_df.iloc[0]["value_ghs"] if not mtd_df.empty else total_value_ghs
        ytd_start = ytd_df.iloc[0]["value_ghs"] if not ytd_df.empty else total_value_ghs

        mtd_pnl = total_value_ghs - mtd_start
        ytd_pnl = total_value_ghs - ytd_start

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
    st.subheader("🍕 Allocation (by Value)")

    df_pie = df[df["Value (GHS)"] > 0][["Asset", "Value (GHS)"]]

    if not df_pie.empty:
        pie = alt.Chart(df_pie).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
            tooltip=["Asset", "Value (GHS)"],
        )
        st.altair_chart(pie, use_container_width=True)
    else:
        st.info("No allocation to display yet.")
