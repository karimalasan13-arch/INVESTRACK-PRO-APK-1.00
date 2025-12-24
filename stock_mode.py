from user_session import get_user_id
def stock_app():
    user_id = get_user_id()
    st.title("📊 Stock Portfolio Tracker")
import streamlit as st
import json
import os
import pandas as pd
import altair as alt
from datetime import datetime
from price_history import stock_live_prices
import plotly.graph_objects as go
from portfolio_tracker import load_history as pt_load_history, autosave_portfolio_value

STOCK_FILE = "stock_data.json"
HIST_FILE = "stock_history.json"

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

# ---------------- Helpers ----------------
def load_stock_data():
    default = {"rate": 14.5, "invested": 0, "assets": {}}
    if not os.path.exists(STOCK_FILE):
        return default
    try:
        with open(STOCK_FILE, "r") as f:
            data = json.load(f)
    except:
        return default
    # patch defaults
    for k, v in default.items():
        data.setdefault(k, v)
    # Ensure numeric asset quantities
    assets = data.get("assets", {})
    for s, q in list(assets.items()):
        try:
            assets[s] = float(q)
        except:
            assets[s] = 0.0
    data["assets"] = assets
    return data


def save_stock_data(data):
    with open(STOCK_FILE, "w") as f:
        json.dump(data, f, indent=4)


