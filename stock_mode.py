import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


STOCK_MAP = {
    "NVDA": "NVDA",
    "AAPL": "AAPL",
    "GOOGL": "GOOGL",
    "GOOG": "GOOG",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    "META": "META",
    "AVGO": "AVGO",
    "TSLA": "TSLA",
    "BRK-B": "BRK-B",
    "TSM": "TSM",
    "LLY": "LLY",
    "JPM": "JPM",
    "WMT": "WMT",
    "V": "V",
    "MA": "MA",
    "NFLX": "NFLX",
    "ORCL": "ORCL",
    "XOM": "XOM",
    "COST": "COST",
    "JNJ": "JNJ",
    "HD": "HD",
    "PG": "PG",
    "BAC": "BAC",
    "ABBV": "ABBV",
    "KO": "KO",
    "PLTR": "PLTR",
    "ASML": "ASML",
    "SAP": "SAP",
    "UNH": "UNH",
    "AMD": "AMD",
    "CRM": "CRM",
    "CSCO": "CSCO",
    "CVX": "CVX",
    "IBM": "IBM",
    "GE": "GE",
    "WFC": "WFC",
    "TMUS": "TMUS",
    "NOW": "NOW",
    "MCD": "MCD",
    "PM": "PM",
    "ABT": "ABT",
    "LIN": "LIN",
    "DIS": "DIS",
    "MRK": "MRK",
    "ISRG": "ISRG",
    "INTU": "INTU",
    "GS": "GS",
    "CAT": "CAT",
    "TXN": "TXN",
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


def safe_price(symbol, price):
    if "stock_price_memory" not in st.session_state:
        st.session_state.stock_price_memory = {}

    memory = st.session_state.stock_price_memory

    if price is not None and price > 0:
        memory[symbol] = round(price, 2)
        return round(price, 2), True

    if symbol in memory:
        return memory[symbol], False

    return None, False


def get_last_good_value():
    return st.session_state.get("stock_last_good_value", None)


def set_last_good_value(value):
    st.session_state.stock_last_good_value = value


def clean_history(history):
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history)

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["value_ghs"] = pd.to_numeric(df["value_ghs"], errors="coerce")

    df = df.dropna()
    df = df.sort_values("timestamp")

    return df


def build_pnl(df, invested):
    if df.empty:
        return df

    df = df.copy()
    df["pnl"] = df["value_ghs"] - invested

    return df


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


def currency_label(currency):
    return f'{currency["code"]} - {currency["name"]}'


def load_currency_index(user_id, mode):
    idx = int(load_setting(user_id, f"{mode}_currency_index", 0))

    if idx < 0 or idx >= len(CURRENCY_OPTIONS):
        idx = 0

    return idx


def fmt(v, currency):
    return f'{currency["symbol"]} {v:,.2f}'


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
            symbol = r["symbol"]

            if symbol in holdings:
                holdings[symbol] = float(r["quantity"])

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


def metric_delta(v):
    if v > 0:
        return f"+{abs(v):.2f}%"

    elif v < 0:
        return f"-{abs(v):.2f}%"

    return "0.00%"


