"""Independent UTC-hourly snapshot collector. Run with SUPABASE_SERVICE_ROLE_KEY.

Never import Streamlit/session-bound db.py here. A failure in any required price
aborts the affected user's snapshot rather than recording an artificial loss.
"""
import os
import math
import logging
from datetime import datetime, timezone
import requests
import yfinance as yf
from supabase import create_client

LOG = logging.getLogger('snapshots')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
MODES = ('crypto', 'stock', 'etf', 'bond', 'overview')
STABLE = {'USDT', 'USDC', 'DAI'}


def number(v, default=0):
    try:
        n = float(v)
        return n if math.isfinite(n) else default
    except (TypeError, ValueError):
        return default


def pages(client, table, columns='*', **filters):
    offset, result = 0, []
    while True:
        q = client.table(table).select(columns)
        for k, v in filters.items():
            q = q.eq(k, v)
        batch = q.range(offset, offset + 999).execute().data or []
        result.extend(batch)
        if len(batch) < 1000:
            return result
        offset += 1000


def crypto_prices(symbols):
    CRYPTO_IDS = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDT': 'tether', 'XRP': 'ripple', 'BNB': 'binancecoin', 'SOL': 'solana', 'USDC': 'usd-coin', 'DOGE': 'dogecoin', 'ADA': 'cardano', 'TRX': 'tron', 'STETH': 'staked-ether', 'WBTC': 'wrapped-bitcoin', 'SUI': 'sui', 'LINK': 'chainlink', 'AVAX': 'avalanche-2', 'XLM': 'stellar', 'SHIB': 'shiba-inu', 'BCH': 'bitcoin-cash', 'HBAR': 'hedera-hashgraph', 'LEO': 'leo-token', 'LTC': 'litecoin', 'TON': 'the-open-network', 'DOT': 'polkadot', 'UNI': 'uniswap', 'PEPE': 'pepe', 'APT': 'aptos', 'NEAR': 'near', 'DAI': 'dai', 'ICP': 'internet-computer', 'ETC': 'ethereum-classic', 'OKB': 'okb', 'KAS': 'kaspa', 'ATOM': 'cosmos', 'CRO': 'crypto-com-chain', 'POL': 'polygon-ecosystem-token', 'FIL': 'filecoin', 'ARB': 'arbitrum', 'VET': 'vechain', 'ALGO': 'algorand', 'RENDER': 'render-token', 'FET': 'fetch-ai', 'OP': 'optimism', 'WIF': 'dogwifcoin', 'IMX': 'immutable-x', 'INJ': 'injective-protocol', 'SEI': 'sei-network', 'AAVE': 'aave', 'GRT': 'the-graph', 'LDO': 'lido-dao', 'QNT': 'quant-network'}
    ids = {s: CRYPTO_IDS[s] for s in symbols if s in CRYPTO_IDS}
    if not ids:
        return {}
    response = requests.get('https://api.coingecko.com/api/v3/simple/price',
                            params={'ids': ','.join(sorted(set(ids.values()))), 'vs_currencies': 'usd'}, timeout=25)
    response.raise_for_status()
    payload = response.json()
    return {s: number(payload.get(cid, {}).get('usd')) for s, cid in ids.items()}


def equity_prices(symbols):
    if not symbols:
        return {}
    result = {}
    # Daily bars give the most recent market close outside trading hours.
    for start in range(0, len(symbols), 35):
        batch = sorted(symbols)[start:start+35]
        frame = yf.download(' '.join(batch), period='5d', interval='1d', progress=False,
                            threads=False, auto_adjust=False)
        if frame.empty:
            continue
        close = frame['Close']
        for s in batch:
            try:
                series = close[s] if hasattr(close, 'columns') else close
                result[s] = number(series.dropna().iloc[-1])
            except (KeyError, IndexError):
                pass
    return result


