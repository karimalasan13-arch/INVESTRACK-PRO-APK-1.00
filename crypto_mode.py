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


CURRENCY_OPTIONS = [
    {"code": "GHS", "name": "Ghana Cedi", "symbol": "₵"},
    {"code": "NGN", "name": "Nigerian Naira", "symbol": "₦"},
    {"code": "KES", "name": "Kenyan Shilling", "symbol": "KSh"},
    {"code": "ZAR", "name": "South African Rand", "symbol": "R"},
    {"code": "CFA", "name": "CFA Franc", "symbol": "CFA"},
    {"code": "USD", "name": "US Dollar", "symbol": "$"},
    {"code": "CNY", "name": "Chinese Yuan", "symbol": "¥"},
    {"code": "JPY", "name": "Japanese Yen", "symbol": "¥"},
    {"code": "GBP", "name": "British Pound", "symbol": "£"},
    {"code": "CAD", "name": "Canadian Dollar", "symbol": "C$"},
    {"code": "CHF", "name": "Swiss Franc", "symbol": "CHF"},
    {"code": "EUR", "name": "Euro", "symbol": "€"},
]


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
# SNAPSHOT
# -----------------------------------------
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


# -----------------------------------------
# SAFE PRICE
# -----------------------------------------
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


# -----------------------------------------
# LAST GOOD VALUE
# -----------------------------------------
def get_last_good_value():
    return st.session_state.get("crypto_last_good_value", None)


def set_last_good_value(value):
    st.session_state.crypto_last_good_value = value


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
        {
            "user_id": user_id,
            "key": key,
            "value": float(value),
        },
        on_conflict="user_id,key",
    ).execute()


# -----------------------------------------
# CURRENCY HELPERS
# -----------------------------------------
def currency_label(currency):
    return f'{currency["code"]} - {currency["name"]}'


def load_currency_index(user_id, mode):
    idx = int(load_setting(user_id, f"{mode}_currency_index", 0))

    if idx < 0 or idx >= len(CURRENCY_OPTIONS):
        idx = 0

    return idx


def fmt(v, currency):
    return f'{currency["symbol"]} {v:,.2f}'


def pct(v):
    return f"{v:.2f}%"


# -----------------------------------------
# PNL HISTORY
# -----------------------------------------
def build_pnl_history(history, invested):

    if not history:
        return pd.DataFrame()

    h = pd.DataFrame(history)

    if h.empty:
        return pd.DataFrame()

    h["timestamp"] = pd.to_datetime(
        h["timestamp"],
        errors="coerce"
    )

    h["value_ghs"] = pd.to_numeric(
        h["value_ghs"],
        errors="coerce"
    )

    h = h.dropna().sort_values("timestamp")

    h["pnl"] = h["value_ghs"] - invested

    return h


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
        {
            "user_id": user_id,
            "symbol": k,
            "quantity": float(v),
        }
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
# STREAMLIT METRIC DELTA FIX
# -----------------------------------------
def metric_delta(value):
    if value > 0:
        return f"{value:.2f}%"

    if value < 0:
        return f"-{abs(value):.2f}%"

    return "0.00%"


