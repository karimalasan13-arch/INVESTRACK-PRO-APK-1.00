"""Isolated investment demo state. No Supabase operations for visitors."""
import streamlit as st
from copy import deepcopy
from uuid import uuid4
from datetime import date, timedelta
VISITOR_ID = "__investrack_visitor__"
SEEDS = {"crypto": {"BTC": 0.08, "ETH": 1.4, "SOL": 8.0}, "stock": {"AAPL": 6.0, "MSFT": 3.0, "NVDA": 5.0}, "etf": {"VOO": 4.0, "QQQ": 2.0, "SCHD": 10.0}}
INITIAL = {"crypto_investment": 8500.0, "stock_investment": 3200.0, "etf_investment": 3500.0, "stock_cash": 350.0, "etf_cash": 200.0, "bond_cash": 150.0}
def is_visitor(user_id=None):
    return user_id == VISITOR_ID
def store():
    if '_iv_demo_investments' not in st.session_state:
        maturity = (date.today()+timedelta(days=365)).isoformat()
        st.session_state['_iv_demo_investments'] = {
            'settings': dict(INITIAL), 'holdings': deepcopy(SEEDS),
            'bonds': [{'id': 'demo_bond_1', 'name':'Illustrative Treasury Note', 'issuer':'Sample issuer', 'bond_type':'Government Bond', 'currency_code':'USD', 'usd_to_native_rate':1.0, 'face_value':2500.0, 'purchase_value':2400.0, 'current_value':2450.0, 'coupon_rate':4.5, 'income_received':75.0, 'maturity_date':maturity, 'payment_frequency':'Semi-Annual'}]
        }
    return st.session_state['_iv_demo_investments']
def load_setting(key, default):
    return float(store()['settings'].get(key, default))
def save_setting(key, value):
    store()['settings'][key] = float(value)
def holdings(mode, allowed):
    saved=store()['holdings'].get(mode, {})
    return {sym: float(saved.get(sym, 0)) for sym in allowed}
def save_holdings(mode, values):
    store()['holdings'][mode] = {k:float(v) for k,v in values.items()}
def bonds():
    return deepcopy(store()['bonds'])
def add_bond(holding):
    store()['bonds'].append(dict(holding,id='demo_'+uuid4().hex))
def update_bond(holding_id, holding):
    for row in store()['bonds']:
        if row['id']==holding_id:
            row.update(holding)
def delete_bond(holding_id):
    store()['bonds']=[r for r in store()['bonds'] if r['id']!=holding_id]
def demo_notice():
    st.info('DEMO MODE — Illustrative portfolio and temporary changes only. Sign in to save your investments.')
