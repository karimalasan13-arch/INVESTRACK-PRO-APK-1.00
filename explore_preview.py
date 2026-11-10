"""Unauthenticated, local-only exploration of InvesTrack Pro.

No Supabase imports, personal-data reads, or persistence. Preview entries are
stored only in the current Streamlit session and are never merged into an account.
"""
from datetime import date
import pandas as pd
import streamlit as st

SAMPLE_CASH = [
    {"Date": "2026-11-01", "Description": "Sample salary", "Type": "Income", "Amount": 4500.0},
    {"Date": "2026-11-03", "Description": "Sample rent", "Type": "Expense", "Amount": 1200.0},
    {"Date": "2026-11-05", "Description": "Sample groceries", "Type": "Expense", "Amount": 420.0},
]
SAMPLE_ASSETS = {
    "Stocks": [("Sample stock A", 1200.0), ("Sample stock B", 850.0)],
    "Crypto": [("Sample BTC holding", 950.0), ("Sample ETH holding", 420.0)],
    "ETFs": [("Sample index ETF", 1750.0)],
    "Bonds": [("Sample government bond", 2000.0)],
}


def _sign_in_to_save(navigate, key):
    st.info("Preview only. Sign in or create an account to save and access your own records.")
    if st.button("Sign in to save", key=key, type="primary"):
        navigate("Login")


def render_cashflow_preview(navigate):
    st.title("💳 Cash Flow")
    st.caption("Explore First · Sample data and temporary entries only · Not saved")
    scope = st.radio("Workspace", ["Personal", "Business"], horizontal=True, key="iv_preview_cash_scope")
    key = "iv_preview_cash_" + scope.lower()
    if key not in st.session_state:
        st.session_state[key] = [dict(item) for item in SAMPLE_CASH]
    records = st.session_state[key]
    income = sum(float(r["Amount"]) for r in records if r["Type"] == "Income")
    expense = sum(float(r["Amount"]) for r in records if r["Type"] == "Expense")
    a, b, c = st.columns(3)
    a.metric("Income (sample)", f"{income:,.2f}")
    b.metric("Expenses (sample)", f"{expense:,.2f}")
    c.metric("Net cash flow (sample)", f"{income-expense:,.2f}")
    st.subheader("Cash flow overview")
    st.bar_chart(pd.DataFrame({"Amount": [income, expense]}, index=["Income", "Expenses"]))
    st.subheader("Transactions")
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    with st.expander("Try adding a transaction (temporary)", expanded=False):
        with st.form("iv_preview_cash_form_" + scope):
            description = st.text_input("Description")
            kind = st.selectbox("Type", ["Expense", "Income"])
            amount = st.number_input("Amount", min_value=0.01, value=100.0, step=10.0)
            submitted = st.form_submit_button("Add to preview")
        if submitted:
            if not description.strip():
                st.warning("Enter a description.")
            else:
                records.append({"Date": date.today().isoformat(), "Description": description.strip(), "Type": kind, "Amount": float(amount)})
                st.rerun()
    if st.button("Reset sample transactions", key="iv_preview_reset_cash_" + scope):
        st.session_state[key] = [dict(item) for item in SAMPLE_CASH]
        st.rerun()
    _sign_in_to_save(navigate, "iv_preview_cash_login")


def render_investment_preview(navigate):
    st.title("📈 Investments")
    st.caption("Explore First · Illustrative portfolio values, not live market quotes · Not saved")
    mode = st.radio("Investment mode", ["Overview", "Crypto", "Stocks", "ETFs", "Bonds"], horizontal=True, key="iv_preview_invest_mode")
    if "iv_preview_assets" not in st.session_state:
        st.session_state.iv_preview_assets = {k: [{"Asset": name, "Value": value} for name, value in items] for k, items in SAMPLE_ASSETS.items()}
    holdings = st.session_state.iv_preview_assets
    if mode == "Overview":
        totals = {k: sum(float(x["Value"]) for x in v) for k, v in holdings.items()}
        st.metric("Illustrative portfolio total", f"{sum(totals.values()):,.2f}")
        st.subheader("Sample allocation")
        st.bar_chart(pd.DataFrame({"Value": totals.values()}, index=list(totals)))
    else:
        records = holdings[mode]
        st.metric("Illustrative value", f"{sum(float(x['Value']) for x in records):,.2f}")
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
        st.bar_chart(pd.DataFrame({"Value": [r["Value"] for r in records]}, index=[r["Asset"] for r in records]))
        with st.expander("Try a sample holding (temporary)"):
            with st.form("iv_preview_asset_form_" + mode):
                name = st.text_input("Asset name or symbol")
                value = st.number_input("Illustrative holding value", min_value=0.01, value=100.0)
                submitted = st.form_submit_button("Add to preview")
            if submitted:
                if name.strip():
                    records.append({"Asset": name.strip(), "Value": float(value)})
                    st.rerun()
                else:
                    st.warning("Enter an asset name.")
    if st.button("Reset sample portfolio", key="iv_preview_reset_invest"):
        st.session_state.iv_preview_assets = {k: [{"Asset": name, "Value": value} for name, value in items] for k, items in SAMPLE_ASSETS.items()}
        st.rerun()
    _sign_in_to_save(navigate, "iv_preview_invest_login")