# -----------------------------------------
# MAIN
# -----------------------------------------
def crypto_app():

    st.title("Crypto Dashboard")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    # -----------------------------------------
    # LOAD SETTINGS
    # -----------------------------------------
    currency_index = load_currency_index(user_id, "crypto")
    selected_currency = CURRENCY_OPTIONS[currency_index]

    rate = load_setting(user_id, "crypto_rate", 14.5)

    invested = load_setting(
        user_id,
        "crypto_investment",
        0.0
    )

    holdings = load_crypto_holdings(user_id)

    # -----------------------------------------
    # SIDEBAR
    # -----------------------------------------
    st.sidebar.header("⚙️ Settings")

    currency_labels = [
        currency_label(c) for c in CURRENCY_OPTIONS
    ]

    selected_label = st.sidebar.selectbox(
        "Display Currency",
        currency_labels,
        index=currency_index
    )

    selected_index = currency_labels.index(selected_label)
    selected_currency = CURRENCY_OPTIONS[selected_index]
    currency_code = selected_currency["code"]

    rate = st.sidebar.number_input(
        f"USD → {currency_code}",
        value=float(rate),
        step=0.1
    )

    invested = st.sidebar.number_input(
        f'Total Invested ({currency_code})',
        value=float(invested),
        step=10.0
    )

    if st.sidebar.button("💾 Save Settings"):

        save_setting(user_id, "crypto_currency_index", selected_index)

        save_setting(user_id, "crypto_rate", rate)

        save_setting(
            user_id,
            "crypto_investment",
            invested
        )

        st.sidebar.success("Settings saved")

    st.sidebar.caption(
        f"Portfolio values will display in {currency_code}. "
        "Your exchange-rate input controls the conversion."
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Holdings")

    for sym in API_MAP:

        holdings[sym] = st.sidebar.number_input(
            sym,
            value=float(holdings.get(sym, 0.0)),
            step=0.0001
        )

    if st.sidebar.button("💾 Save Holdings"):

        save_crypto_holdings(
            user_id,
            holdings
        )

        st.sidebar.success("Holdings saved")

    # -----------------------------------------
    # LIVE PRICES
    # -----------------------------------------
    try:
        prices = crypto_live_prices() or {}

    except Exception:
        prices = {}

    rows = []

    total_value = 0.0
    data_degraded = False

    failed_assets = []

    value_col = f"Value ({currency_code})"

    for sym, qty in holdings.items():

        raw_price = prices.get(
            sym,
            1.0 if sym == "USDT" else 0.0
        )

        price, ok = safe_price(sym, raw_price)

        if price is None:
            data_degraded = True
            failed_assets.append(sym)
            continue

        if not ok:
            data_degraded = True
            failed_assets.append(sym)

        value_display = qty * price * rate

        total_value += value_display

        rows.append([
            sym,
            qty,
            round(price, 4),
            round(value_display, 2),
        ])

    # -----------------------------------------
    # LAST GOOD VALUE PROTECTION
    # -----------------------------------------
    last_good = get_last_good_value()

    if total_value > 0 and not data_degraded:
        set_last_good_value(total_value)

    elif last_good is not None:
        total_value = last_good

    # -----------------------------------------
    # WARNINGS
    # -----------------------------------------
    if failed_assets:

        st.warning(
            "Some prices could not be refreshed live: "
            + ", ".join(failed_assets)
            + ". Cached prices are being used."
        )

    # -----------------------------------------
    # DATAFRAME
    # -----------------------------------------
    df = pd.DataFrame(
        rows,
        columns=[
            "Asset",
            "Qty",
            "Price (USD)",
            value_col
        ]
    )

    # -----------------------------------------
    # KPI
    # -----------------------------------------
    pnl = total_value - invested

    pnl_pct = (
        (pnl / invested) * 100
        if invested > 0 else 0.0
    )

    st.subheader("📊 Overview")

    top1, top2, top3 = st.columns(3)

    top1.metric(
        "Portfolio Value",
        fmt(total_value, selected_currency)
    )

    top2.metric(
        "Invested",
        fmt(invested, selected_currency)
    )

    top3.metric(
        "PnL",
        fmt(pnl, selected_currency),
        metric_delta(pnl_pct)
    )

    # -----------------------------------------
    # HISTORY
    # -----------------------------------------
    history = load_portfolio_history(user_id)

    # -----------------------------------------
    # MTD / YTD
    # -----------------------------------------
    mtd_pnl = 0.0
    ytd_pnl = 0.0

    mtd_pct = 0.0
    ytd_pct = 0.0

    if history and len(history) >= 2:

        try:
            h = pd.DataFrame(history)

            h["timestamp"] = pd.to_datetime(
                h["timestamp"],
                errors="coerce"
            )

            h["value_ghs"] = pd.to_numeric(
                h["value_ghs"],
                errors="coerce"
            )

            h = h.dropna().sort_values("timestamp")

            if not h.empty:

                now = datetime.utcnow()

                mtd = h[
                    (h["timestamp"].dt.month == now.month)
                    &
                    (h["timestamp"].dt.year == now.year)
                ]

                ytd = h[
                    h["timestamp"].dt.year == now.year
                ]

                if not mtd.empty:

                    start = mtd.iloc[0]["value_ghs"]

                    if start > 0:

                        mtd_pnl = total_value - start

                        mtd_pct = (
                            (mtd_pnl / start) * 100
                        )

                if not ytd.empty:

                    start = ytd.iloc[0]["value_ghs"]

                    if start > 0:

                        ytd_pnl = total_value - start

                        ytd_pct = (
                            (ytd_pnl / start) * 100
                        )

        except Exception as e:
            print("MTD/YTD error:", e)

    # -----------------------------------------
    # MTD / YTD DISPLAY
    # -----------------------------------------
    bottom1, bottom2 = st.columns(2)

    bottom1.metric(
        "MTD",
        fmt(mtd_pnl, selected_currency),
        metric_delta(mtd_pct)
    )

    bottom2.metric(
        "YTD",
        fmt(ytd_pnl, selected_currency),
        metric_delta(ytd_pct)
    )

    st.markdown("---")

    # -----------------------------------------
    # HOLDINGS TABLE
    # -----------------------------------------
    st.subheader("📋 Holdings Breakdown")

    st.dataframe(
        df,
        use_container_width=True
    )

    # -----------------------------------------
    # MANUAL SNAPSHOT
    # -----------------------------------------
    col1, col2 = st.columns([1, 3])

    with col1:

        if st.button("📸 Save Snapshot Now"):

            if total_value > 0:

                if force_snapshot(user_id, total_value):
                    st.success("Snapshot saved!")

                else:
                    st.error("Snapshot failed.")

    with col2:
        st.caption("Manually save portfolio history")

    # -----------------------------------------
    # AUTOSAVE
    # -----------------------------------------
    if total_value > 0 and not data_degraded:

        autosave_portfolio_value(
            user_id,
            total_value,
            "crypto"
        )

    # -----------------------------------------
    # PORTFOLIO TREND
    # -----------------------------------------
    st.subheader("📈 Portfolio Trend")

    if len(history) >= 2:

        h = pd.DataFrame(history)

        h["timestamp"] = pd.to_datetime(
            h["timestamp"],
            errors="coerce"
        )

        h["value_ghs"] = pd.to_numeric(
            h["value_ghs"],
            errors="coerce"
        )

        h = h.dropna()

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines",
            line=dict(
                shape="spline",
                smoothing=1.1,
                width=3
            ),
            fill="tozeroy",
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            yaxis_title=f"Value ({currency_code})",
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:
        st.info("Waiting for more history data...")

    # -----------------------------------------
    # PNL CURVE
    # -----------------------------------------
    st.subheader("📊 All-Time PnL Curve")

    pnl_df = build_pnl_history(
        history,
        invested
    )

    if len(pnl_df) >= 2:

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(
                shape="spline",
                smoothing=1.1,
                width=3
            ),
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            yaxis_title=f"PnL ({currency_code})",
            hovermode="x unified"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    else:
        st.info("PnL history will appear soon.")

    # -----------------------------------------
    # ALLOCATION PIE
    # -----------------------------------------
    st.subheader("Allocation")

    if not df.empty:

        pie_df = df[df[value_col] > 0]

        pie = alt.Chart(
            pie_df
        ).mark_arc().encode(
            theta=f"{value_col}:Q",
            color="Asset:N",
        )

        st.altair_chart(
            pie,
            use_container_width=True
        )
