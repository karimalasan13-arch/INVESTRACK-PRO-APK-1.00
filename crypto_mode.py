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
# SESSION CACHE HELPER
# -----------------------------------------
def session_cache(key, loader):
    if key not in st.session_state:
        st.session_state[key] = loader()
    return st.session_state[key]


# -----------------------------------------
# SUPABASE HELPERS
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
        return float(res.data["value"]) if res.data else default
    except Exception:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": value},
        on_conflict="user_id,key",
    ).execute()


def load_crypto_holdings(user_id):
    holdings = {s: 0.0 for s in API_MAP}
    try:
        res = (
            supabase.table("crypto_holdings")
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
        {"user_id": user_id, "symbol": s, "quantity": q}
        for s, q in holdings.items()
    ]
    supabase.table("crypto_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


def load_portfolio_history(user_id):
    try:
        res = (
            supabase.table("portfolio_history")
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
    st.title("💰 Crypto Portfolio Tracker")
    user_id = st.session_state.user.id

    rate = session_cache(
        "crypto_rate",
        lambda: load_setting(user_id, "crypto_rate", 14.5)
    )
    invested = session_cache(
        "crypto_investment",
        lambda: load_setting(user_id, "crypto_investment", 0.0)
    )
    holdings = session_cache(
        "crypto_holdings",
        lambda: load_crypto_holdings(user_id)
    )

    # ---------- Sidebar ----------
    st.sidebar.header("Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS", value=rate, step=0.1)
    invested = st.sidebar.number_input("Total Investment (GHS)", value=invested, step=10.0)

    if st.sidebar.button("Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.session_state.pop("crypto_rate", None)
        st.session_state.pop("crypto_investment", None)
        st.success("Settings saved")
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym, value=float(holdings[sym]), step=0.0001
        )

    if st.sidebar.button("Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.session_state.pop("crypto_holdings", None)
        st.success("Holdings saved")
        st.rerun()

    # ---------- Prices ----------
    prices = crypto_live_prices()

    rows, total_value = [], 0.0
    for sym, qty in holdings.items():
        usd = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        v_usd = usd * qty
        v_ghs = v_usd * rate
        total_value += v_ghs
        rows.append([sym, qty, usd, v_usd, v_ghs])

    df = pd.DataFrame(rows, columns=["Asset", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"])
    st.dataframe(df, use_container_width=True)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested else 0.0

    autosave_portfolio_value(user_id, total_value)
    history = session_cache(
        "crypto_history",
        lambda: load_portfolio_history(user_id)
    )

    # ---------- Summary ----------
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Value", fmt(total_value))
    c2.metric("Invested", fmt(invested))
    c3.metric("All-Time PnL", fmt(pnl), pct(pnl_pct))

    # ---------- Chart ----------
    if len(history) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[h["timestamp"] for h in history],
            y=[h["value_ghs"] for h in history],
            mode="lines+markers",
        ))
        st.plotly_chart(fig, use_container_width=True)

    # ---------- MTD / YTD ----------
    hist = pd.DataFrame(history)
    if not hist.empty:
        hist["timestamp"] = pd.to_datetime(hist["timestamp"])
        now = datetime.utcnow()
        mtd = hist[hist["timestamp"].dt.month == now.month]
        ytd = hist[hist["timestamp"].dt.year == now.year]

        mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total_value
        ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total_value

        c1, c2 = st.columns(2)
        c1.metric("MTD", fmt(total_value - mtd_start))
        c2.metric("YTD", fmt(total_value - ytd_start))

    # ---------- Pie ----------
    pie_df = df[df["Value (GHS)"] > 0][["Asset", "Value (GHS)"]]
    if not pie_df.empty:
        st.altair_chart(
            alt.Chart(pie_df).mark_arc().encode(
                theta="Value (GHS):Q",
                color="Asset:N",
                tooltip=["Asset", "Value (GHS)"],
            ),
            use_container_width=True,
        )
