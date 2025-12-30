import requests
import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import datetime

# ---------------------------------------------
# SHARED CACHE HELPERS
# ---------------------------------------------
def _get_cached(key):
    return st.session_state.get(key)

def _set_cached(key, value):
    st.session_state[key] = value


# ---------------------------------------------
# CRYPTO LIVE PRICES (RESILIENT)
# ---------------------------------------------
@st.cache_data(ttl=300)
def _fetch_crypto_from_api():
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

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=" + ",".join(ids.values()) +
        "&vs_currencies=usd"
    )

    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()

    prices = {}
    for sym, cid in ids.items():
        prices[sym] = float(data.get(cid, {}).get("usd", 1.0 if sym == "USDT" else 0.0))

    return prices


def crypto_live_prices():
    """
    Returns: (prices: dict, status: str)
    """
    try:
        prices = _fetch_crypto_from_api()
        _set_cached("last_crypto_prices", prices)
        return prices, "live"
    except Exception:
        cached = _get_cached("last_crypto_prices")
        if cached:
            return cached, "cached"
        # absolute fallback
        return {"USDT": 1.0}, "offline"


# ---------------------------------------------
# STOCK LIVE PRICES (RESILIENT)
# ---------------------------------------------
@st.cache_data(ttl=300)
def _fetch_stocks_yahoo(symbols):
    data = yf.download(
        tickers=" ".join(symbols),
        period="1d",
        interval="1m",
        progress=False,
        threads=False,
    )

    prices = {}
    for s in symbols:
        try:
            prices[s] = float(data["Close"][s].dropna().iloc[-1])
        except Exception:
            prices[s] = 0.0

    return prices


def stock_live_prices(symbols):
    """
    Returns: (prices: dict, status: str)
    """
    try:
        prices = _fetch_stocks_yahoo(symbols)
        _set_cached("last_stock_prices", prices)
        return prices, "live"
    except Exception:
        cached = _get_cached("last_stock_prices")
        if cached:
            return cached, "cached"
        return {s: 0.0 for s in symbols}, "offline"
