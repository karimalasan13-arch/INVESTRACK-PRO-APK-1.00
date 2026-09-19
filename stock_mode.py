import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

from price_history import stock_live_prices
from portfolio_tracker import autosave_portfolio_value
from db import get_supabase


STOCK_MAP = {
    "NVDA": "NVDA", "AAPL": "AAPL", "GOOGL": "GOOGL", "GOOG": "GOOG",
    "MSFT": "MSFT", "AMZN": "AMZN", "META": "META", "AVGO": "AVGO",
    "TSLA": "TSLA", "BRK-B": "BRK-B", "TSM": "TSM", "LLY": "LLY",
    "JPM": "JPM", "WMT": "WMT", "V": "V", "MA": "MA", "NFLX": "NFLX",
    "ORCL": "ORCL", "XOM": "XOM", "COST": "COST", "JNJ": "JNJ",
    "HD": "HD", "PG": "PG", "BAC": "BAC", "ABBV": "ABBV",
    "KO": "KO", "PLTR": "PLTR", "ASML": "ASML", "SAP": "SAP",
    "UNH": "UNH", "AMD": "AMD", "CRM": "CRM", "CSCO": "CSCO",
    "CVX": "CVX", "IBM": "IBM", "GE": "GE", "WFC": "WFC",
    "TMUS": "TMUS", "NOW": "NOW", "MCD": "MCD", "PM": "PM",
    "ABT": "ABT", "LIN": "LIN", "DIS": "DIS", "MRK": "MRK",
    "ISRG": "ISRG", "INTU": "INTU", "GS": "GS", "CAT": "CAT",
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
    return idx if 0 <= idx < len(CURRENCY_OPTIONS) else 0


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

    if v < 0:
        return f"-{abs(v):.2f}%"

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




def render_performance_trend(history_df, current_value, currency, currency_code, uirevision):
    """Render a Robinhood-style portfolio performance chart with range controls."""
    if history_df is None or len(history_df) < 2:
        return False

    h = history_df.copy()
    h["timestamp"] = pd.to_datetime(h["timestamp"], errors="coerce")
    h["value_ghs"] = pd.to_numeric(h["value_ghs"], errors="coerce")
    h = h.dropna(subset=["timestamp", "value_ghs"]).sort_values("timestamp")
    h = h.drop_duplicates(subset=["timestamp"], keep="last")

    if len(h) < 2:
        return False

    # Keep the chart anchored to the live value even when the most recent
    # autosave/snapshot predates the current dashboard refresh.
    now = pd.Timestamp.now(tz=None)
    last_ts = h["timestamp"].iloc[-1]
    if getattr(last_ts, "tzinfo", None) is not None:
        now = pd.Timestamp.now(tz=last_ts.tzinfo)

    live_row = pd.DataFrame({
        "timestamp": [now],
        "value_ghs": [float(current_value)],
    })
    h = pd.concat([h[["timestamp", "value_ghs"]], live_row], ignore_index=True)
    h = h.dropna().sort_values("timestamp")

    end = h["timestamp"].iloc[-1]
    ranges = [
        ("1W", end - pd.Timedelta(days=7)),
        ("1M", end - pd.DateOffset(months=1)),
        ("3M", end - pd.DateOffset(months=3)),
        ("YTD", pd.Timestamp(year=end.year, month=1, day=1, tz=end.tz)),
        ("1Y", end - pd.DateOffset(years=1)),
        ("ALL", None),
    ]

    symbol = currency["symbol"]
    fig = go.Figure()
    period_frames = []
    period_meta = []

    for label, cutoff in ranges:
        period = h.copy() if cutoff is None else h[h["timestamp"] >= cutoff].copy()

        # If the selected period contains only the live point, include the
        # immediately preceding observation so the user still sees a change.
        if len(period) < 2 and cutoff is not None:
            earlier = h[h["timestamp"] < cutoff].tail(1)
            period = pd.concat([earlier, period], ignore_index=True).sort_values("timestamp")

        if period.empty:
            period = h.tail(1).copy()

        start_value = float(period["value_ghs"].iloc[0])
        end_value = float(period["value_ghs"].iloc[-1])
        change = end_value - start_value
        change_pct = (change / start_value * 100.0) if start_value else 0.0
        positive = change >= 0
        line_color = "#22c55e" if positive else "#ef4444"
        fill_color = "rgba(34,197,94,0.16)" if positive else "rgba(239,68,68,0.14)"

        period_frames.append(period)
        period_meta.append((label, end_value, change, change_pct, line_color, fill_color))

        fig.add_trace(go.Scatter(
            x=period["timestamp"],
            y=period["value_ghs"],
            mode="lines",
            visible=False,
            line=dict(color=line_color, width=3, shape="spline", smoothing=0.85),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate=(
                "%{x|%d %b %Y}<br>"
                + f"{symbol} %{{y:,.2f}}<extra></extra>"
            ),
        ))

    # Default to 1Y, matching the reference design.
    default_idx = 4
    fig.data[default_idx].visible = True

    def annotations_for(idx):
        label, end_value, change, change_pct, line_color, _ = period_meta[idx]
        arrow = "▲" if change >= 0 else "▼"
        sign = "+" if change >= 0 else "-"
        return [
            dict(
                x=0, y=1.18, xref="paper", yref="paper",
                text=f"<b>{symbol}{end_value:,.2f}</b>",
                showarrow=False, xanchor="left", yanchor="top",
                font=dict(size=30, color="#f8fafc"),
            ),
            dict(
                x=0, y=1.07, xref="paper", yref="paper",
                text=(
                    f"<b>{arrow} {sign}{symbol}{abs(change):,.2f} "
                    f"({sign}{abs(change_pct):.2f}%) · {label}</b>"
                ),
                showarrow=False, xanchor="left", yanchor="top",
                font=dict(size=15, color=line_color),
            ),
        ]

    buttons = []
    for idx, (label, *_rest) in enumerate(period_meta):
        visible = [False] * len(period_meta)
        visible[idx] = True
        buttons.append(dict(
            label=f"<b>{label}</b>",
            method="update",
            args=[
                {"visible": visible},
                {"annotations": annotations_for(idx)},
            ],
        ))

    fig.update_layout(
        height=500,
        margin=dict(l=8, r=18, t=105, b=78),
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        hovermode="x",
        showlegend=False,
        dragmode=False,
        uirevision=uirevision,
        annotations=annotations_for(default_idx),
        updatemenus=[dict(
            type="buttons",
            direction="right",
            active=default_idx,
            x=0.0,
            xanchor="left",
            y=-0.14,
            yanchor="top",
            pad=dict(r=6, t=4),
            bgcolor="#111827",
            bordercolor="#273244",
            borderwidth=1,
            font=dict(size=13, color="#22c55e"),
            buttons=buttons,
        )],
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            fixedrange=True,
        ),
        yaxis=dict(
            side="right",
            showgrid=True,
            gridcolor="rgba(148,163,184,0.22)",
            griddash="dot",
            zeroline=False,
            tickformat="~s",
            tickfont=dict(color="#a7adb8", size=12),
            fixedrange=True,
            rangemode="tozero",
            nticks=5,
        ),
        hoverlabel=dict(
            bgcolor="#111827",
            bordercolor="#334155",
            font=dict(color="#f8fafc"),
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "displaylogo": False,
            "responsive": True,
        },
    )
    return True


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

        rows.append([sym, qty, price, round(value, 2)])

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
            (history["timestamp"].dt.month == now.month)
            & (history["timestamp"].dt.year == now.year)
        ]

        ytd = history[history["timestamp"].dt.year == now.year]

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

    if not render_performance_trend(
        history,
        total_value,
        selected_currency,
        currency_code,
        "stock_portfolio_trend",
    ):
        st.caption("Portfolio trend will appear after at least two snapshots.")

    st.subheader("All-Time PnL Curve")

    pnl_df = build_pnl(history, invested)

    if len(pnl_df) >= 2:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=pnl_df["timestamp"],
            y=pnl_df["pnl"],
            mode="lines",
            line=dict(shape="spline", smoothing=1.2, width=3),
            hovertemplate=f'{selected_currency["symbol"]} %{{y:,.2f}}<extra></extra>'
        ))

        fig.update_layout(
            margin=dict(l=10, r=10, b=10, t=10),
            hovermode="x unified",
            yaxis_title=f"PnL ({currency_code})",
            dragmode="pan",
            uirevision="stock_pnl_curve"
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config=PLOTLY_CHART_CONFIG
        )

    st.markdown("---")

    st.subheader("Allocation")

    donut_df = build_donut_df(top_df, value_col)
    render_donut_chart(donut_df, value_col, selected_currency)

    if total_value > 0 and not data_degraded:
        autosave_portfolio_value(user_id, total_value, "stock")

    if st.button("Save Snapshot"):
        if total_value > 0 and not data_degraded:
            force_snapshot(user_id, total_value)
