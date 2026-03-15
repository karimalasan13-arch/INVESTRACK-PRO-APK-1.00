import requests
import yfinance as yf
import streamlit as st

# ---------------------------------------------
# CACHE SETTINGS
# ---------------------------------------------
CRYPTO_CACHE_TTL = 300   # 5 minutes
STOCK_CACHE_TTL = 300    # 5 minutes


# ---------------------------------------------
# CRYPTO LIVE PRICES
# ---------------------------------------------
@st.cache_data(ttl=CRYPTO_CACHE_TTL, show_spinner=False)
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

    prices = {}

    try:

        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=" + ",".join(ids.values()) +
            "&vs_currencies=usd"
        )

        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()

        for sym, cg_id in ids.items():
            price = float(data.get(cg_id, {}).get("usd", 0.0))
            prices[sym] = price

    except Exception:
        prices = {}

    # -----------------------------------------
    # SESSION FALLBACK
    # -----------------------------------------
    if prices:

        st.session_state.crypto_last_prices = prices

        return prices

    return st.session_state.get("crypto_last_prices", {})


# ---------------------------------------------
# STOCK LIVE PRICES
# ---------------------------------------------
@st.cache_data(ttl=STOCK_CACHE_TTL, show_spinner=False)
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

        if data.empty:
            return st.session_state.get("stock_last_prices", {})

        for sym in symbols:

            try:
                price = data["Close"][sym].dropna().iloc[-1]
                prices[sym] = float(price)

            except Exception:
                prices[sym] = 0.0

    except Exception:
        prices = {}

    # -----------------------------------------
    # SESSION FALLBACK
    # -----------------------------------------
    if prices:

        st.session_state.stock_last_prices = prices

        return prices

    return st.session_state.get("stock_last_prices", {})
