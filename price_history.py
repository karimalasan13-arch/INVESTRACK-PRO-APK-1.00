# price_history.py

import os
import requests
import yfinance as yf
import streamlit as st

# ---------------------------------------------
# SECRETS
# ---------------------------------------------
ALPHA_VANTAGE_API_KEY = (
    st.secrets.get("ALPHA_VANTAGE_API_KEY")
    or os.getenv("ALPHA_VANTAGE_API_KEY")
)

# ---------------------------------------------
# CRYPTO LIVE PRICES (CoinGecko)
# ---------------------------------------------
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
        print("CRYPTO PRICE ERROR:", e)
        return {k: 0.0 for k in ids.keys()}

# ---------------------------------------------
# STOCK LIVE PRICES (Alpha Vantage → Yahoo)
# ---------------------------------------------
def stock_live_prices(symbols=None):
    if not symbols:
        return {}

    prices = {}

    # -----------------------------
    # Alpha Vantage (single symbol)
    # -----------------------------
    if ALPHA_VANTAGE_API_KEY:
        try:
            symbol = symbols[0]
            url = (
                "https://www.alphavantage.co/query"
                f"?function=GLOBAL_QUOTE&symbol={symbol}"
                f"&apikey={ALPHA_VANTAGE_API_KEY}"
            )

            r = requests.get(url, timeout=10)
            data = r.json()

            quote = data.get("Global Quote", {})
            price = quote.get("05. price")

            if price:
                prices[symbol] = float(price)
                return prices

        except Exception as e:
            print("Alpha Vantage error:", e)

    # -----------------------------
    # Yahoo Finance fallback
    # -----------------------------
    try:
        tickers = " ".join(symbols)
        data = yf.download(
            tickers=tickers,
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
        print("Yahoo Finance error:", e)
        prices = {sym: 0.0 for sym in symbols}

    return prices
