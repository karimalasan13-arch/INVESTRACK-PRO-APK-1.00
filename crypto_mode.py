import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


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
# SESSION CLIENT
# -----------------------------------------
def db():
    supabase = get_supabase()

    if "access_token" in st.session_state:
        try:
            supabase.auth.set_session(
                access_token=st.session_state.access_token,
                refresh_token=st.session_state.refresh_token,
            )
        except Exception:
            pass

    return supabase


# -----------------------------------------
# PRICE MEMORY
# -----------------------------------------
def safe_price(symbol, price):

    if "crypto_price_memory" not in st.session_state:
        st.session_state.crypto_price_memory = {}

    if price and price > 0:
        st.session_state.crypto_price_memory[symbol] = price
        return price

    return st.session_state.crypto_price_memory.get(symbol, 0)


# -----------------------------------------
# BUILD PNL HISTORY
# -----------------------------------------
def build_pnl_history(history, invested):

    if not history:
        return pd.DataFrame()

    h = pd.DataFrame(history)

    if h.empty:
        return pd.DataFrame()

    h["timestamp"] = pd.to_datetime(h["timestamp"])
    h = h[h["value_ghs"] > 0]

    h["pnl"] = h["value_ghs"] - invested

    return h.sort_values("timestamp")


# -----------------------------------------
# SETTINGS
# -----------------------------------------
def load_setting(user_id, key, default):

    try:
        res = (
            db()
            .table("user_settings")
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

    db().table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
        on_conflict="user_id,key",
    ).execute()


# -----------------------------------------
# HOLDINGS
# -----------------------------------------
def load_crypto_holdings(user_id):

    holdings = {k: 0.0 for k in API_MAP}

    try:
        res = (
            db()
            .table("crypto_holdings")
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

    db().table("crypto_holdings").upsert(
        rows,
        on_conflict="user_id,symbol",
    ).execute()


# -----------------------------------------
# HISTORY
# -----------------------------------------
def load_portfolio_history(user_id):

    try:
        res = (
            db()
            .table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "crypto")
            .order("timestamp")
            .execute()
        )

        return res.data or []

    except Exception:
        return []


# -----------------------------------------
# FORMAT
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

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # SIDEBAR
    st.sidebar.header("💰 Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Crypto Holdings")

    for sym in API_MAP:

        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            step=0.0001,
            key=f"crypto_{sym}",
        )

    if st.sidebar.button("💾 Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Holdings saved")

    # LIVE PRICES
    try:
        prices = crypto_live_prices() or {}
    except Exception:
        prices = {}

    rows = []
    total_value = 0

    for sym, qty in holdings.items():

        raw_price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        usd_price = safe_price(sym, raw_price)

        value_ghs = qty * usd_price * rate
        total_value += value_ghs

        rows.append([sym, qty, usd_price, value_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    st.subheader("📘 Crypto Assets")
    st.dataframe(df, use_container_width=True)

    if total_value > 0:
        autosave_portfolio_value(user_id, total_value, "crypto")

    history = load_portfolio_history(user_id)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # RANGE SELECTOR
    range_option = st.radio(
        "Chart Range",
        ["1D", "7D", "1M", "3M", "1Y", "ALL"],
        horizontal=True,
    )

    filtered_history = []

    if history:

        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h[h["value_ghs"] > 0]

        now = datetime.utcnow()

        if range_option == "1D":
            h = h[h["timestamp"] >= now - pd.Timedelta(days=1)]

        elif range_option == "7D":
            h = h[h["timestamp"] >= now - pd.Timedelta(days=7)]

        elif range_option == "1M":
            h = h[h["timestamp"] >= now - pd.Timedelta(days=30)]

        elif range_option == "3M":
            h = h[h["timestamp"] >= now - pd.Timedelta(days=90)]

        elif range_option == "1Y":
            h = h[h["timestamp"] >= now - pd.Timedelta(days=365)]

        filtered_history = h.sort_values("timestamp").to_dict("records")

    # VALUE CHART
    st.subheader("📈 Portfolio Value Over Time")

    if filtered_history and len(filtered_history) >= 2:

        h = pd.DataFrame(filtered_history)

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=h["timestamp"],
                y=h["value_ghs"],
                mode="lines",
                line=dict(shape="spline", smoothing=1.2, width=3),
                fill="tozeroy",
            )
        )

        fig.update_layout(
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="Value (GHS)",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Not enough data for this range.")

    # PNL CHART
    st.subheader("📊 All-Time PnL")

    pnl_df = build_pnl_history(filtered_history, invested)

    if pnl_df is not None and len(pnl_df) >= 2:

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=pnl_df["timestamp"],
                y=pnl_df["pnl"],
                mode="lines",
                line=dict(shape="spline", smoothing=1.2, width=3),
            )
        )

        fig.update_layout(
            hovermode="x unified",
            height=350,
            xaxis_title="Date",
            yaxis_title="PnL (GHS)",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("PnL chart will appear once enough history exists.")

    # MTD / YTD
    st.markdown("---")
    st.subheader("📆 MTD & YTD Performance")

    if history:

        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h[h["value_ghs"] > 0]
        h = h.sort_values("timestamp")

        now = datetime.utcnow()

        mtd = h[h["timestamp"].dt.month == now.month]
        ytd = h[h["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total_value
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total_value

        mtd_pnl = total_value - mtd_start
        ytd_pnl = total_value - ytd_start

        mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0
        ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0

    else:
        mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0

    c1, c2 = st.columns(2)
    c1.metric("MTD", fmt(mtd_pnl), pct(mtd_pct))
    c2.metric("YTD", fmt(ytd_pnl), pct(ytd_pct))

    # ALLOCATION
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
