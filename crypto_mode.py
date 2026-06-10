import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

from price_history import crypto_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


API_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether", "XRP": "ripple",
    "BNB": "binancecoin", "SOL": "solana", "USDC": "usd-coin",
    "DOGE": "dogecoin", "ADA": "cardano", "TRX": "tron",
    "STETH": "staked-ether", "WBTC": "wrapped-bitcoin", "SUI": "sui",
    "LINK": "chainlink", "AVAX": "avalanche-2", "XLM": "stellar",
    "SHIB": "shiba-inu", "BCH": "bitcoin-cash", "HBAR": "hedera-hashgraph",
    "LEO": "leo-token", "LTC": "litecoin", "TON": "the-open-network",
    "DOT": "polkadot", "UNI": "uniswap", "PEPE": "pepe", "APT": "aptos",
    "NEAR": "near", "DAI": "dai", "ICP": "internet-computer",
    "ETC": "ethereum-classic", "OKB": "okb", "KAS": "kaspa",
    "ATOM": "cosmos", "CRO": "crypto-com-chain",
    "POL": "polygon-ecosystem-token", "FIL": "filecoin",
    "ARB": "arbitrum", "VET": "vechain", "ALGO": "algorand",
    "RENDER": "render-token", "FET": "fetch-ai", "OP": "optimism",
    "WIF": "dogwifcoin", "IMX": "immutable-x",
    "INJ": "injective-protocol", "SEI": "sei-network",
    "AAVE": "aave", "GRT": "the-graph", "LDO": "lido-dao",
    "QNT": "quant-network",
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


PLOTLY_CHART_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToAdd": [
        "pan2d",
        "zoomIn2d",
        "zoomOut2d",
        "resetScale2d",
    ],
    "modeBarButtonsToRemove": [
        "select2d",
        "lasso2d",
    ],
}


DONUT_CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
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
    return idx if 0 <= idx < len(CURRENCY_OPTIONS) else 0


def fmt(v, currency):
    return f'{currency["symbol"]} {v:,.2f}'


def build_pnl_history(history, invested):
    if not history:
        return pd.DataFrame()

    h = pd.DataFrame(history)

    if h.empty:
        return pd.DataFrame()

    h["timestamp"] = pd.to_datetime(h["timestamp"], errors="coerce")
    h["value_ghs"] = pd.to_numeric(h["value_ghs"], errors="coerce")
    h = h.dropna().sort_values("timestamp")
    h["pnl"] = h["value_ghs"] - invested

    return h


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
            symbol = r["symbol"]
            if symbol in holdings:
                holdings[symbol] = float(r["quantity"])

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


def metric_delta(value):
    if value > 0:
        return f"{value:.2f}%"

    if value < 0:
        return f"-{abs(value):.2f}%"

    return "0.00%"


def build_donut_df(source_df, value_col, max_slices=7):
    if source_df.empty:
        return pd.DataFrame()

    donut_df = (
        source_df[source_df[value_col] > 0]
        .copy()
        .sort_values(value_col, ascending=False)
    )

    if donut_df.empty:
        return pd.DataFrame()

    if len(donut_df) > max_slices:
        top = donut_df.head(max_slices).copy()
        others_value = donut_df.iloc[max_slices:][value_col].sum()

        if others_value > 0:
            others_row = {
                "Asset": "Others",
                "Qty": "-",
                "Price (USD)": "-",
                value_col: others_value,
            }
            top = pd.concat([top, pd.DataFrame([others_row])], ignore_index=True)

        donut_df = top

    total = donut_df[value_col].sum()

    if total <= 0:
        return pd.DataFrame()

    donut_df["Allocation %"] = (donut_df[value_col] / total * 100).round(2)

    return donut_df


def render_donut_chart(donut_df, value_col, selected_currency):
    if donut_df.empty:
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=donut_df["Asset"],
                values=donut_df[value_col],
                hole=0.68,
                sort=False,
                direction="clockwise",
                textinfo="none",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    f"Value: {selected_currency['symbol']} %{{value:,.2f}}<br>"
                    "Allocation: %{percent}<extra></extra>"
                ),
            )
        ]
    )

    fig.update_layout(
        height=360,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=13),
        ),
        annotations=[
            dict(
                text="100%",
                x=0.5,
                y=0.5,
                font=dict(size=26, color="white"),
                showarrow=False,
            )
        ],
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config=DONUT_CHART_CONFIG
    )


