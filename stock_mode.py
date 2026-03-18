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
# PRICE MEMORY (ANTI-ZERO)
# -----------------------------------------
def safe_price(symbol, price):

    if "stock_price_memory" not in st.session_state:
        st.session_state.stock_price_memory = {}

    if price and price > 0:
        st.session_state.stock_price_memory[symbol] = price
        return price

    return st.session_state.stock_price_memory.get(symbol, 0)


# -----------------------------------------
# LOAD HISTORY (MODE ISOLATED)
# -----------------------------------------
def load_portfolio_history(user_id):
    try:
        res = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "stocks")   # ✅ CRITICAL FIX
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"
    
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
    except:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
        on_conflict="user_id,key",
    ).execute()

# -----------------------------------------
# MAIN APP
# -----------------------------------------
def stock_app():

    st.title("📊 Stock Portfolio Tracker")

    user_id = st.session_state.user_id

    # -------------------------------------
    # LOAD SETTINGS
    # -------------------------------------
        rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)

    st.sidebar.header("⚙️ Stock Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Investment (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Stock Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Stock Holdings")

    # -------------------------------------
    # LOAD HOLDINGS
    # -------------------------------------
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
    except:
        pass

    # -------------------------------------
    # FETCH PRICES
    # -------------------------------------
    prices = stock_live_prices(list(STOCK_MAP.keys())) or {}

    if not prices:
        st.warning("⚠️ Live stock prices unavailable. Using last known prices.")

    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():

        raw_price = prices.get(sym, 0.0)
        usd_price = safe_price(sym, raw_price)

        value_ghs = usd_price * qty * rate
        total_value += value_ghs

        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(
        rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"]
    )

    st.subheader("📘 Stock Assets")
    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # FINAL VALUE PROTECTION (CRITICAL)
    # -------------------------------------
    if "last_valid_stock_total" not in st.session_state:
        st.session_state.last_valid_stock_total = total_value

    if total_value <= 0:
        total_value = st.session_state.last_valid_stock_total
    else:
        st.session_state.last_valid_stock_total = total_value

    # -------------------------------------
    # SAVE (MODE SAFE)
    # -------------------------------------
    autosave_portfolio_value(user_id, total_value, "stocks")  # ✅ FIXED

    history = load_portfolio_history(user_id)

    # -------------------------------------
    # PnL
    # -------------------------------------
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

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
    # CHART (CLEAN + STABLE)
    # -------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:

        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        # remove bad values
        h = h[h["value_ghs"] > 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines"
        ))

        fig.update_layout(
            height=350,
            hovermode="x unified"
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Waiting for data...")

    # -------------------------------------
    # ALLOCATION
    # -------------------------------------
    st.markdown("---")
    st.subheader("🍕 Allocation")

    pie_df = df[df["Value (GHS)"] > 0]

    if not pie_df.empty:

        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
            tooltip=["Asset", "Value (GHS)"],
        )

        st.altair_chart(pie, use_container_width=True)

    else:
        st.info("Allocation will appear once assets have value.")
