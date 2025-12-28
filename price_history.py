import requests
import yfinance as yf
import pandas as pd
import streamlit as st

# =====================================================
# CRYPTO LIVE PRICES (CoinGecko)
# =====================================================

@st.cache_data(ttl=300, show_spinner=False)  # cache for 5 minutes
def crypto_live_prices():
    """
    Fetch live crypto prices (USD) from CoinGecko.
    Returns: { 'BTC': 65000.0, ... }
    """

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
        r.raise_for_status()
        data = r.json()

        prices = {}
        for symbol, cg_id in ids.items():
            usd_price = data.get(cg_id, {}).get("usd", 0)
            prices[symbol] = float(usd_price) if usd_price else 0.0

        return prices

    except Exception as e:
        print("CRYPTO PRICE ERROR:", e)
        return {symbol: 0.0 for symbol in ids.keys()}


# =====================================================
# STOCK LIVE PRICES
# =====================================================

ALPHA_VANTAGE_API_KEY = "K5BD9E87QW2WKQAMY"

VALID_TICKER_MAP = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "TSLA": "TSLA",
    "META": "META",
    "NVDA": "NVDA",
    "JPM": "JPM",
    "V": "V",
    "BRK-B": "BRK.B",
}


@st.cache_data(ttl=300, show_spinner=False)  # cache for 5 minutes
def stock_live_prices(symbols=None):
    """
    Fetch USD stock prices.
    Priority:
      1. Alpha Vantage (single symbol)
      2. Yahoo Finance (fallback, batch)
    """

    if not symbols:
        return {}

    symbols = list(set(symbols))  # dedupe
    prices = {}

    # ---------------------------------
    # Alpha Vantage (single symbol only)
    # ---------------------------------
    symbol = symbols[0]
    try:
        url = (
            "https://www.alphavantage.co/query"
            f"?function=TIME_SERIES_INTRADAY"
            f"&symbol={symbol}"
            f"&interval=5min"
            f"&apikey={ALPHA_VANTAGE_API_KEY}"
            f"&outputsize=compact"
        )

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        series = data.get("Time Series (5min)")
        if series:
            latest_ts = sorted(series.keys())[-1]  # FIXED: latest timestamp
            prices[symbol] = float(series[latest_ts]["4. close"])
        else:
            raise ValueError("Alpha Vantage returned no time series")

    except Exception as e:
        print(f"Alpha Vantage failed for {symbol}: {e}")
        prices.update(fetch_from_yahoo(symbols))

    return prices


# =====================================================
# YAHOO FINANCE FALLBACK
# =====================================================

def fetch_from_yahoo(symbols):
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
                if len(symbols) == 1:
                    price = data["Close"].dropna().iloc[-1]
                else:
                    price = data["Close"][symbol].dropna().iloc[-1]

                prices[symbol] = float(price)
            except Exception:
                prices[symbol] = 0.0

    except Exception as e:
        print("Yahoo Finance error:", e)
        for symbol in symbols:
            prices[symbol] = 0.0

    return prices