# local history wrapper to avoid conflict with portfolio_tracker API
def load_local_history():
    if not os.path.exists(HIST_FILE):
        return []
    try:
        with open(HIST_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_local_history(history):
    with open(HIST_FILE, "w") as f:
        json.dump(history, f, indent=4)


def fmt(v): return f"GHS {v:,.2f}"
def pct(v): return f"{v:.2f}%"


# ---------------- Main App ----------------
def stock_app():
    st.title("📊 Stock Portfolio Tracker")

    data = load_stock_data()

    st.sidebar.header("Stock Settings")
    rate = st.sidebar.number_input("Stock Exchange Rate (USD → GHS)",
                                   value=float(data.get("rate", 14.5)), step=0.1)
    invested = st.sidebar.number_input("Total Stock Investment (GHS)",
                                       value=float(data.get("invested", 0.0)), step=10.0)

    data["rate"] = rate
    data["invested"] = invested

    st.sidebar.markdown("---")
    st.sidebar.subheader("Stock Holdings (select and set qty)")

    assets = data.get("assets", {})
    for sym in STOCK_MAP.keys():
        assets.setdefault(sym, 0.0)

    updated = False
    for sym in STOCK_MAP:
        new_qty = st.sidebar.number_input(f"{STOCK_MAP[sym]} ({sym}) quantity",
                                          value=float(assets.get(sym, 0.0)), step=1.0, key=f"stk_{sym}")
        if new_qty != assets.get(sym, 0.0):
            assets[sym] = new_qty
            updated = True

    if st.sidebar.button("Save Holdings"):
        data["assets"] = assets
        save_stock_data(data)
        st.sidebar.success("Stock holdings saved.")
        updated = False

    if st.sidebar.button("Save Settings"):
        save_stock_data(data)
        st.sidebar.success("Settings saved.")

    # Fetch prices only for symbols we might hold (non-zero) to reduce API usage
    symbols_to_fetch = [s for s, q in assets.items() if q and q > 0] or list(STOCK_MAP.keys())
    prices = stock_live_prices(symbols=symbols_to_fetch)  # USD prices dict keyed by ticker like "AAPL","MSFT",...

    rows = []
    total_value_ghs = 0.0
    for sym, qty in assets.items():
        usd_price = prices.get(sym, 0.0)
        try:
            value_usd = float(usd_price) * float(qty)
        except:
            value_usd = 0.0
        value_ghs = value_usd * rate
        total_value_ghs += value_ghs
        rows.append([sym, qty, usd_price, value_usd, value_ghs])

    df = pd.DataFrame(rows, columns=["Symbol", "Qty", "Price (USD)", "Value (USD)", "Value (GHS)"])

    st.subheader("📘 Stock Asset Breakdown")
    if df.empty:
        st.info("No stock holdings yet.")
    else:
        st.dataframe(df, use_container_width=True)

    # All-time PnL
    pnl = total_value_ghs - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # Auto-save via your portfolio_tracker helper (make sure it accepts a numeric value)
    try:
        autosave_portfolio_value(total_value_ghs)
    except Exception:
        # ignore if external autosave not available or errors
        pass

    # Save daily history (one entry per day) - local history
    history = load_local_history()
    today_iso = datetime.utcnow().date().isoformat()
    updated_today = False
    for entry in history:
        if entry.get("timestamp") == today_iso:
            entry["value_ghs"] = total_value_ghs
            updated_today = True
            break
    if not updated_today:
        history.append({"timestamp": today_iso, "value_ghs": total_value_ghs})
    save_local_history(history)

    # Summary UI
    st.markdown("---")
    st.subheader("📈 Portfolio Summary")

    def disp(label, value, small=None):
        st.markdown(f"<div style='font-size:13px;color:#666;margin-bottom:4px'>{label}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:36px;font-weight:700'>{value}</div>", unsafe_allow_html=True)
        if small:
            st.markdown(small, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        disp("Total Value (GHS)", fmt(total_value_ghs))
    with col2:
        disp("Total Invested (GHS)", fmt(invested))
    with col3:
        color = "#0b8f2f" if pnl >= 0 else "#b00020"
        arrow = "↑" if pnl >= 0 else "↓"
        small_html = f"<div style='font-size:16px;color:{color};'>{arrow} {abs(pnl_pct):.2f}%</div>"
        disp("All-Time PnL", f"<span style='color:{color};'>GHS {pnl:,.2f}</span>", small_html)

    # ------------------------------------------------------------
    # 📈 Portfolio Value Line Chart (Plotly: pinch + zoom + pan enabled)
    # ------------------------------------------------------------
    st.markdown("---")
    st.subheader("📈 Portfolio Value Over Time")

    history = load_local_history()

    if len(history) < 2:
        st.info("Portfolio history will appear here as data is collected.")
    else:
        dates = [h.get("timestamp") for h in history]
        values = [h.get("value_ghs", 0.0) for h in history]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=values,
                mode="lines+markers",
                line=dict(color="#00c3ff", width=3),
                marker=dict(size=6),
                hovertemplate="Value: ₵ %{y:,.2f}<br>Date: %{x}<extra></extra>"
            )
        )

        fig.update_layout(
            height=350,
            xaxis_title="Date",
            yaxis_title="Portfolio Value (GHS)",
            hovermode="x unified",
            dragmode="zoom",        # click+drag to zoom
            showlegend=False,
            margin=dict(l=40, r=20, t=20, b=40),
        )

        # Enable touch pinch zoom
        fig.update_xaxes(rangeslider_visible=False)
        fig.update_yaxes(fixedrange=False)

        st.plotly_chart(fig, use_container_width=True)

        # ---- MTD & YTD ----
        st.markdown("---")
        st.subheader("📆 MTD & YTD Performance")

        hist_df = pd.DataFrame(history)
        if not hist_df.empty:
            hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
            hist_df = hist_df.sort_values("timestamp")

            now = datetime.utcnow()
            # MTD
            month_df = hist_df[hist_df["timestamp"].dt.month == now.month]
            if len(month_df) > 0:
                mtd_start = float(month_df.iloc[0].get("value_ghs", 0.0))
                mtd_pnl = total_value_ghs - mtd_start
                mtd_pct = (mtd_pnl / mtd_start * 100) if mtd_start > 0 else 0.0
            else:
                mtd_pnl = mtd_pct = 0.0
            # YTD
            year_df = hist_df[hist_df["timestamp"].dt.year == now.year]
            if len(year_df) > 0:
                ytd_start = float(year_df.iloc[0].get("value_ghs", 0.0))
                ytd_pnl = total_value_ghs - ytd_start
                ytd_pct = (ytd_pnl / ytd_start * 100) if ytd_start > 0 else 0.0
            else:
                ytd_pnl = ytd_pct = 0.0
        else:
            mtd_pnl = ytd_pnl = mtd_pct = ytd_pct = 0.0

        c1, c2 = st.columns(2)
        with c1:
            col = "#0b8f2f" if mtd_pnl >= 0 else "#b00020"
            st.markdown(f"<div style='font-size:28px;font-weight:700;color:{col};'>GHS {mtd_pnl:,.2f}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:14px;color:{col};'>{mtd_pct:.2f}%</div>", unsafe_allow_html=True)
        with c2:
            col = "#0b8f2f" if ytd_pnl >= 0 else "#b00020"
            st.markdown(f"<div style='font-size:28px;font-weight:700;color:{col};'>GHS {ytd_pnl:,.2f}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:14px;color:{col};'>{ytd_pct:.2f}%</div>", unsafe_allow_html=True)

        # ---- Allocation Pie Chart ----
        st.markdown("---")
        st.subheader("🍕 Allocation (by Value)")
        df_pie = df[ df["Value (GHS)"] > 0 ][["Symbol", "Value (GHS)"]].rename(columns={"Symbol":"Asset"})
        if not df_pie.empty:
            pie = alt.Chart(df_pie).mark_arc().encode(
                theta=alt.Theta(field="Value (GHS)", type="quantitative"),
                color=alt.Color("Asset:N"),
                tooltip=["Asset", "Value (GHS)"]
            )
            st.altair_chart(pie, use_container_width=True)
        else:
            st.info("No allocation to show (add holdings).")

        # ---- Candlestick-like chart from daily closes ----
        st.markdown("---")
        st.subheader("🕯️ Portfolio Candlestick (derived from daily closes)")
        st.caption("Note: candlesticks are derived from daily close values: open = previous close, close = today's close, high/low = max/min(open, close). This is NOT intraday OHLC.")

        if len(history) >= 2:
            hist_df = pd.DataFrame(history)
            hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
            hist_df = hist_df.sort_values("timestamp").reset_index(drop=True)
            hist_df["close"] = hist_df["value_ghs"]
            hist_df["open"] = hist_df["close"].shift(1).fillna(hist_df["close"])
            hist_df["high"] = hist_df[["open", "close"]].max(axis=1)
            hist_df["low"] = hist_df[["open", "close"]].min(axis=1)

            base = alt.Chart(hist_df).encode(
                x=alt.X("timestamp:T", axis=alt.Axis(title="Date"))
            )

            rule = base.mark_rule().encode(
                y="low:Q",
                y2="high:Q",
                color=alt.condition("datum.close >= datum.open", alt.value("#0b8f2f"), alt.value("#b00020"))
            )

            bar = base.mark_bar(size=8).encode(
                y="open:Q",
                y2="close:Q",
                color=alt.condition("datum.close >= datum.open", alt.value("#0b8f2f"), alt.value("#b00020")),
                tooltip=[alt.Tooltip("timestamp:T", title="Date"), alt.Tooltip("open:Q"), alt.Tooltip("high:Q"), alt.Tooltip("low:Q"), alt.Tooltip("close:Q")]
            )

            chart = (rule + bar).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Not enough history to show candlestick. Need at least 2 daily entries.")
