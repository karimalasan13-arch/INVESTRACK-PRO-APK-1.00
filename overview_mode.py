from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import get_supabase
from portfolio_tracker import autosave_portfolio_value, manual_snapshot
from price_history import crypto_live_prices, stock_live_prices

from crypto_mode import API_MAP, load_crypto_holdings
from stock_mode import STOCK_MAP, load_stock_holdings
from etf_mode import ETF_MAP, load_etf_holdings
from bond_mode import load_bond_holdings


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
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
}

DONUT_CONFIG = {
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


def fmt(value, currency):
    return f'{currency["symbol"]} {float(value):,.2f}'


def pct_delta(value):
    if value > 0:
        return f"+{value:.2f}%"
    if value < 0:
        return f"-{abs(value):.2f}%"
    return "0.00%"


def to_master(value, source_usd_rate, master_usd_rate):
    """
    Convert a value expressed in a module's display/native currency
    into the unified Overview reporting currency.

    Both rates follow the app convention: USD 1 = X currency units.
    """
    value = float(value or 0.0)
    source_rate = float(source_usd_rate or 0.0)
    master_rate = float(master_usd_rate or 0.0)

    if source_rate <= 0 or master_rate <= 0:
        return 0.0

    return (value / source_rate) * master_rate


def load_overview_history(user_id):
    try:
        res = (
            db()
            .table("portfolio_history")
            .select("timestamp,value_ghs")
            .eq("user_id", user_id)
            .eq("mode", "overview")
            .order("timestamp")
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def clean_history(history):
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["value_ghs"] = pd.to_numeric(df["value_ghs"], errors="coerce")
    return df.dropna().sort_values("timestamp")


def safe_price(memory_key, symbol, raw_price):
    if memory_key not in st.session_state:
        st.session_state[memory_key] = {}

    memory = st.session_state[memory_key]

    try:
        price = float(raw_price or 0.0)
    except Exception:
        price = 0.0

    if price > 0:
        memory[symbol] = price
        return price, True

    cached = memory.get(symbol)
    if cached is not None and cached > 0:
        return float(cached), False

    return None, False


def get_market_prices():
    try:
        crypto_prices = crypto_live_prices() or {}
    except Exception:
        crypto_prices = {}

    try:
        stock_prices = stock_live_prices(list(STOCK_MAP.keys())) or {}
    except Exception:
        stock_prices = {}

    try:
        etf_prices = stock_live_prices(list(ETF_MAP.keys())) or {}
    except Exception:
        etf_prices = {}

    return crypto_prices, stock_prices, etf_prices


def build_asset_class_donut(class_df, currency):
    chart_df = class_df[class_df["Value"] > 0].copy()

    if chart_df.empty:
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=chart_df["Asset Class"],
                values=chart_df["Value"],
                hole=0.68,
                sort=False,
                textinfo="none",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    f"Value: {currency['symbol']} %{{value:,.2f}}<br>"
                    "Allocation: %{percent}<extra></extra>"
                ),
            )
        ]
    )

    fig.update_layout(
        height=390,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
        ),
        annotations=[
            dict(
                text="Portfolio",
                x=0.5,
                y=0.5,
                font=dict(size=21),
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
        config=DONUT_CONFIG,
    )


def overview_app():
    st.title("Unified Portfolio Overview")
    st.caption(
        "One view across Crypto, Stocks, ETFs and Bonds / Fixed Income."
    )

    if "user_id" not in st.session_state:
        st.error("User not logged in.")
        return

    user_id = st.session_state.user_id

    # ---------------------------------------------------------
    # MASTER REPORTING CURRENCY
    # ---------------------------------------------------------
    master_index = int(load_setting(user_id, "overview_currency_index", 0))
    if not 0 <= master_index < len(CURRENCY_OPTIONS):
        master_index = 0

    master_currency = CURRENCY_OPTIONS[master_index]
    default_master_rate = 14.5 if master_currency["code"] == "GHS" else 1.0
    master_rate = load_setting(user_id, "overview_rate", default_master_rate)

    st.sidebar.header("🌐 Unified Overview")

    labels = [currency_label(c) for c in CURRENCY_OPTIONS]
    selected_label = st.sidebar.selectbox(
        "Master Reporting Currency",
        labels,
        index=master_index,
        key="overview_currency",
    )

    selected_index = labels.index(selected_label)
    master_currency = CURRENCY_OPTIONS[selected_index]
    master_code = master_currency["code"]

    master_rate = st.sidebar.number_input(
        f"USD → {master_code}",
        min_value=0.000001,
        value=float(master_rate),
        step=0.1 if float(master_rate) >= 1 else 0.01,
        format="%.6f",
        key="overview_rate_input",
    )

    if st.sidebar.button(
        "💾 Save Overview Settings",
        key="save_overview_settings",
    ):
        save_setting(user_id, "overview_currency_index", selected_index)
        save_setting(user_id, "overview_rate", master_rate)
        st.sidebar.success("Overview settings saved")

    st.sidebar.caption(
        "The Overview converts every asset class into this single "
        "reporting currency before combining totals."
    )

    # ---------------------------------------------------------
    # MODULE SETTINGS
    # ---------------------------------------------------------
    crypto_rate = load_setting(user_id, "crypto_rate", 14.5)
    crypto_invested = load_setting(user_id, "crypto_investment", 0.0)

    stock_rate = load_setting(user_id, "stock_rate", 14.5)
    stock_invested = load_setting(user_id, "stock_investment", 0.0)
    stock_cash = load_setting(user_id, "stock_cash", 0.0)

    etf_rate = load_setting(user_id, "etf_rate", 14.5)
    etf_invested = load_setting(user_id, "etf_investment", 0.0)
    etf_cash = load_setting(user_id, "etf_cash", 0.0)

    bond_display_rate = load_setting(user_id, "bond_rate", 14.5)
    bond_cash = load_setting(user_id, "bond_cash", 0.0)

    # ---------------------------------------------------------
    # HOLDINGS + LIVE PRICES
    # ---------------------------------------------------------
    crypto_holdings = load_crypto_holdings(user_id)
    stock_holdings = load_stock_holdings(user_id)
    etf_holdings = load_etf_holdings(user_id)
    bond_holdings = load_bond_holdings(user_id)

    crypto_prices, stock_prices, etf_prices = get_market_prices()

    holding_rows = []
    failed_assets = []

    crypto_value = 0.0
    stock_security_value = 0.0
    etf_security_value = 0.0
    bond_security_value = 0.0
    bond_invested = 0.0
    bond_income = 0.0

    # Crypto
    for symbol, qty in crypto_holdings.items():
        if float(qty or 0.0) <= 0:
            continue

        raw = crypto_prices.get(
            symbol,
            1.0 if symbol in ["USDT", "USDC", "DAI"] else 0.0,
        )
        price, live = safe_price(
            "overview_crypto_price_memory",
            symbol,
            raw,
        )

        if price is None:
            failed_assets.append(f"Crypto {symbol}")
            continue

        value = float(qty) * price * master_rate
        crypto_value += value

        holding_rows.append({
            "Holding": symbol,
            "Asset Class": "Crypto",
            "Value": value,
            "Live": live,
        })

    # Stocks
    for symbol, qty in stock_holdings.items():
        if float(qty or 0.0) <= 0:
            continue

        price, live = safe_price(
            "overview_stock_price_memory",
            symbol,
            stock_prices.get(symbol, 0.0),
        )

        if price is None:
            failed_assets.append(f"Stock {symbol}")
            continue

        value = float(qty) * price * master_rate
        stock_security_value += value

        holding_rows.append({
            "Holding": symbol,
            "Asset Class": "Stocks",
            "Value": value,
            "Live": live,
        })

    # ETFs
    for symbol, qty in etf_holdings.items():
        if float(qty or 0.0) <= 0:
            continue

        price, live = safe_price(
            "overview_etf_price_memory",
            symbol,
            etf_prices.get(symbol, 0.0),
        )

        if price is None:
            failed_assets.append(f"ETF {symbol}")
            continue

        value = float(qty) * price * master_rate
        etf_security_value += value

        holding_rows.append({
            "Holding": symbol,
            "Asset Class": "ETFs",
            "Value": value,
            "Live": live,
        })

    # Bonds / fixed income
    for holding in bond_holdings:
        native_rate = float(holding.get("usd_to_native_rate") or 0.0)
        current_native = float(holding.get("current_value") or 0.0)
        purchase_native = float(holding.get("purchase_value") or 0.0)
        income_native = float(holding.get("income_received") or 0.0)

        current_master = to_master(
            current_native,
            native_rate,
            master_rate,
        )
        purchase_master = to_master(
            purchase_native,
            native_rate,
            master_rate,
        )
        income_master = to_master(
            income_native,
            native_rate,
            master_rate,
        )

        bond_security_value += current_master
        bond_invested += purchase_master
        bond_income += income_master

        if current_master > 0:
            holding_rows.append({
                "Holding": holding.get("name") or "Fixed Income",
                "Asset Class": "Bonds",
                "Value": current_master,
                "Live": True,
            })

    # Cash is stored in each module's own display currency.
    stock_cash_master = to_master(stock_cash, stock_rate, master_rate)
    etf_cash_master = to_master(etf_cash, etf_rate, master_rate)
    bond_cash_master = to_master(
        bond_cash,
        bond_display_rate,
        master_rate,
    )
    total_cash = (
        stock_cash_master
        + etf_cash_master
        + bond_cash_master
    )

    if total_cash > 0:
        holding_rows.append({
            "Holding": "Cash",
            "Asset Class": "Cash",
            "Value": total_cash,
            "Live": True,
        })

    # Current asset-class values.
    stock_value = stock_security_value + stock_cash_master
    etf_value = etf_security_value + etf_cash_master
    bond_value = bond_security_value + bond_cash_master

    total_value = (
        crypto_value
        + stock_value
        + etf_value
        + bond_value
    )

    # Normalize each module's user-entered invested capital.
    crypto_invested_master = to_master(
        crypto_invested,
        crypto_rate,
        master_rate,
    )
    stock_invested_master = to_master(
        stock_invested,
        stock_rate,
        master_rate,
    )
    etf_invested_master = to_master(
        etf_invested,
        etf_rate,
        master_rate,
    )

    total_invested = (
        crypto_invested_master
        + stock_invested_master
        + etf_invested_master
        + bond_invested
    )

    # Bond income is cash already received from the investment, so include
    # it in total-return calculations without double-counting it as value.
    total_return = total_value + bond_income - total_invested
    total_return_pct = (
        total_return / total_invested * 100
        if total_invested > 0
        else 0.0
    )

    # ---------------------------------------------------------
    # HEADLINE METRICS
    # ---------------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Total Portfolio Value",
        fmt(total_value, master_currency),
    )
    m2.metric(
        "Total Invested",
        fmt(total_invested, master_currency),
    )
    m3.metric(
        "Total Return",
        fmt(total_return, master_currency),
        pct_delta(total_return_pct),
    )
    m4.metric(
        "Total Cash",
        fmt(total_cash, master_currency),
    )

    if failed_assets:
        st.warning(
            "Some live prices are temporarily unavailable: "
            + ", ".join(failed_assets[:10])
            + ("…" if len(failed_assets) > 10 else "")
            + ". Those assets are excluded until a live or cached price is available."
        )

    # ---------------------------------------------------------
    # ASSET-CLASS CARDS + ALLOCATION
    # ---------------------------------------------------------
    class_rows = [
        {"Asset Class": "Crypto", "Value": crypto_value},
        {"Asset Class": "Stocks", "Value": stock_security_value},
        {"Asset Class": "ETFs", "Value": etf_security_value},
        {"Asset Class": "Bonds", "Value": bond_security_value},
        {"Asset Class": "Cash", "Value": total_cash},
    ]
    class_df = pd.DataFrame(class_rows)

    st.markdown("---")
    st.subheader("Asset-Class Breakdown")

    card1, card2, card3, card4 = st.columns(4)

    card_data = [
        ("Crypto", crypto_value, crypto_invested_master),
        ("Stocks", stock_value, stock_invested_master),
        ("ETFs", etf_value, etf_invested_master),
        (
            "Bonds",
            bond_value,
            bond_invested,
        ),
    ]

    for col, (label, value, invested) in zip(
        [card1, card2, card3, card4],
        card_data,
    ):
        allocation = (
            value / total_value * 100
            if total_value > 0
            else 0.0
        )
        class_return = (
            value - invested
            if label != "Bonds"
            else value + bond_income - invested
        )

        col.metric(
            label,
            fmt(value, master_currency),
            f"{allocation:.1f}% of portfolio",
        )
        col.caption(
            f"Return: {fmt(class_return, master_currency)}"
        )

    left, right = st.columns([1.15, 1])

    with left:
        st.subheader("Portfolio Allocation")
        build_asset_class_donut(class_df, master_currency)

    # ---------------------------------------------------------
    # PORTFOLIO HEALTH
    # ---------------------------------------------------------
    holdings_df = pd.DataFrame(holding_rows)

    with right:
        st.subheader("Portfolio Health")

        positive_holdings = (
            holdings_df[holdings_df["Value"] > 0].copy()
            if not holdings_df.empty
            else pd.DataFrame()
        )

        non_cash = (
            positive_holdings[
                positive_holdings["Asset Class"] != "Cash"
            ].copy()
            if not positive_holdings.empty
            else pd.DataFrame()
        )

        if not non_cash.empty:
            largest = non_cash.sort_values(
                "Value",
                ascending=False,
            ).iloc[0]
            largest_pct = (
                largest["Value"] / total_value * 100
                if total_value > 0
                else 0.0
            )
            st.metric(
                "Largest Holding",
                str(largest["Holding"]),
                f"{largest_pct:.1f}% of portfolio",
            )
        else:
            st.metric("Largest Holding", "—")

        largest_class_df = class_df[
            class_df["Asset Class"] != "Cash"
        ].sort_values("Value", ascending=False)

        if not largest_class_df.empty and total_value > 0:
            largest_class = largest_class_df.iloc[0]
            st.metric(
                "Largest Asset Class",
                str(largest_class["Asset Class"]),
                f"{largest_class['Value'] / total_value * 100:.1f}% of portfolio",
            )

        h1, h2 = st.columns(2)
        h1.metric(
            "Tracked Holdings",
            int(len(non_cash)) if not non_cash.empty else 0,
        )
        h2.metric(
            "Cash Allocation",
            (
                f"{total_cash / total_value * 100:.1f}%"
                if total_value > 0
                else "0.0%"
            ),
        )

        if not non_cash.empty and total_value > 0:
            concentration = (
                non_cash["Value"].max() / total_value * 100
            )
            if concentration >= 30:
                st.info(
                    "Concentration note: one holding represents "
                    f"{concentration:.1f}% of the total portfolio."
                )

    # ---------------------------------------------------------
    # TOP HOLDINGS
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("Top Holdings Across Your Portfolio")

    if holdings_df.empty:
        st.info(
            "Add holdings in Crypto, Stocks, ETFs or Bonds to build "
            "your unified portfolio."
        )
    else:
        display_df = holdings_df[
            holdings_df["Value"] > 0
        ].copy()

        if not display_df.empty:
            display_df["Allocation %"] = (
                display_df["Value"] / total_value * 100
                if total_value > 0
                else 0.0
            )
            display_df["Value"] = display_df["Value"].round(2)
            display_df["Allocation %"] = (
                display_df["Allocation %"].round(2)
            )
            display_df = display_df.sort_values(
                "Value",
                ascending=False,
            ).head(10)

            display_df = display_df.rename(
                columns={"Value": f"Value ({master_code})"}
            )

            st.dataframe(
                display_df[
                    [
                        "Holding",
                        "Asset Class",
                        f"Value ({master_code})",
                        "Allocation %",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    # ---------------------------------------------------------
    # UNIFIED HISTORY
    # Dedicated Overview snapshots avoid mixing old module histories
    # that may have been recorded in different display currencies.
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("Unified Portfolio Trend")

    history = clean_history(load_overview_history(user_id))

    if len(history) >= 2:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=history["timestamp"],
                y=history["value_ghs"],
                mode="lines",
                fill="tozeroy",
                line=dict(
                    shape="spline",
                    smoothing=1.15,
                    width=3,
                ),
                hovertemplate=(
                    f'{master_currency["symbol"]} '
                    "%{y:,.2f}<extra></extra>"
                ),
            )
        )
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode="x unified",
            yaxis_title=f"Value ({master_code})",
            dragmode="pan",
            uirevision="unified_portfolio_trend",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config=PLOTLY_CHART_CONFIG,
        )
    else:
        st.caption(
            "The unified trend will appear after at least two Overview "
            "snapshots. Existing asset-class histories remain untouched."
        )

    snap_col, note_col = st.columns([1, 3])

    with snap_col:
        if st.button(
            "📸 Save Unified Snapshot",
            key="overview_manual_snapshot",
            use_container_width=True,
        ):
            if total_value > 0:
                if manual_snapshot(
                    user_id,
                    total_value,
                    "overview",
                ):
                    st.success("Unified snapshot saved.")
                    st.rerun()
                else:
                    st.error("Snapshot could not be saved.")
            else:
                st.warning(
                    "A positive portfolio value is required."
                )

    with note_col:
        st.caption(
            "Unified history starts from this release. This is deliberate: "
            "older module snapshots may have been stored under different "
            "display currencies, so they are not mixed into one misleading chart."
        )

    # Only autosave when every held market-priced asset was successfully
    # valued. This prevents temporary API failures from creating false drops.
    if total_value > 0 and not failed_assets:
        autosave_portfolio_value(
            user_id,
            total_value,
            "overview",
        )

    st.markdown(
        """
        <div style="
            border-left:4px solid #84cc16;
            background:rgba(132,204,22,.08);
            border-radius:10px;
            padding:.9rem 1rem;
            margin:1rem 0;
        ">
            <strong>Unified valuation note:</strong>
            The Overview combines the values already tracked in your
            individual asset dashboards. Market prices can be delayed,
            and manually entered bond values and exchange rates remain
            user-controlled.
        </div>
        """,
        unsafe_allow_html=True,
    )
