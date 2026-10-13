"""Shared, presentation-only historical charts for InvesTrack Pro."""
from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PERIODS = ("24H", "7D", "30D", "90D", "1Y", "ALL")
CHART_CONFIG = {"displaylogo": False, "scrollZoom": False, "responsive": True,
                "modeBarButtonsToRemove": ["select2d", "lasso2d"]}

def _history_frame(history):
    if isinstance(history, pd.DataFrame):
        df = history.copy()
    else:
        df = pd.DataFrame(history or [])
    if df.empty or not {"timestamp", "value_ghs"}.issubset(df.columns):
        return pd.DataFrame(columns=["timestamp", "value_ghs"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["value_ghs"] = pd.to_numeric(df["value_ghs"], errors="coerce")
    return df.dropna(subset=["timestamp", "value_ghs"]).sort_values("timestamp")

def _filter(df, period):
    if period == "ALL" or df.empty:
        return df
    hours = {"24H":24, "7D":168, "30D":720, "90D":2160, "1Y":8760}[period]
    now = pd.Timestamp.now(tz="UTC")
    return df.loc[df["timestamp"] >= now - pd.Timedelta(hours=hours)]

def render_portfolio_charts(history, *, mode, currency_symbol, currency_code,
                            invested=None, pnl_title="Cumulative P&L"):
    """Render value and optional P&L charts from genuine stored observations.

    `invested` is a CURRENT cost basis. Historical P&L derived from it is only
    indicative if holdings or cash contributions changed during the period.
    """
    df = _history_frame(history)
    period = st.radio("Chart period", PERIODS, index=5, horizontal=True,
                      key=f"iv_chart_period_{mode}")
    visible = _filter(df, period)
    if len(visible) < 2:
        st.info("Not enough recorded snapshots for this period yet. Try ALL, or allow more observations to accumulate.")
        return
    def draw(title, values, color, *, fill=False):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=visible["timestamp"], y=values, mode="lines",
            line={"shape":"spline", "smoothing":0.65, "width":2.6, "color":color},
            fill="tozeroy" if fill else None,
            fillcolor="rgba(45, 212, 191, 0.09)" if fill else None,
            hovertemplate="%{x|%d %b %Y, %H:%M UTC}<br>" + currency_symbol + " %{y:,.2f}<extra></extra>",
            name=title))
        fig.update_layout(
            title={"text":title, "font":{"size":16, "color":"#F1F5F9"}},
            height=310, margin={"l":12,"r":12,"t":48,"b":18},
            paper_bgcolor="#1D2333", plot_bgcolor="#1D2333",
            font={"color":"#B8C4D5", "size":11},
            xaxis={"showgrid":False, "zeroline":False, "showline":False},
            yaxis={"gridcolor":"rgba(148,163,184,.17)", "zeroline":False,
                   "tickprefix":currency_symbol + " ", "fixedrange":False},
            hovermode="x", showlegend=False, dragmode="pan",
            uirevision=f"{mode}_{title}_{period}")
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG,
                        key=f"iv_chart_{mode}_{'value' if fill else 'pnl'}")
    draw("Portfolio Value", visible["value_ghs"], "#2DD4BF", fill=True)
    if "pnl" in visible.columns and visible["pnl"].notna().all():
        pnl = visible["pnl"]
    elif invested is not None:
        pnl = visible["value_ghs"] - float(invested)
    else:
        pnl = None
    if pnl is not None:
        draw(pnl_title, pnl, "#34D399" if pnl.iloc[-1] >= 0 else "#FB7185")
        if "pnl" not in visible.columns:
            st.caption("Historical P&L is indicative: it uses the current invested amount. Deposits, withdrawals and cost-basis changes are not reconstructed.")
        else:
            st.caption("Hourly P&L uses invested capital recorded at each snapshot; past currency rates are not reconstructed.")
    st.caption(f"{len(visible):,} actual snapshots • {period} • {currency_code}. Curves smooth the display only; no values are generated between observations.")
