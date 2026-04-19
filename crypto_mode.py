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

MODE = "crypto"


# -----------------------------------------
# DB
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
# 🚨 FORCE SNAPSHOT
# -----------------------------------------
def force_snapshot(user_id, value_ghs):
    try:
        db().table("portfolio_history").insert({
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "value_ghs": round(float(value_ghs), 2),
            "mode": MODE,
        }).execute()
        return True
    except Exception:
        return False


# -----------------------------------------
# SAFE PRICE (MODE ISOLATED)
# -----------------------------------------
def safe_price(symbol, price):

    key = f"{MODE}_price_memory"

    if key not in st.session_state:
        st.session_state[key] = {}

    if price and price > 0:
        st.session_state[key][symbol] = price
        return price

    return st.session_state[key].get(symbol, 0)


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
            .eq("mode", MODE)
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


# -----------------------------------------
# MAIN
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
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(sym, value=float(holdings.get(sym, 0.0)), step=0.0001)

    if st.sidebar.button("💾 Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Saved")

    # -------------------------------------
    # PRICE FETCH + ERROR REPORTING
    # -------------------------------------
    price_error = False

    try:
        prices = crypto_live_prices() or {}
        if not prices:
            price_error = True
    except Exception:
        prices = {}
        price_error = True

    if price_error:
        st.error("⚠️ Live crypto prices unavailable. Showing last known values.")

    # -------------------------------------
    # BUILD TABLE
    # -------------------------------------
    rows = []
    total_value = 0.0

    for sym, qty in holdings.items():

        raw_price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        usd_price = safe_price(sym, raw_price)

        value = qty * usd_price * rate
        total_value += value

        rows.append([sym, qty, usd_price, value])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    # SNAPSHOT BUTTON
    if st.button("📸 Save Snapshot Now"):
        if total_value > 0 and force_snapshot(user_id, total_value):
            st.success("Snapshot saved")

    # AUTOSAVE
    if total_value > 0:
        autosave_portfolio_value(user_id, total_value, MODE)

    history = load_portfolio_history(user_id)

    # SUMMARY
    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", f"GHS {total_value:,.2f}")
    c2.metric("Invested", f"GHS {invested:,.2f}")
    c3.metric("PnL", f"GHS {pnl:,.2f}", f"{pnl_pct:.2f}%")

    # CHART
    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        h = h[h["value_ghs"] > 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h["timestamp"], y=h["value_ghs"], mode="lines"))
        st.plotly_chart(fig, use_container_width=True)

    # PIE
    pie_df = df[df["Value (GHS)"] > 0]
    if not pie_df.empty:
        pie = alt.Chart(pie_df).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
        )
        st.altair_chart(pie, use_container_width=True)
