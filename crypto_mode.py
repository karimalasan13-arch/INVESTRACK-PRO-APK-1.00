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
CRYPTO_ASSETS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "LTC", "USDT"]


# -----------------------------------------
# SUPABASE HELPERS
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
        if res.data:
            return float(res.data["value"])
    except Exception:
        pass
    return default


def save_setting(user_id: str, key: str, value: float):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": value},
        on_conflict="user_id,key",
    ).execute()


def load_crypto_holdings(user_id: str):
    holdings = {a: 0.0 for a in CRYPTO_ASSETS}
    try:
        res = (
            supabase.table("crypto_holdings")
            .select("symbol, quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for r in res.data:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_crypto_holdings(user_id: str, holdings: dict):
    rows = [
        {"user_id": user_id, "symbol": k, "quantity": float(v)}
        for k, v in holdings.items()
    ]
    supabase.table("crypto_holdings").upsert(
        rows,
        on_conflict="user_id,symbol",
    ).execute()


def load_crypto_history(user_id: str):
    try:
        res = (
            supabase.table("crypto_history")
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
    user_id = st.session_state.user_id
    st.title("💰 Crypto Portfolio Tracker")

    # ---------------- LOAD DATA ----------------
    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # ---------------- SIDEBAR ----------------
    st.sidebar.header("Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS Rate", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Crypto Investment (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for a in CRYPTO_ASSETS:
        holdings[a] = st.sidebar.number_input(
            f"{a} Quantity",
            value=float(holdings[a]),
            step=0.0001,
            key=f"crypto_{a}",
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # ---------------- PRICES ----------------
    prices = crypto_live_prices()
    rows, total_value_ghs = [], 0.0

    for sym, qty in holdings.items():
        usd_price = 1.0 if sym == "USDT" else float(prices.get(sym, 0.0))
        value_usd = usd_price * qty
        value_ghs = value_usd * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "USD Price", "Value (GHS)"])
    st.subheader("📘 Crypto Breakdown")
    st.dataframe(df, use_container_width=True)

    # ---------------- PNL ----------------
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    autosave_portfolio_value(user_id, total_value_ghs)
    history = load_crypto_history(user_id)

    # ---------------- DASHBOARD ----------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value_ghs))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    st.markdown("---")
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        df_h = pd.DataFrame(history)
        df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h["timestamp"],
            y=df_h["value_ghs"],
            mode="lines+markers",
        ))

        fig.update_layout(height=350, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("📆 MTD & YTD Performance")

        now = datetime.utcnow()
        mtd_df = df_h[df_h["timestamp"].dt.month == now.month]
        ytd_df = df_h[df_h["timestamp"].dt.year == now.year]

        mtd_start = mtd_df.iloc[0]["value_ghs"] if not mtd_df.empty else total_value_ghs
        ytd_start = ytd_df.iloc[0]["value_ghs"] if not ytd_df.empty else total_value_ghs

        mtd_pnl = total_value_ghs - mtd_start
        ytd_pnl = total_value_ghs - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0

        c1, c2 = st.columns(2)
        c1.metric("MTD", fmt(mtd_pnl), pct(mtd_pct))
        c2.metric("YTD", fmt(ytd_pnl), pct(ytd_pct))

    else:
        st.info("📊 Portfolio history will appear after multiple snapshots are saved.")

        st.markdown("---")
        st.subheader("🍕 Allocation (by Value)")

        df_pie = df.copy()
        df_pie["Value (GHS)"] = pd.to_numeric(df_pie["Value (GHS)"], errors="coerce").fillna(0)

        df_pie = df_pie[df_pie["Value (GHS)"] > 0]

        if df_pie.empty:
        st.info("Allocation will appear once assets have non-zero value.")
        else:
            pie = alt.Chart(df_pie).mark_arc().encode(
                theta=alt.Theta(field="Value (GHS)", type="quantitative"),
                color=alt.Color(field="Asset", type="nominal"),
                tooltip=["Asset", "Value (GHS)"]
            )
            st.altair_chart(pie, use_container_width=True)

