import requests
import yfinance as yf
import streamlit as st

# ---------------------------------------------
# CRYPTO LIVE PRICES (CACHED)
# ---------------------------------------------
@st.cache_data(ttl=90, show_spinner=False)
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

        # USDT safety fallback
        prices["USDT"] = prices.get("USDT", 1.0) or 1.0
        return prices

    except Exception:
        # Safe fallback — app never crashes
        return {k: (1.0 if k == "USDT" else 0.0) for k in ids.keys()}


# ---------------------------------------------
# STOCK LIVE PRICES (CACHED)
# ---------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def stock_live_prices(symbols):
    prices = {}

    try:
        tickers = " ".join(symbols)
        data = yf.download(
            tickers=tickers,
            period="1d",
            interval="1m",
            progress=False,
            threads=False,
        )

        for symbol in symbols:
            try:
                price = data["Close"][symbol].dropna().iloc[-1]
                prices[symbol] = float(price)
            except Exception:
                prices[symbol] = 0.0

    except Exception:
        prices = {s: 0.0 for s in symbols}

    return prices
