import streamlit as st
import pandas as pd
import altair as alt
from pnl_manager import load_investments, load_history, compute_grouped_pnl
from price_history import get_crypto_history, get_stock_history

def combined_metrics(rate):
    return compute_grouped_pnl(rate)

def combined_allocation(rate):
    pnl = compute_grouped_pnl(rate)
    df = pd.DataFrame([
        {"segment": "Crypto", "value": pnl["crypto_value"]},
        {"segment": "Stocks", "value": pnl["stock_value"]}
    ])
    st.altair_chart(alt.Chart(df).mark_arc().encode(theta="value", color="segment"), use_container_width=True)

def combined_price_charts():
    crypto = get_crypto_history()
    stock = get_stock_history()
    crypto_index = None
    stock_index = None

    for s,df in crypto.items():
        if df.empty: continue
        crypto_index = df[["date","price"]].copy() if crypto_index is None else crypto_index.assign(price=crypto_index["price"]+df["price"])
    for s,df in stock.items():
        if df.empty: continue
        stock_index = df[["date","price"]].copy() if stock_index is None else stock_index.assign(price=stock_index["price"]+df["price"])

    if crypto_index is not None:
        st.write("Crypto Index")
        st.line_chart(crypto_index.set_index("date")["price"])
    if stock_index is not None:
        st.write("Stock Index")
        st.line_chart(stock_index.set_index("date")["price"])

def combined_mtd_ytd(rate):
    pnl = compute_grouped_pnl(rate)
    df = pd.DataFrame([
        {"segment": "Crypto", "MTD": pnl["crypto_mtd"], "YTD": pnl["crypto_ytd"]},
        {"segment": "Stocks", "MTD": pnl["stock_mtd"], "YTD": pnl["stock_ytd"]}
    ])
    base = alt.Chart(df).encode(x="segment")
    st.altair_chart(base.mark_bar().encode(y="MTD", color=alt.value("#1f77b4")) +
                    base.mark_bar().encode(y="YTD", color=alt.value("#2ca02c")),
                    use_container_width=True)