def crypto_app():
    st.title("Crypto Dashboard")

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    currency_index = load_currency_index(user_id, "crypto")
    selected_currency = CURRENCY_OPTIONS[currency_index]

    rate = load_setting(user_id, "crypto_rate", 14.5)
    invested = load_setting(user_id, "crypto_investment", 0.0)
    holdings = load_crypto_holdings(user_id)

    st.sidebar.header("⚙️ Settings")

    currency_labels = [currency_label(c) for c in CURRENCY_OPTIONS]

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
        save_setting(user_id, "crypto_currency_index", selected_index)
        save_setting(user_id, "crypto_rate", rate)
        save_setting(user_id, "crypto_investment", invested)
        st.sidebar.success("Settings saved")

    st.sidebar.caption(
        f"Portfolio values will display in {currency_code}. "
        "Your exchange-rate input controls the conversion."
    )

    st.sidebar.markdown("---")

    with st.expander("⚙️ Manage Crypto Holdings", expanded=False):
        st.caption("Enter your quantities. The dashboard will show your top 10 holdings by value.")

        symbols = list(API_MAP.keys())

        for i in range(0, len(symbols), 3):
            cols = st.columns(3)

            for j, col in enumerate(cols):
                if i + j < len(symbols):
                    sym = symbols[i + j]

                    with col:
                        holdings[sym] = st.number_input(
                            sym,
                            value=float(holdings.get(sym, 0.0)),
                            step=0.0001,
                            key=f"crypto_qty_{sym}"
                        )

        if st.button("💾 Save Crypto Holdings"):
            save_crypto_holdings(user_id, holdings)
            st.success("Crypto holdings saved")

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
            1.0 if sym in ["USDT", "USDC", "DAI"] else 0.0
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
            round(price, 6),
            round(value_display, 2),
        ])

    last_good = get_last_good_value()

    if total_value > 0 and not data_degraded:
        set_last_good_value(total_value)
    elif last_good is not None:
        total_value = last_good

    if failed_assets:
        st.warning(
            "Some prices could not be refreshed live: "
            + ", ".join(failed_assets)
            + ". Cached prices are being used."
        )

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

    history = load_portfolio_history(user_id)

    mtd_pnl = 0.0
    ytd_pnl = 0.0
    mtd_pct = 0.0
    ytd_pct = 0.0

    if history and len(history) >= 2:
        try:
            h = pd.DataFrame(history)
            h["timestamp"] = pd.to_datetime(h["timestamp"], errors="coerce")
            h["value_ghs"] = pd.to_numeric(h["value_ghs"], errors="coerce")
            h = h.dropna().sort_values("timestamp")

            if not h.empty:
                now = datetime.utcnow()

                mtd = h[
                    (h["timestamp"].dt.month == now.month)
                    & (h["timestamp"].dt.year == now.year)
                ]

                ytd = h[h["timestamp"].dt.year == now.year]

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

        except Exception as e:
            print("MTD/YTD error:", e)

    bottom1, bottom2 = st.columns(2)

    bottom1.metric("MTD", fmt(mtd_pnl, selected_currency), metric_delta(mtd_pct))
    bottom2.metric("YTD", fmt(ytd_pnl, selected_currency), metric_delta(ytd_pct))

    st.markdown("---")

    st.subheader("🏆 Top 10 Crypto Holdings")

    if top_df.empty:
        st.info("No crypto holdings entered yet.")
    else:
        st.dataframe(top_df, use_container_width=True)

    with st.expander("📂 View All Crypto Assets"):
        st.dataframe(
            df.sort_values(value_col, ascending=False),
            use_container_width=True
        )

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

    if total_value > 0 and not data_degraded:
        autosave_portfolio_value(user_id, total_value, "crypto")

    st.subheader("📈 Portfolio Trend")

    if len(history) >= 2:
        h = pd.DataFrame(history)
        h["timestamp"] = pd.to_datetime(h["timestamp"], errors="coerce")
        h["value_ghs"] = pd.to_numeric(h["value_ghs"], errors="coerce")
        h = h.dropna()

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=h["timestamp"],
            y=h["value_ghs"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.1, width=3),
            fill="tozeroy",
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            yaxis_title=f"Value ({currency_code})",
            hovermode="x unified",
            dragmode="pan",
            uirevision="crypto_portfolio_trend"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config=PLOTLY_CHART_CONFIG
        )

    else:
        st.info("Waiting for more history data...")

    st.subheader("📊 All-Time PnL Curve")

    pnl_df = build_pnl_history(history, invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.1, width=3),
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            yaxis_title=f"PnL ({currency_code})",
            hovermode="x unified",
            dragmode="pan",
            uirevision="crypto_pnl_curve"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config=PLOTLY_CHART_CONFIG
        )

    else:
        st.info("PnL history will appear soon.")

    st.subheader("Allocation")

    donut_df = build_donut_df(top_df, value_col)
    render_donut_chart(donut_df, value_col, selected_currency)