def stock_app():
    st.title("Stock Portfolio Dashboard")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    currency_index = load_currency_index(user_id, "stock")
    selected_currency = CURRENCY_OPTIONS[currency_index]

    rate = load_setting(user_id, "stock_rate", 14.5)
    invested = load_setting(user_id, "stock_investment", 0.0)
    cash = load_setting(user_id, "stock_cash", 0.0)

    holdings = load_stock_holdings(user_id)

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
        f"Total Invested ({currency_code})",
        value=float(invested),
        step=10.0
    )

    if st.sidebar.button("💾 Save Settings"):
        save_setting(user_id, "stock_currency_index", selected_index)
        save_setting(user_id, "stock_rate", rate)
        save_setting(user_id, "stock_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.caption(
        f"Portfolio values will display in {currency_code}. "
        "Your exchange-rate input controls the conversion."
    )

    st.sidebar.markdown("---")

    with st.expander("⚙️ Manage Stock Holdings", expanded=False):
        st.caption("Enter your quantities. The dashboard will show your top 10 holdings by value.")

        symbols = list(STOCK_MAP.keys())

        for i in range(0, len(symbols), 3):
            cols = st.columns(3)

            for j, col in enumerate(cols):
                if i + j < len(symbols):
                    sym = symbols[i + j]

                    with col:
                        holdings[sym] = st.number_input(
                            sym,
                            value=float(holdings.get(sym, 0.0)),
                            step=1.0,
                            key=f"stock_qty_{sym}"
                        )

        cash = st.number_input(
            f"Cash ({currency_code})",
            value=float(cash),
            step=10.0,
            key="stock_cash_input"
        )

        if st.button("💾 Save Stock Holdings"):
            save_stock_holdings(user_id, holdings)
            save_setting(user_id, "stock_cash", cash)
            st.success("Stock holdings saved")

    try:
        prices = stock_live_prices(list(STOCK_MAP.keys())) or {}
    except Exception:
        prices = {}

    rows = []
    total_value = cash
    data_degraded = False
    failed_assets = []

    value_col = f"Value ({currency_code})"

    for sym, qty in holdings.items():
        raw = prices.get(sym, 0.0)
        price, ok = safe_price(sym, raw)

        if price is None:
            data_degraded = True
            failed_assets.append(sym)
            continue

        if not ok:
            data_degraded = True
            failed_assets.append(sym)

        value = price * qty * rate
        total_value += value

        rows.append([
            sym,
            qty,
            price,
            round(value, 2)
        ])

    last_good = get_last_good_value()

    if total_value > 0 and not data_degraded:
        set_last_good_value(total_value)

    elif last_good is not None:
        total_value = last_good

    if failed_assets:
        st.warning(
            "Some stock prices could not be refreshed live: "
            + ", ".join(failed_assets)
            + ". Cached prices are being used."
        )

    if cash > 0:
        rows.append(["CASH", "-", "-", round(cash, 2)])

    df = pd.DataFrame(
        rows,
        columns=["Asset", "Qty", "Price (USD)", value_col]
    )

    df[value_col] = pd.to_numeric(df[value_col], errors="coerce").fillna(0.0)

    top_df = (
        df[df[value_col] > 0]
        .sort_values(value_col, ascending=False)
        .head(10)
    )

    pnl = total_value - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    st.subheader("📊 Overview")

    top1, top2, top3 = st.columns(3)

    top1.metric("Portfolio Value", fmt(total_value, selected_currency))
    top2.metric("Invested", fmt(invested, selected_currency))
    top3.metric("PnL", fmt(pnl, selected_currency), metric_delta(pnl_pct))

    history = clean_history(load_portfolio_history(user_id))

    mtd_pnl = ytd_pnl = 0.0
    mtd_pct = ytd_pct = 0.0

    if not history.empty:
        now = datetime.utcnow()

        mtd = history[
            (history["timestamp"].dt.month == now.month) &
            (history["timestamp"].dt.year == now.year)
        ]

        ytd = history[
            history["timestamp"].dt.year == now.year
        ]

        if not mtd.empty:
            start = mtd.iloc[0]["value_ghs"]

            if start > 0:
                mtd_pnl = total_value - start
                mtd_pct = (mtd_pnl / start) * 100

        if not ytd.empty:
            start = ytd.iloc[0]["value_ghs"]

            if start > 0:
                ytd_pnl = total_value - start
                ytd_pct = (ytd_pnl / start) * 100

    bottom1, bottom2 = st.columns(2)

    bottom1.metric("MTD", fmt(mtd_pnl, selected_currency), metric_delta(mtd_pct))
    bottom2.metric("YTD", fmt(ytd_pnl, selected_currency), metric_delta(ytd_pct))

    st.markdown("---")

    st.subheader("🏆 Top 10 Stock Holdings")

    if top_df.empty:
        st.info("No stock holdings entered yet.")
    else:
        st.dataframe(top_df, use_container_width=True)

    with st.expander("📂 View All Stock Assets"):
        st.dataframe(
            df.sort_values(value_col, ascending=False),
            use_container_width=True
        )

    st.subheader("Portfolio Trend")

    if len(history) >= 2:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=history["timestamp"],
            y=history["value_ghs"],
            mode="lines",
            fill="tozeroy",
            line=dict(
                shape="spline",
                smoothing=1.2,
                width=3
            ),
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified",
            yaxis_title=f"Value ({currency_code})"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.subheader("All-Time PnL Curve")

    pnl_df = build_pnl(history, invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(
                shape="spline",
                smoothing=1.2,
                width=3
            ),
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            margin=dict(l=10, r=10, b=10, t=10),
            hovermode="x unified",
            yaxis_title=f"PnL ({currency_code})"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    st.subheader("Allocation")

    if not top_df.empty:
        pie_df = top_df.copy()

        total_allocation = pie_df[value_col].sum()

        if total_allocation > 0:
            pie_df["Allocation %"] = (
                pie_df[value_col] / total_allocation * 100
            ).round(2)

            pie_df["Asset Share"] = (
                pie_df["Asset"]
                + " — "
                + pie_df["Allocation %"].astype(str)
                + "%"
            )

            pie = alt.Chart(pie_df).mark_arc().encode(
                theta=alt.Theta(
                    field=value_col,
                    type="quantitative"
                ),
                color=alt.Color(
                    field="Asset Share",
                    type="nominal",
                    title="Asset"
                ),
                tooltip=[
                    alt.Tooltip("Asset:N", title="Asset"),
                    alt.Tooltip("Qty:Q", title="Quantity"),
                    alt.Tooltip("Price (USD):Q", title="Price USD", format=",.4f"),
                    alt.Tooltip(f"{value_col}:Q", title=value_col, format=",.2f"),
                    alt.Tooltip("Allocation %:Q", title="Allocation %", format=".2f"),
                ],
            )

            st.altair_chart(pie, use_container_width=True)

    if total_value > 0 and not data_degraded:
        autosave_portfolio_value(
            user_id,
            total_value,
            "stock"
        )

    if st.button("Save Snapshot"):
        if total_value > 0 and not data_degraded:
            force_snapshot(
                user_id,
                total_value
            )
