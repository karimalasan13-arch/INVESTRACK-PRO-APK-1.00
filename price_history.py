import requests
import yfinance as yf
import pandas as pd

# ---------------------------------------------
# CRYPTO LIVE PRICES
# ---------------------------------------------
def crypto_live_prices():
    import requests

    # Correct CoinGecko IDs for each symbol
    ids = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "LTC": "litecoin"
        "USDT": "Tether",
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
            # Some IDs appear but with None — ensure fallback 0
            usd_price = data.get(cg_id, {}).get("usd", 0)
            prices[symbol] = float(usd_price) if usd_price else 0.0

        return prices

    except Exception as e:
        print("CRYPTO PRICE ERROR:", e)
        return {k: 0.0 for k in ids.keys()}

import requests
import yfinance as yf
import pandas as pd

# Alpha Vantage API key (replace with your actual key)
ALPHA_VANTAGE_API_KEY = 'K5BD9E87QW2WKQAMY'

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

def stock_live_prices(symbols=None):
    """
    Fetch USD stock prices with Alpha Vantage first, then fall back to Yahoo Finance.
    Supports filtering: stock_live_prices(symbols=['AAPL','GOOGL'])
    Returns: { 'AAPL': 189.23, ... }
    """
    prices = {}

    # Fetch data from Alpha Vantage if symbols are provided
    if symbols:
        symbol = symbols[0]  # Alpha Vantage supports one symbol at a time
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=5min&apikey={ALPHA_VANTAGE_API_KEY}&outputsize=compact"
        try:
            response = requests.get(url)
            data = response.json()

            if "Time Series (5min)" in data:
                time_series = data["Time Series (5min)"]
                # Get the latest closing price
                latest_timestamp = sorted(time_series.keys())[0]
                latest_data = time_series[latest_timestamp]
                price = float(latest_data["4. close"])
                prices[symbol] = price
            else:
                print(f"Alpha Vantage: No data for {symbol}, falling back to Yahoo Finance.")
                prices = fetch_from_yahoo(symbols)
        except Exception as e:
            print(f"Alpha Vantage error for {symbol}: {e}")
            prices = fetch_from_yahoo(symbols)
    else:
        prices = fetch_from_yahoo(symbols)

    return prices

def fetch_from_yahoo(symbols):
    prices = {}
    try:
        tickers = " ".join(symbols)
        data = yf.download(
            tickers=tickers,
            period="1d",
            interval="1m",
            progress=False,
            threads=False
        )
        for symbol in symbols:
            try:
                price = data["Close"][symbol].dropna().iloc[-1]
                prices[symbol] = float(price)
            except Exception as e:
                print(f"Yahoo Finance error for {symbol}: {e}")
                prices[symbol] = 0.0
    except Exception as e:
        print(f"Yahoo Finance error: {e}")
        for symbol in symbols:
            prices[symbol] = 0.0

    return prices
