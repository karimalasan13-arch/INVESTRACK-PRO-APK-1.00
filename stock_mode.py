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
        return float(res.data["value"])
    except:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert({
        "user_id": user_id,
        "key": key,
        "value": value
    }, on_conflict="user_id,key").execute()


def load_stock_holdings(user_id):
    holdings = {sym: 0.0 for sym in STOCK_MAP}
    res = supabase.table("stock_holdings") \
        .select("symbol,quantity") \
        .eq("user_id", user_id) \
        .execute()

    for row in res.data:
        holdings[row["symbol"]] = float(row["quantity"])

    return holdings


def save_stock_holdings(user_id, holdings):
    rows = [
        {
            "user_id": user_id,
            "symbol": sym,
            "quantity": qty
        }
        for sym, qty in holdings.items()
    ]

    supabase.table("stock_holdings") \
        .upsert(rows, on_conflict="user_id,symbol") \
        .execute()


def load_portfolio_history(user_id):
    res = supabase.table("portfolio_history") \
        .select("timestamp,value_ghs") \
        .eq("user_id", user_id) \
        .order("timestamp") \
        .execute()
    return res.data or []

# -----------------------------------------
# FORMATTERS
# -----------------------------------------
def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"

# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():
    user_id = st.session_state.user.id
    st.title("📊 Stock Portfolio Tracker")

    # -------------------------------------
    # LOAD DATA
    # -------------------------------------
    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    assets = load_stock_holdings(user_id)

    # -------------------------------------
    # SIDEBAR
    # -------------------------------------
    st.sidebar.header("Stock Settings")

    rate = st.sidebar.number_input(
        "Stock Exchange Rate (USD → GHS)", value=rate, step=0.1
    )

    invested = st.sidebar.number_input(
        "Total Stock Investment (GHS)", value=invested, step=10.0
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
    # LIVE PRICES
    # -------------------------------------
    prices = stock_live_prices(
        symbols=[s for s, q in assets.items() if q > 0] or list(STOCK_MAP)
    )

    rows = []
    total_value_ghs = 0.0

    for sym, qty in assets.items():
        usd_price = prices.get(sym, 0.0)
        value_ghs = usd_price * qty * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_ghs / rate, value_ghs])

    df = pd.DataFrame(
        rows,
        columns=["Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"]
    )

    st.subheader("📘 Stock Asset Breakdown")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # SNAPSHOT SAVE (8 HOUR)
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value_ghs)
    history = load_portfolio_history(user_id)

    # -------------------------------------
    # SUMMARY
    # -------------------------------------
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value_ghs))
    c2.metric("Invested", fmt(invested))
    c3.metric("PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------
    # LINE CHART
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:
        fig = go.Figure(go.Scatter(
            x=[h["timestamp"] for h in history],
            y=[h["value_ghs"] for h in history],
            mode="lines+markers"
        ))
        fig.update_layout(
            dragmode="zoom",
            hovermode="x unified",
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Portfolio history will appear as data is collected.")

    # -------------------------------------
    # ALLOCATION PIE
    # -------------------------------------
    st.markdown("---")
    st.subheader("🍕 Allocation")

    df_pie = df[df["Value (GHS)"] > 0][["Asset", "Value (GHS)"]]
    if not df_pie.empty:
        st.altair_chart(
            alt.Chart(df_pie).mark_arc().encode(
                theta="Value (GHS):Q",
                color="Asset:N",
                tooltip=["Asset", "Value (GHS)"]
            ),
            use_container_width=True
        )
