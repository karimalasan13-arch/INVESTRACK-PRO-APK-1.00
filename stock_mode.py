import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase


# -----------------------------------------
# CONFIG
# -----------------------------------------
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


# -----------------------------------------
# DB HELPERS (USER-SAFE)
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


def load_holdings(user_id):
    holdings = {k: 0.0 for k in STOCK_MAP}
    try:
        res = (
            supabase.table("stock_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": k, "quantity": v}
        for k, v in holdings.items()
    ]
    supabase.table("stock_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


def load_history(user_id):
    try:
        return (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .order("timestamp")
            .execute()
            .data
        )
    except Exception:
        return []


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():
    user_id = st.session_state.user_id
    st.title("📊 Stock Portfolio Tracker")

    # -------------------------------------
    # LOAD USER DATA
    # -------------------------------------
    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    holdings = load_holdings(user_id)

    # -------------------------------------
    # SIDEBAR — SETTINGS
    # -------------------------------------
    st.sidebar.header("Stock Settings")

    rate = st.sidebar.number_input(
        "USD → GHS Rate",
        value=rate,
        step=0.1,
    )

    invested = st.sidebar.number_input(
        "Total Invested (GHS)",
        value=invested,
        step=10.0,
    )

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in STOCK_MAP:
        holdings[sym] = st.sidebar.number_input(
            f"{sym} Qty",
            value=float(holdings[sym]),
            step=1.0,
            key=f"s_{sym}",
        )

    if st.sidebar.button("Save Holdings"):
        save_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES
    # -------------------------------------
    with st.spinner("Fetching prices…"):
        prices = stock_live_prices(list(STOCK_MAP.keys()))

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():
        usd = float(prices.get(sym, 0.0))
        ghs = usd * qty * rate
        total_value += ghs
        rows.append([sym, qty, usd, ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "USD", "GHS"])
    st.subheader("📘 Stock Breakdown")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # HISTORY SNAPSHOT
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value)
    history = load_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Value", f"GHS {total_value:,.2f}")
    c2.metric("Invested", f"GHS {invested:,.2f}")
    c3.metric("PnL", f"GHS {pnl:,.2f}", f"{pnl_pct:.2f}%")

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio History")

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
        st.info("Portfolio history will appear as data is collected.")

    # -------------------------------------
    # MTD / YTD PERFORMANCE
    # -------------------------------------
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    now = datetime.utcnow()

    if history:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        mtd = h[h["timestamp"].dt.month == now.month]
        ytd = h[h["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total_value
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total_value

        mtd_pnl = total_value - mtd_start
        ytd_pnl = total_value - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0.0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0.0
    else:
        mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0.0

    c1, c2 = st.columns(2)
    c1.metric("MTD", f"GHS {mtd_pnl:,.2f}", f"{mtd_pct:.2f}%")
    c2.metric("YTD", f"GHS {ytd_pnl:,.2f}", f"{ytd_pct:.2f}%")

    # -------------------------------------
    # ALLOCATION PIE
    # -------------------------------------
    st.markdown("---")
    st.subheader("🍕 Allocation")

    df_pie = df[df["GHS"] > 0][["Asset", "GHS"]]

    if not df_pie.empty:
        pie = alt.Chart(df_pie).mark_arc().encode(
            theta="GHS:Q",
            color="Asset:N",
            tooltip=["Asset", "GHS"],
        )
        st.altair_chart(pie, use_container_width=True)
    else:
        st.info("No allocation to display yet.")
