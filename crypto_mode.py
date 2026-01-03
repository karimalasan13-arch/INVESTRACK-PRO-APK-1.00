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
# HELPERS
# -----------------------------------------
def load_setting(user_id, key, default):
    try:
        r = (
            supabase.table("user_settings")
            .select("value")
            .eq("user_id", user_id)
            .eq("key", key)
            .single()
            .execute()
        )
        return float(r.data["value"])
    except Exception:
        return default


def save_setting(user_id, key, value):
    supabase.table("user_settings").upsert(
        {"user_id": user_id, "key": key, "value": float(value)},
        on_conflict="user_id,key",
    ).execute()


def load_crypto_holdings(user_id):
    holdings = {k: 0.0 for k in API_MAP}
    try:
        r = (
            supabase.table("crypto_holdings")
            .select("symbol,quantity")
            .eq("user_id", user_id)
            .execute()
        )
        for row in r.data or []:
            holdings[row["symbol"]] = float(row["quantity"])
    except Exception:
        pass
    return holdings


def save_crypto_holdings(user_id, holdings):
    rows = [
        {"user_id": user_id, "symbol": s, "quantity": float(q)}
        for s, q in holdings.items()
    ]
    supabase.table("crypto_holdings").upsert(
        rows, on_conflict="user_id,symbol"
    ).execute()


def load_portfolio_history(user_id):
    try:
        r = (
            supabase.table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .order("timestamp")
            .execute()
        )
        return r.data or []
    except Exception:
        return []


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# -----------------------------------------
# MAIN APP
# -----------------------------------------
def crypto_app():
    st.title("💰 Crypto Portfolio")

    user_id = st.session_state.user_id

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    # ---------------- SIDEBAR (INPUTS ONLY) ----------------
    st.sidebar.header("⚙️ Crypto Settings")

    rate = st.sidebar.number_input("USD → GHS", value=float(rate), step=0.1)
    invested = st.sidebar.number_input("Total Invested (GHS)", value=float(invested))

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Saved")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in API_MAP:
        holdings[sym] = st.sidebar.number_input(
            sym, value=float(holdings.get(sym, 0.0)), step=0.0001
        )

    if st.sidebar.button("💾 Save Holdings"):
        save_crypto_holdings(user_id, holdings)
        st.sidebar.success("Saved")

    # ---------------- DATA ----------------
    prices = crypto_live_prices() or {}

    rows, total_value = [], 0.0
    for sym, qty in holdings.items():
        price = prices.get(sym, 1.0 if sym == "USDT" else 0.0)
        value = qty * price * rate
        total_value += value
        rows.append([sym, qty, price, value])

    df = pd.DataFrame(
        rows, columns=["Asset", "Qty", "Price (USD)", "Value (GHS)"]
    )

    autosave_portfolio_value(user_id, total_value)
    history = load_portfolio_history(user_id)

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # ---------------- MOBILE TABS ----------------
    tab1, tab2, tab3 = st.tabs(["📊 Summary", "📈 Charts", "🍕 Allocation"])

    # -------- SUMMARY --------
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("Value", fmt(total_value))
        c2.metric("Invested", fmt(invested))
        c3.metric("PnL", fmt(pnl), pct(pnl_pct))

        st.dataframe(df, use_container_width=True)

    # -------- CHARTS --------
    with tab2:
        if len(history) >= 2:
            h = pd.DataFrame(history)
            h["timestamp"] = pd.to_datetime(h["timestamp"])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=h["timestamp"], y=h["value_ghs"], mode="lines+markers"
            ))
            fig.update_layout(
                height=350,
                xaxis_title="Date",
                yaxis_title="Value (GHS)",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Portfolio history will appear after multiple snapshots.")

        # ---- MTD / YTD ----
        if history:
            now = datetime.utcnow()
            h = h.sort_values("timestamp")

            mtd = h[h["timestamp"].dt.month == now.month]
            ytd = h[h["timestamp"].dt.year == now.year]

            mtd_start = mtd.iloc[0]["value_ghs"] if not mtd.empty else total_value
            ytd_start = ytd.iloc[0]["value_ghs"] if not ytd.empty else total_value

            mtd_pnl = total_value - mtd_start
            ytd_pnl = total_value - ytd_start

            c1, c2 = st.columns(2)
            c1.metric("MTD", fmt(mtd_pnl), pct((mtd_pnl / mtd_start * 100) if mtd_start else 0))
            c2.metric("YTD", fmt(ytd_pnl), pct((ytd_pnl / ytd_start * 100) if ytd_start else 0))

    # -------- ALLOCATION --------
    with tab3:
        pie_df = df[df["Value (GHS)"] > 0]
        if not pie_df.empty:
            pie = alt.Chart(pie_df).mark_arc().encode(
                theta="Value (GHS):Q",
                color="Asset:N",
                tooltip=["Asset", "Value (GHS)"],
            )
            st.altair_chart(pie, use_container_width=True)
        else:
            st.info("No allocation yet.")
