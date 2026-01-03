import time
import requests
import yfinance as yf

# ---------------------------------------------
# GLOBAL CACHE (STREAMLIT SAFE)
# ---------------------------------------------
_PRICE_CACHE = {
    "crypto": {"ts": 0, "data": {}},
    "stocks": {"ts": 0, "data": {}},
}

CACHE_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------
# CRYPTO LIVE PRICES (COINGECKO, HARDENED)
# ---------------------------------------------
def crypto_live_prices():
    now = time.time()

    # Serve from cache if fresh
    if now - _PRICE_CACHE["crypto"]["ts"] < CACHE_TTL_SECONDS:
        return _PRICE_CACHE["crypto"]["data"]

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

        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()

        prices = {}
        for sym, cg_id in ids.items():
            usd = data.get(cg_id, {}).get("usd")
            prices[sym] = float(usd) if usd is not None else 0.0

        # Cache result
        _PRICE_CACHE["crypto"] = {
            "ts": now,
            "data": prices,
        }

        return prices

    except Exception as e:
        print("CRYPTO PRICE ERROR:", e)

        # Fallback to last cache
        return _PRICE_CACHE["crypto"]["data"] or {k: 0.0 for k in ids}


# ---------------------------------------------
# STOCK LIVE PRICES (YAHOO ONLY, HARDENED)
# ---------------------------------------------
def stock_live_prices(symbols):
    if not symbols:
        return {}

    now = time.time()

    # Serve from cache if fresh
    if now - _PRICE_CACHE["stocks"]["ts"] < CACHE_TTL_SECONDS:
        cached = _PRICE_CACHE["stocks"]["data"]
        return {s: cached.get(s, 0.0) for s in symbols}

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
                price = data["Close"][sym].dropna().iloc[-1]
                prices[sym] = float(price)
            except Exception:
                prices[sym] = 0.0

        # Cache result
        _PRICE_CACHE["stocks"] = {
            "ts": now,
            "data": prices,
        }

        return prices

    except Exception as e:
        print("STOCK PRICE ERROR:", e)

        # Fallback to last cache
        cached = _PRICE_CACHE["stocks"]["data"]
        return {s: cached.get(s, 0.0) for s in symbols}
