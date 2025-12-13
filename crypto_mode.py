import streamlit as st
import json
import os
import pandas as pd
import altair as alt
from datetime import datetime
from price_history import crypto_live_prices
import plotly.graph_objects as go
from portfolio_tracker import load_history as pt_load_history, autosave_portfolio_value


USER_FILE = "user_data.json"
HIST_FILE = "crypto_history.json"

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
    "USDT": "Tether",
}

# -------------------------------------------------
# Local history functions (do NOT conflict with portfolio_tracker)
# -------------------------------------------------
def load_local_history():
    if not os.path.exists(HIST_FILE):
        return []
    try:
        with open(HIST_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_local_history(history):
    with open(HIST_FILE, "w") as f:
        json.dump(history, f, indent=4)


# -------------------------------------------------
# User storage
# -------------------------------------------------
def load_user_data():
    default = {"crypto_rate": 14.5, "crypto_investment": 0, "crypto_holdings": {}}

    if not os.path.exists(USER_FILE):
        return default

    try:
        with open(USER_FILE, "r") as f:
            data = json.load(f)
    except:
        return default

    for k, v in default.items():
        data.setdefault(k, v)

    # Ensure float quantities
    for s, q in list(data["crypto_holdings"].items()):
        try:
            data["crypto_holdings"][s] = float(q)
        except:
            data["crypto_holdings"][s] = 0.0

    return data


def save_user_data(data):
    with open(USER_FILE, "w") as f:
        json.dump(data, f, indent=4)


# Formatting helpers
def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# -------------------------------------------------
# MAIN APP
# -------------------------------------------------
def crypto_app():
    st.title("💰 Crypto Portfolio Tracker")

    data = load_user_data()

    # --- Sidebar settings ---
    st.sidebar.header("Crypto Settings (separate)")
    rate = st.sidebar.number_input(
        "Crypto Exchange Rate (USD → GHS)", value=float(data["crypto_rate"]), step=0.1
    )
    invested = st.sidebar.number_input(
        "Total Crypto Investment (GHS)", value=float(data["crypto_investment"]), step=10.0
    )

    data["crypto_rate"] = rate
    data["crypto_investment"] = invested

    st.sidebar.markdown("---")
    st.sidebar.subheader("Crypto Holdings")

    holdings = data["crypto_holdings"]
    for sym in API_MAP.keys():
        holdings.setdefault(sym, 0.0)

    updated = False
    for sym in API_MAP:
        new_qty = st.sidebar.number_input(
            f"{sym} quantity", value=float(holdings[sym]), step=0.0001, key=f"hold_{sym}"
        )
        if new_qty != holdings[sym]:
            holdings[sym] = new_qty
            updated = True

    if st.sidebar.button("Save Holdings"):
        save_user_data(data)
        st.sidebar.success("Crypto holdings saved.")

    if st.sidebar.button("Save Settings"):
        save_user_data(data)
        st.sidebar.success("Settings saved.")

    # -------------------------------------------------
    # Live prices
    # -------------------------------------------------
    prices = crypto_live_prices()

    # Build table
    rows = []
    total_value_ghs = 0.0

    for sym, qty in holdings.items():
        usd_price = prices.get(sym, 0)
        value_usd = usd_price * qty
        value_ghs = value_usd * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_usd, value_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"])

    st.subheader("📘 Crypto Asset Breakdown")
    st.dataframe(df, use_container_width=True)

    # PnL
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    # -------------------------------------------------
    # Save daily history
    # -------------------------------------------------
    history = load_local_history()
    today = datetime.utcnow().date().isoformat()

    updated_today = False
    for entry in history:
        if entry["timestamp"] == today:
            entry["value_ghs"] = total_value_ghs
            updated_today = True
            break

    if not updated_today:
        history.append({"timestamp": today, "value_ghs": total_value_ghs})

    save_local_history(history)

    # Also autosave via your tracker
    autosave_portfolio_value(total_value_ghs)

    # -------------------------------------------------
    # Summary Section
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Value (GHS)", fmt(total_value_ghs))

    with col2:
        st.metric("Total Invested (GHS)", fmt(invested))

    with col3:
        st.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # -------------------------------------------------
    # Line Chart (Plotly)
    # -------------------------------------------------
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) < 2:
        st.info("Portfolio history will appear here as data is collected.")
    else:
        dates = [h["timestamp"] for h in history]
        values = [h["value_ghs"] for h in history]  # FIXED KEY

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=values,
                mode="lines+markers",
                line=dict(color="#00c3ff", width=3),
                marker=dict(size=6),
                hovertemplate="Value: ₵ %{y:,.2f}<br>Date: %{x}<extra></extra>",
            )
        )

        fig.update_layout(
            height=350,
            xaxis_title="Date",
            yaxis_title="Portfolio Value (GHS)",
            hovermode="x unified",
            dragmode="zoom",
            showlegend=False,
            margin=dict(l=40, r=20, t=20, b=40),
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------------------
    # MTD / YTD
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    hist_df = pd.DataFrame(history)
    hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
    hist_df = hist_df.sort_values("timestamp")

    now = datetime.utcnow()

    # MTD
    month_df = hist_df[hist_df["timestamp"].dt.month == now.month]
    if len(month_df) > 0:
        mtd_start = float(month_df.iloc[0]["value_ghs"])
        mtd_pnl = total_value_ghs - mtd_start
        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0
    else:
        mtd_pnl = mtd_pct = 0.0

    # YTD
    year_df = hist_df[hist_df["timestamp"].dt.year == now.year]
    if len(year_df) > 0:
        ytd_start = float(year_df.iloc[0]["value_ghs"])
        ytd_pnl = total_value_ghs - ytd_start
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0
    else:
        ytd_pnl = ytd_pct = 0.0

    colA, colB = st.columns(2)

    with colA:
        st.markdown("### 📅 MTD PnL")
        st.metric("MTD", fmt(mtd_pnl), pct(mtd_pct))

    with colB:
        st.markdown("### 📆 YTD PnL")
        st.metric("YTD", fmt(ytd_pnl), pct(ytd_pct))

    # -------------------------------------------------
    # Allocation pie chart
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("🍕 Allocation (by Value)")

    df_pie = df[df["Value (GHS)"] > 0][["Asset", "Value (GHS)"]]
    if df_pie.empty:
        st.info("No allocations to display.")
    else:
        pie = (
            alt.Chart(df_pie)
            .mark_arc()
            .encode(
                theta=alt.Theta(field="Value (GHS)", type="quantitative"),
                color=alt.Color("Asset:N"),
                tooltip=["Asset", "Value (GHS)"],
            )
        )
        st.altair_chart(pie, use_container_width=True)

    # -------------------------------------------------
    # Candlestick-style daily chart
    # -------------------------------------------------
    st.markdown("---")
    st.subheader("🕯️ Portfolio Candlestick (daily closes only)")

    if len(history) >= 2:
        hist_df = pd.DataFrame(history)
        hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
        hist_df = hist_df.sort_values("timestamp").reset_index(drop=True)

        hist_df["close"] = hist_df["value_ghs"]
        hist_df["open"] = hist_df["close"].shift(1).fillna(hist_df["close"])
        hist_df["high"] = hist_df[["open", "close"]].max(axis=1)
        hist_df["low"] = hist_df[["open", "close"]].min(axis=1)

        base = alt.Chart(hist_df).encode(
            x=alt.X("timestamp:T", axis=alt.Axis(title="Date"))
        )

        rule = base.mark_rule().encode(
            y="low:Q",
            y2="high:Q",
            color=alt.condition("datum.close >= datum.open", alt.value("#0b8f2f"), alt.value("#b00020")),
        )

        bar = base.mark_bar(size=8).encode(
            y="open:Q",
            y2="close:Q",
            color=alt.condition("datum.close >= datum.open", alt.value("#0b8f2f"), alt.value("#b00020")),
            tooltip=["timestamp:T", "open:Q", "high:Q", "low:Q", "close:Q"],
        )

        st.altair_chart((rule + bar).properties(height=300), use_container_width=True)
    else:
        st.info("Not enough history to show candlestick.")
