import requests
import yfinance as yf

# ---------------------------------------------
# CRYPTO LIVE PRICES (DEFENSIVE)
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
        for sym, cid in ids.items():
            prices[sym] = float(data.get(cid, {}).get("usd", 0.0))

        prices.setdefault("USDT", 1.0)
        return prices

    except Exception as e:
        print("CRYPTO PRICE ERROR:", e)
        return {k: (1.0 if k == "USDT" else 0.0) for k in ids}


# ---------------------------------------------
# STOCK LIVE PRICES (DEFENSIVE)
# ---------------------------------------------
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

        for sym in symbols:
            try:
                prices[sym] = float(data["Close"][sym].dropna().iloc[-1])
            except Exception:
                prices[sym] = 0.0

    except Exception as e:
        print("STOCK PRICE ERROR:", e)
        prices = {s: 0.0 for s in symbols}

    return prices
