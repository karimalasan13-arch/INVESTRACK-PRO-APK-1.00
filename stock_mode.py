import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


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
# 🚨 NEW: FORCE SNAPSHOT (BYPASS FILTERS)
# -----------------------------------------
def force_snapshot(user_id, value_ghs, mode="stock"):
    try:
        db().table("portfolio_history").insert({
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "value_ghs": round(float(value_ghs), 2),
            "mode": mode,
        }).execute()
        return True
    except Exception as e:
        print("Force snapshot failed:", e)
        return False


# -------------------------------
# SAFE PRICE
# -------------------------------
def safe_price(symbol, price):

    if "stock_price_memory" not in st.session_state:
        st.session_state.stock_price_memory = {}

    if price and price > 0:
        st.session_state.stock_price_memory[symbol] = price
        return round(price, 2)

    return round(st.session_state.stock_price_memory.get(symbol, 0), 2)


# -------------------------------
# CLEAN HISTORY
# -------------------------------
def clean_history(history):

    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["value_ghs"] = pd.to_numeric(df["value_ghs"], errors="coerce")

    df = df.dropna()
    df = df[df["value_ghs"] > 0]
    df = df.sort_values("timestamp")

    return df


# -------------------------------
# BUILD PNL
# -------------------------------
def build_pnl(df, invested):

    if df.empty:
        return df

    df = df.copy()
    df["pnl"] = df["value_ghs"] - invested
    return df


# -------------------------------
# SETTINGS
# -------------------------------
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


# -------------------------------
# HOLDINGS
# -------------------------------
def load_stock_holdings(user_id):

    holdings = {k: 0.0 for k in STOCK_MAP}

    try:
        res = (
            db()
            .table("stock_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )

        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])

    except Exception:
        pass

    return holdings


def save_stock_holdings(user_id, holdings):

    rows = [
        {"user_id": user_id, "symbol": k, "quantity": float(v)}
        for k, v in holdings.items()
    ]

    db().table("stock_holdings").upsert(
        rows,
        on_conflict="user_id,symbol",
    ).execute()


# -------------------------------
# HISTORY
# -------------------------------
def load_portfolio_history(user_id):
    try:
        res = (
            db()
            .table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "stock")
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


# -------------------------------
# FORMATTERS
# -------------------------------
def fmt(v):
    return f"GHS {v:,.2f}"


def pct(v):
    return f"{v:.2f}%"


# -------------------------------
# MAIN
# -------------------------------
def stock_app():

    st.title("📊 Stock Portfolio Tracker")

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    cash = load_setting(user_id, "stock_cash", 0.0)

    holdings = load_stock_holdings(user_id)

    # SIDEBAR
    st.sidebar.header("📊 Stock Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Stock Holdings")

    for sym in STOCK_MAP:
        holdings[sym] = st.sidebar.number_input(sym, value=float(holdings.get(sym, 0.0)), step=1.0)

    cash = st.sidebar.number_input("💵 Cash (GHS)", value=float(cash), step=10.0)

    if st.sidebar.button("💾 Save Holdings"):
        save_stock_holdings(user_id, holdings)
        save_setting(user_id, "stock_cash", cash)

    # LIVE PRICES
    prices = stock_live_prices(list(STOCK_MAP.keys())) or {}

    rows = []
    total_value = cash

    for sym, qty in holdings.items():
        price = safe_price(sym, prices.get(sym, 0.0))
        value = price * qty * rate
        total_value += value
        rows.append([sym, qty, price, value])

    if cash > 0:
        rows.append(["CASH", "-", "-", cash])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])

    st.dataframe(df, use_container_width=True)

    # -------------------------------------
    # 🔥 NEW: MANUAL SNAPSHOT BUTTON
    # -------------------------------------
    col1, col2 = st.columns([1, 3])

    with col1:
        if st.button("📸 Save Snapshot Now"):
            if total_value > 0:
                if force_snapshot(user_id, total_value):
                    st.success("Snapshot saved instantly!")
                else:
                    st.error("Snapshot failed.")

    with col2:
        st.caption("Manually save your portfolio at any time")

    # -------------------------------------
    # AUTOSAVE (UNCHANGED)
    # -------------------------------------
    if total_value > 0:
        autosave_portfolio_value(user_id, total_value, "stock")

    # HISTORY
    raw_history = load_portfolio_history(user_id)
    history = clean_history(raw_history)

    # SUMMARY
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    st.subheader("📈 Portfolio Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # VALUE CHART
    st.subheader("📈 Portfolio Value Over Time")

    if len(history) >= 2:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=history["timestamp"],
            y=history["value_ghs"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.2, width=3),
            fill="tozeroy"
        ))

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning(f"Not enough clean data for chart ({len(history)} rows)")

    # PNL CHART
    st.subheader("📊 All-Time PnL")

    pnl_df = build_pnl(history, invested)

    if len(pnl_df) >= 2:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.2, width=3),
        ))

        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning(f"Not enough clean PnL data ({len(pnl_df)} rows)")

    # PIE
    st.subheader("🍕 Allocation")

    pie_df = df[df["Value (GHS)"] > 0]

    if not pie_df.empty:
        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
        )
        st.altair_chart(pie, use_container_width=True)
