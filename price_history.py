import requests
import yfinance as yf
import pandas as pd
import streamlit as st

# ---------------------------------------------
# CRYPTO LIVE PRICES (CACHED)
# ---------------------------------------------
@st.cache_data(ttl=60)
def crypto_live_prices():
    ids = {
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

    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=" + ",".join(ids.values()) +
            "&vs_currencies=usd"
        )
        r = requests.get(url, timeout=10)
        data = r.json()

        prices = {}
        for sym, cid in ids.items():
            prices[sym] = float(data.get(cid, {}).get("usd", 0.0))

        return prices

    except Exception as e:
        print("CRYPTO PRICE ERROR:", e)
        return {k: 0.0 for k in ids.keys()}


# ---------------------------------------------
# STOCK LIVE PRICES (CACHED)
# ---------------------------------------------
@st.cache_data(ttl=60)
def stock_live_prices(symbols=None):
    if not symbols:
        return {}

    prices = {}

    try:
        data = yf.download(
            tickers=" ".join(symbols),
            period="1d",
            interval="1m",
            progress=False,
            threads=False,
        )

        for sym in symbols:
            try:
                prices[sym] = float(data["Close"][sym].dropna().iloc[-1])
            except Exception:
                prices[sym] = 0.0

    except Exception as e:
        print("STOCK PRICE ERROR:", e)
        prices = {s: 0.0 for s in symbols}

    return prices