def main():
    url = os.environ['SUPABASE_URL']
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    client = create_client(url, key)
    hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()
    holdings = {mode: pages(client, f'{mode}_holdings') for mode in ('crypto', 'stock', 'etf', 'bond')}
    settings = pages(client, 'user_settings', 'user_id,key,value')
    user_ids = {str(r['user_id']) for rows in holdings.values() for r in rows}
    user_ids.update(str(r['user_id']) for r in settings)
    setting_by_user = {}
    for row in settings:
        setting_by_user.setdefault(str(row['user_id']), {})[row['key']] = number(row['value'])
    by_user = {m: {} for m in holdings}
    for mode, rows in holdings.items():
        for r in rows:
            by_user[mode].setdefault(str(r['user_id']), []).append(r)
    crypto_syms = {r['symbol'] for r in holdings['crypto'] if number(r.get('quantity')) > 0}
    stock_syms = {r['symbol'] for r in holdings['stock'] if number(r.get('quantity')) > 0}
    etf_syms = {r['symbol'] for r in holdings['etf'] if number(r.get('quantity')) > 0}
    cp, ep = {}, {}
    try:
        cp = crypto_prices(crypto_syms)
    except Exception as exc:
        LOG.warning('Crypto pricing unavailable: %s', exc)
    try:
        ep = equity_prices(stock_syms | etf_syms)
    except Exception as exc:
        LOG.warning('Equity pricing unavailable: %s', exc)
    # Last known prices persist between scheduled runs, including closed markets.
    cached = {r['asset_type'] + ':' + r['symbol']: number(r['price_usd'])
              for r in pages(client, 'snapshot_price_cache', 'asset_type,symbol,price_usd')}
    fresh = []
    for typ, prices in (('crypto', cp), ('equity', ep)):
        for sym, price in prices.items():
            if price > 0:
                cached[f'{typ}:{sym}'] = price
                fresh.append({'asset_type': typ, 'symbol': sym, 'price_usd': price,
                              'updated_at': datetime.now(timezone.utc).isoformat()})
    if fresh:
        client.table('snapshot_price_cache').upsert(fresh, on_conflict='asset_type,symbol').execute()

    completed = 0
    for uid in sorted(user_ids):
        try:
            setting = setting_by_user.get(uid, {})
            values, invested, income = {}, {}, {}
            for mode in ('crypto', 'stock', 'etf'):
                amount = 0.0
                for h in by_user[mode].get(uid, []):
                    qty = number(h.get('quantity'))
                    if qty <= 0:
                        continue
                    sym = h['symbol']
                    price = cached.get(f'{"crypto" if mode == "crypto" else "equity"}:{sym}', 0)
                    if price <= 0 and mode == 'crypto' and sym in STABLE:
                        price = 1.0
                    if price <= 0:
                        raise ValueError(f'Price unavailable for {mode}:{sym}')
                    amount += qty * price
                rate = number(setting.get(f'{mode}_rate'), 14.5)
                if rate <= 0:
                    raise ValueError(f'Invalid {mode} FX rate')
                cash = number(setting.get(f'{mode}_cash')) / rate if mode != 'crypto' else 0
                values[mode] = amount + cash
                invested[mode] = number(setting.get(f'{mode}_investment')) / rate
                income[mode] = 0.0
            bond_value = number(setting.get('bond_cash')) / max(number(setting.get('bond_rate'), 14.5), 0.000001)
            bond_basis = bond_income = 0.0
            for h in by_user['bond'].get(uid, []):
                rate = number(h.get('usd_to_native_rate'))
                if rate <= 0:
                    raise ValueError('Invalid bond native FX rate')
                bond_value += number(h.get('current_value')) / rate
                bond_basis += number(h.get('purchase_value')) / rate
                bond_income += number(h.get('income_received')) / rate
            values['bond'], invested['bond'], income['bond'] = bond_value, bond_basis, bond_income
            values['overview'] = sum(values[m] for m in ('crypto', 'stock', 'etf', 'bond'))
            invested['overview'] = sum(invested[m] for m in ('crypto', 'stock', 'etf', 'bond'))
            income['overview'] = bond_income
            rows = []
            for mode in MODES:
                value = values[mode]
                if value < 0:
                    raise ValueError('Negative valuation')
                rows.append({'user_id': uid, 'mode': mode, 'snapshot_hour': hour,
                             'value_usd': round(value, 6), 'invested_usd': round(invested[mode], 6),
                             'income_usd': round(income[mode], 6),
                             'pnl_usd': round(value + income[mode] - invested[mode], 6)})
            client.table('portfolio_hourly_snapshots').upsert(
                rows, on_conflict='user_id,mode,snapshot_hour').execute()
            completed += 1
        except Exception as exc:
            LOG.warning('Skipped user %s: %s', uid[:8], exc)
    LOG.info('Hourly snapshot completed: %d/%d users, hour=%s', completed, len(user_ids), hour)


if __name__ == '__main__':
    main()
