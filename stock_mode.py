import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

st.write("USER ID:", user_id)
from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import supabase
from user_session import get_user_id   # 🔑 REQUIRED


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
# SUPABASE HELPERS (USER SAFE)
# -----------------------------------------
def load_setting(user_id, key, default):
    try:
        res = supabase.table("user_settings") \
            .select("value") \
            .eq("user_id", user_id) \
            .eq("key", key) \
            .single() \
            .execute()

        if res.data:
            return float(res.data["value"])
    except:
        pass

    return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert({
        "user_id": user_id,
        "key": key,
        "value": value
    }).execute()


def load_stock_holdings(user_id: str):
    holdings = {sym: 0.0 for sym in STOCK_MAP}
    try:
        res = supabase.table("stock_holdings") \
            .select("symbol,quantity") \
            .eq("user_id", user_id) \
            .execute()

        for row in res.data:
            holdings[row["symbol"]] = float(row["quantity"])
    except:
        pass

    return holdings


def save_stock_holdings(user_id: str, holdings: dict):
    rows = [
        {
            "user_id": user_id,
            "symbol": sym,
            "quantity": qty
        }
        for sym, qty in holdings.items()
    ]

    supabase.table("stock_holdings").upsert(
        rows,
        on_conflict="user_id,symbol"
    ).execute()


def load_portfolio_history(user_id: str):
    try:
        res = supabase.table("portfolio_history") \
            .select("timestamp,value_ghs") \
            .eq("user_id", user_id) \
            .order("timestamp") \
            .execute()

        return res.data or []
    except:
        return []


# -----------------------------------------
# FORMATTERS
# -----------------------------------------
def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():
    user_id = get_user_id()   # 🔑 SINGLE SOURCE OF TRUTH
    st.title("📊 Stock Portfolio Tracker")

    # -------------------------------------
    # LOAD USER DATA
    # -------------------------------------
    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    assets = load_stock_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("Stock Settings")

    rate = st.sidebar.number_input(
        "Stock Exchange Rate (USD → GHS)",
        value=rate,
        step=0.1
    )

    invested = st.sidebar.number_input(
        "Total Stock Investment (GHS)",
        value=invested,
        step=10.0
    )

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Stock Holdings")

    for sym in STOCK_MAP:
        assets[sym] = st.sidebar.number_input(
            f"{sym} quantity",
            value=float(assets.get(sym, 0.0)),
            step=1.0,
            key=f"stk_{sym}"
        )

    if st.sidebar.button("Save Holdings"):
        save_stock_holdings(user_id, assets)
        st.sidebar.success("Holdings saved")

    # -------------------------------------
    # LIVE PRICES (USD)
    # -------------------------------------
    symbols_to_fetch = [s for s, q in assets.items() if q > 0] or list(STOCK_MAP.keys())
    prices = stock_live_prices(symbols=symbols_to_fetch)

    rows = []
    total_value_ghs = 0.0

    for sym, qty in assets.items():
        usd_price = prices.get(sym, 0.0)
        value_usd = usd_price * qty
        value_ghs = value_usd * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_usd, value_ghs])

    df = pd.DataFrame(
        rows,
        columns=["Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"]
    )

    st.subheader("📘 Stock Asset Breakdown")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # PnL
    # -------------------------------------
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # -------------------------------------
    # 8-HOUR SNAPSHOT SAVE (SAFE)
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value_ghs)

    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value (GHS)", fmt(total_value_ghs))
    c2.metric("Total Invested (GHS)", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        dates = [h["timestamp"] for h in history]
        values = [h["value_ghs"] for h in history]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            mode="lines+markers"
        ))

        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="Portfolio Value (GHS)",
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
        hist_df = pd.DataFrame(history)
        hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
        hist_df = hist_df.sort_values("timestamp")

        now = datetime.utcnow()

        month_df = hist_df[hist_df["timestamp"].dt.month == now.month]
        year_df = hist_df[hist_df["timestamp"].dt.year == now.year]

        mtd_start = month_df.iloc[0]["value_ghs"] if not month_df.empty else total_value_ghs
        ytd_start = year_df.iloc[0]["value_ghs"] if not year_df.empty else total_value_ghs

        mtd_pnl = total_value_ghs - mtd_start
        ytd_pnl = total_value_ghs - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0
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
            tooltip=["Asset", "Value (GHS)"]
        )
        st.altair_chart(pie, use_container_width=True)
