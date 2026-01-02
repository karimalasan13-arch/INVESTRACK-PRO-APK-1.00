import requests
import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime

# ---------------------------------------------
# CRYPTO LIVE PRICES (SAFE)
# ---------------------------------------------
@st.cache_data(ttl=300)
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
        for symbol, cg_id in ids.items():
            prices[symbol] = float(data.get(cg_id, {}).get("usd", 0.0))

        return prices

    except Exception as e:
        print("Crypto price fetch failed:", e)
        return {k: 0.0 for k in ids.keys()}


# ---------------------------------------------
# STOCK LIVE PRICES (RATE-LIMIT SAFE)
# ---------------------------------------------
@st.cache_data(ttl=300)
def stock_live_prices(symbols):
    """
    Fetch stock prices safely.
    NEVER crash UI due to rate limits.
    """
    prices = {}

    if not symbols:
        return prices

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
                if isinstance(data, pd.DataFrame):
                    price = data["Close"][sym].dropna().iloc[-1]
                    prices[sym] = float(price)
                else:
                    prices[sym] = 0.0
            except Exception:
                prices[sym] = 0.0

    except Exception as e:
        # 🔴 RATE LIMIT OR NETWORK ISSUE — DO NOT CRASH
        print("Yahoo Finance blocked request:", e)
        prices = {sym: 0.0 for sym in symbols}

    return prices
