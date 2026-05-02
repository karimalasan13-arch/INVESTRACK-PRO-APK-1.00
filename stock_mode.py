import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


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


def force_snapshot(user_id, value_ghs, mode="crypto"):
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


def safe_price(symbol, price):
    if "crypto_price_memory" not in st.session_state:
        st.session_state.crypto_price_memory = {}

    memory = st.session_state.crypto_price_memory

    if price is not None and price > 0:
        memory[symbol] = price
        return price, True

    if symbol in memory:
        return memory[symbol], False

    return None, False


def get_last_good_value():
    return st.session_state.get("crypto_last_good_value", None)


def set_last_good_value(value):
    st.session_state.crypto_last_good_value = value


def build_pnl_history(history, invested):
    if not history:
        return pd.DataFrame()

    h = pd.DataFrame(history)
    if h.empty:
        return pd.DataFrame()

    h["timestamp"] = pd.to_datetime(h["timestamp"])
    h = h.sort_values("timestamp")
    h["pnl"] = h["value_ghs"] - invested
    return h


def load_setting(user_id, key, default):
    try:
        res = (
            db().table("user_settings")
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


def load_crypto_holdings(user_id):
    holdings = {k: 0.0 for k in API_MAP}
    try:
        res = db().table("crypto_holdings").select("symbol,quantity").eq("user_id", user_id).execute()
        for r in res.data or []:
            holdings[r["symbol"]] = float(r["quantity"])
    except Exception:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [{"user_id": user_id, "symbol": k, "quantity": float(v)} for k, v in holdings.items()]
    db().table("crypto_holdings").upsert(rows, on_conflict="user_id,symbol").execute()


def load_portfolio_history(user_id):
    try:
        res = (
            db().table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "crypto")
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


def crypto_app():

    st.title("💰 Crypto Portfolio Tracker")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    st.sidebar.header("💰 Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested), step=10.0)

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Crypto Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(sym, value=float(holdings.get(sym, 0.0)), step=0.0001)

    if st.sidebar.button("💾 Save Holdings"):
        save_crypto_holdings(user_id, holdings)

    try:
        prices = crypto_live_prices() or {}
    except Exception:
        prices = {}

    rows = []
    total_value = 0.0
    data_degraded = False

    for sym, qty in holdings.items():
        raw = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        price, ok = safe_price(sym, raw)

        if price is None:
            data_degraded = True
            continue

        if not ok:
            data_degraded = True

        val = qty * price * rate
        total_value += val
        rows.append([sym, qty, price, val])

    last_good = get_last_good_value()
    if total_value > 0 and not data_degraded:
        set_last_good_value(total_value)
    elif last_good is not None:
        total_value = last_good

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    if total_value > 0 and not data_degraded:
        autosave_portfolio_value(user_id, total_value, "crypto")

    history = load_portfolio_history(user_id)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    st.subheader("📈 Portfolio Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # ✅ SMOOTH CHART
    st.subheader("📈 Portfolio Value Over Time")
    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"])

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.2, width=3),
            fill="tozeroy"
        ))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 All-Time PnL")
    pnl_df = build_pnl_history(history, invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.2, width=3),
        ))
        st.plotly_chart(fig, use_container_width=True)
    # -----------------------------------------
    # PIE
    # -----------------------------------------
    st.subheader("🍕 Allocation")

    if not df.empty:
        pie = alt.Chart(df[df["Value (GHS)"] > 0]).mark_arc().encode(
            theta="Value (GHS):Q",
            color="Asset:N",
        )
        st.altair_chart(pie, use_container_width=True)
