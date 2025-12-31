import requests
import yfinance as yf
import streamlit as st


# ---------------------------------------------
# CRYPTO LIVE PRICES (RESILIENT)
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

        if r.status_code != 200:
            raise RuntimeError("CoinGecko unavailable")

        data = r.json()
        prices = {
            sym: float(data.get(cid, {}).get("usd", 0.0))
            for sym, cid in ids.items()
        }

        prices["USDT"] = prices.get("USDT") or 1.0
        return prices, True

    except Exception:
        fallback = {k: (1.0 if k == "USDT" else 0.0) for k in ids}
        return fallback, False


# ---------------------------------------------
# STOCK LIVE PRICES (RESILIENT)
# ---------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def stock_live_prices(symbols):
    try:
        data = yf.download(
            tickers=" ".join(symbols),
            period="1d",
            interval="1m",
            progress=False,
            threads=False,
        )

        prices = {}
        for sym in symbols:
            try:
                prices[sym] = float(data["Close"][sym].dropna().iloc[-1])
            except Exception:
                prices[sym] = 0.0

        return prices, True

    except Exception:
        return {s: 0.0 for s in symbols}, False
