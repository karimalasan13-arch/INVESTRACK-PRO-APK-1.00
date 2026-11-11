"""Session-only cash flow backend for unauthenticated visitors.

No network, Supabase credentials, disk storage, or user-record access.
"""
from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4
import streamlit as st


def _new_id():
    return 'preview_' + uuid4().hex


def _seed():
    result = {}
    for kind in ('personal', 'business'):
        wsid = 'preview_workspace_' + kind
        result.setdefault('cf_workspaces', []).append({
            'id': wsid, 'user_id': 'visitor', 'kind': kind,
            'name': 'Personal' if kind == 'personal' else 'Sample Business', 'currency': 'USD'})
        account = {'id': 'preview_account_' + kind, 'user_id': 'visitor',
                   'workspace_id': wsid, 'name': 'Sample bank account',
                   'account_type': 'Bank', 'opening_balance': '2500.00'}
        result.setdefault('cf_accounts', []).append(account)
        for days, txkind, amount, category, counterparty in (
            (8, 'income', '4500.00', 'Salary' if kind == 'personal' else 'Sales', 'Sample payer'),
            (5, 'expense', '1200.00', 'Rent' if kind == 'personal' else 'Materials', 'Sample supplier'),
            (2, 'expense', '420.00', 'Food & groceries' if kind == 'personal' else 'Transport & logistics', 'Sample merchant'),
        ):
            result.setdefault('cf_transactions', []).append({
                'id': _new_id(), 'user_id': 'visitor', 'workspace_id': wsid,
                'kind': txkind, 'occurred_on': (date.today() - timedelta(days=days)).isoformat(),
                'amount': amount, 'account_id': account['id'], 'to_account_id': None,
                'category': category, 'counterparty': counterparty,
                'description': 'Illustrative sample transaction', 'reference': ''})
    return result


def _store():
    return st.session_state.setdefault('_iv_visitor_cashflow_store', _seed())


class Result:
    def __init__(self, data):
        self.data = deepcopy(data)


class Query:
    def __init__(self, table):
        self.table = table
        self.filters = []
        self.action = 'select'
        self.payload = None
        self.order_by = None
        self.desc = False
        self.limit_n = None

    def select(self, *_args):
        self.action = 'select'
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, key, desc=False):
        self.order_by, self.desc = key, desc
        return self

    def limit(self, count):
        self.limit_n = count
        return self

    def insert(self, payload):
        self.action, self.payload = 'insert', payload
        return self

    def update(self, payload):
        self.action, self.payload = 'update', payload
        return self

    def delete(self):
        self.action = 'delete'
        return self

    def execute(self):
        records = _store().setdefault(self.table, [])
        matching = [r for r in records if all(r.get(k) == v for k, v in self.filters)]
        if self.action == 'insert':
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            created = [dict(item, id=item.get('id') or _new_id()) for item in items]
            records.extend(created)
            return Result(created)
        if self.action == 'update':
            for item in matching:
                item.update(self.payload)
            return Result(matching)
        if self.action == 'delete':
            ids = {r['id'] for r in matching}
            _store()[self.table] = [r for r in records if r['id'] not in ids]
            return Result(matching)
        if self.order_by:
            matching = sorted(matching, key=lambda r: str(r.get(self.order_by) or ''), reverse=self.desc)
        if self.limit_n is not None:
            matching = matching[:self.limit_n]
        return Result(matching)


class LocalClient:
    def table(self, name):
        if name not in ('cf_workspaces', 'cf_accounts', 'cf_transactions'):
            raise ValueError('Visitor store permits only cash-flow preview tables')
        return Query(name)


def get_visitor_client():
    return LocalClient()


def reset():
    st.session_state['_iv_visitor_cashflow_store'] = _seed()
