import streamlit as st
from dashboard_utils import (
    combined_metrics,
    combined_allocation,
    combined_price_charts,
    combined_mtd_ytd
)

def dashboard_app(rate):
    st.title("📊 InvesTrack Pro — Dashboard Overview")

    col1, col2, col3 = st.columns(3)
    metrics = combined_metrics(rate)
    col1.metric("Total Portfolio Value (GHS)", f"{metrics['total_value']:,.2f}")
    col2.metric("Total Invested (GHS)", f"{metrics['total_invested']:,.2f}")
    col3.metric("All-Time PnL (GHS)", f"{metrics['pnl_all']:,.2f}")

    st.metric("MTD PnL (GHS)", f"{metrics['pnl_mtd']:,.2f}")
    st.metric("YTD PnL (GHS)", f"{metrics['pnl_ytd']:,.2f}")

    st.subheader("Portfolio Allocation")
    combined_allocation(rate)

    st.subheader("Crypto vs Stocks — 60-Day Comparison")
    combined_price_charts()

    st.subheader("MTD / YTD Performance")
    combined_mtd_ytd(rate)
