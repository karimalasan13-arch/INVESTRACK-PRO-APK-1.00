import requests
import yfinance as yf
import streamlit as st


# ---------------------------------------------
# CACHE SETTINGS
# ---------------------------------------------
CRYPTO_CACHE_TTL = 300
STOCK_CACHE_TTL = 300


# ---------------------------------------------
# CRYPTO MAP
# ---------------------------------------------
CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "SOL": "solana",
    "USDC": "usd-coin",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "TRX": "tron",
    "STETH": "staked-ether",
    "WBTC": "wrapped-bitcoin",
    "SUI": "sui",
    "LINK": "chainlink",
    "AVAX": "avalanche-2",
    "XLM": "stellar",
    "SHIB": "shiba-inu",
    "BCH": "bitcoin-cash",
    "HBAR": "hedera-hashgraph",
    "LEO": "leo-token",
    "LTC": "litecoin",
    "TON": "the-open-network",
    "DOT": "polkadot",
    "UNI": "uniswap",
    "PEPE": "pepe",
    "APT": "aptos",
    "NEAR": "near",
    "DAI": "dai",
    "ICP": "internet-computer",
    "ETC": "ethereum-classic",
    "OKB": "okb",
    "KAS": "kaspa",
    "ATOM": "cosmos",
    "CRO": "crypto-com-chain",
    "POL": "polygon-ecosystem-token",
    "FIL": "filecoin",
    "ARB": "arbitrum",
    "VET": "vechain",
    "ALGO": "algorand",
    "RENDER": "render-token",
    "FET": "fetch-ai",
    "OP": "optimism",
    "WIF": "dogwifcoin",
    "IMX": "immutable-x",
    "INJ": "injective-protocol",
    "SEI": "sei-network",
    "AAVE": "aave",
    "GRT": "the-graph",
    "LDO": "lido-dao",
    "QNT": "quant-network",
}


# ---------------------------------------------
# CRYPTO LIVE PRICES
# ---------------------------------------------
@st.cache_data(ttl=CRYPTO_CACHE_TTL, show_spinner=False)
def crypto_live_prices():

    prices = {}

    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=" + ",".join(CRYPTO_IDS.values()) +
            "&vs_currencies=usd"
        )

        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        for sym, cg_id in CRYPTO_IDS.items():
            prices[sym] = float(data.get(cg_id, {}).get("usd", 0.0))

    except Exception:
        prices = {}

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
            auto_adjust=False,
        )

        if data.empty:
            return st.session_state.get("stock_last_prices", {})

        for sym in symbols:
            try:
                if "Close" in data:
                    close_data = data["Close"]

                    if hasattr(close_data, "columns"):
                        price = close_data[sym].dropna().iloc[-1]
                    else:
                        price = close_data.dropna().iloc[-1]

                    prices[sym] = float(price)

                else:
                    prices[sym] = 0.0

            except Exception:
                prices[sym] = 0.0

    except Exception:
        prices = {}

    if prices:
        st.session_state.stock_last_prices = prices
        return prices

    return st.session_state.get("stock_last_prices", {})
