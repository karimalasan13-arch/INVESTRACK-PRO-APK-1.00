import requests
import yfinance as yf
from datetime import datetime
from db import supabase


# -----------------------------------------
# INTERNAL HELPERS
# -----------------------------------------
def cache_prices(asset_type: str, prices: dict):
    rows = []
    for sym, price in prices.items():
        rows.append({
            "asset_type": asset_type,
            "symbol": sym,
            "price": float(price),
            "updated_at": datetime.utcnow().isoformat(),
        })

    if rows:
        supabase.table("price_cache").upsert(
            rows,
            on_conflict="asset_type,symbol",
        ).execute()


def load_cached_prices(asset_type: str, symbols: list):
    try:
        res = (
            supabase.table("price_cache")
            .select("symbol,price")
            .eq("asset_type", asset_type)
            .in_("symbol", symbols)
            .execute()
        )
        return {r["symbol"]: float(r["price"]) for r in res.data or []}
    except Exception:
        return {}


# -----------------------------------------
# CRYPTO — SAFE
# -----------------------------------------
def crypto_live_prices():
    try:
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

        url = "https://api.coingecko.com/api/v3/simple/price"
        r = requests.get(
            url,
            params={"ids": ",".join(ids.values()), "vs_currencies": "usd"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        prices = {
            sym: float(data[cg]["usd"])
            for sym, cg in ids.items()
            if cg in data
        }

        cache_prices("crypto", prices)
        return prices

    except Exception:
        # ⛔ Fallback to cache
        return load_cached_prices("crypto", [
            "BTC","ETH","SOL","BNB","XRP","ADA","DOGE","DOT","LTC","USDT"
        ])


# -----------------------------------------
# STOCKS — SAFE
# -----------------------------------------
def stock_live_prices(symbols: list):
    try:
        prices = {}
        tickers = yf.Tickers(" ".join(symbols))

        for sym in symbols:
            info = tickers.tickers[sym].fast_info
            price = info.get("lastPrice")
            if price:
                prices[sym] = float(price)

        if prices:
            cache_prices("stock", prices)

        return prices

    except Exception:
        return load_cached_prices("stock", symbols)
