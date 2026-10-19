"""InvesTrack Pro cash flow module. Requires cashflow_supabase_setup.sql."""
from datetime import date
from decimal import Decimal, InvalidOperation
import pandas as pd
import streamlit as st
from auth import get_auth_client

PERSONAL_INCOME = ['Salary', 'Freelance', 'Business income', 'Interest', 'Dividends', 'Gift', 'Refund', 'Other']
PERSONAL_EXPENSE = ['Food & groceries', 'Rent & housing', 'Utilities', 'Transport', 'Healthcare', 'Education', 'Shopping', 'Entertainment', 'Family', 'Subscriptions', 'Other']
BUSINESS_INCOME = ['Sales', 'Client payment', 'Consulting fees', 'Service revenue', 'Other revenue', 'Refund', 'Other']
BUSINESS_EXPENSE = ['Materials', 'Labour & payroll', 'Rent', 'Utilities', 'Transport & logistics', 'Equipment', 'Marketing', 'Professional fees', 'Taxes & fees', 'Other']


def _db():
    return get_auth_client()


def _query(table, workspace_id, order=None):
    q = _db().table(table).select('*').eq('workspace_id', workspace_id)
    if order:
        q = q.order(order, desc=True)
    return q.execute().data or []


def _money(value, currency):
    return f'{currency} {Decimal(str(value or 0)):,.2f}'


def _rerun():
    st.rerun()


def _workspace(kind, user_id):
    db = _db()
    existing = db.table('cf_workspaces').select('*').eq('user_id', user_id).eq('kind', kind).limit(1).execute().data
    if existing:
        return existing[0]
    return db.table('cf_workspaces').insert({'user_id': user_id, 'kind': kind, 'name': 'Personal' if kind == 'personal' else 'My Business', 'currency': 'GHS'}).execute().data[0]


def render_cashflow():
    user_id = st.session_state.get('user_id')
    if not user_id:
        st.warning('Sign in to access Cash Flow.')
        return
    st.title('💳 Cash Flow Management')
    st.caption('Know exactly where your money comes from and where it goes.')
    kind_label = st.radio('Financial workspace', ['Personal', 'Business'], horizontal=True, key='cf_kind')
    kind = kind_label.lower()
    try:
        ws = _workspace(kind, user_id)
        accounts = _query('cf_accounts', ws['id'])
        transactions = _query('cf_transactions', ws['id'], 'occurred_on')
    except Exception as exc:
        st.error('Cash Flow database is not ready. Run cashflow_supabase_setup.sql in Supabase SQL Editor, then refresh.')
        st.caption(f'Database detail: {type(exc).__name__}')
        return

    currency = ws.get('currency') or 'GHS'
    account_names = {a['id']: a['name'] for a in accounts}
    movements = {a['id']: Decimal(str(a.get('opening_balance') or 0)) for a in accounts}
    total_income = Decimal('0')
    total_expense = Decimal('0')
    for t in transactions:
        amount = Decimal(str(t['amount']))
        if t['kind'] == 'income':
            total_income += amount
            movements[t['account_id']] = movements.get(t['account_id'], Decimal('0')) + amount
        elif t['kind'] == 'expense':
            total_expense += amount
            movements[t['account_id']] = movements.get(t['account_id'], Decimal('0')) - amount
        elif t['kind'] == 'transfer':
            movements[t['account_id']] = movements.get(t['account_id'], Decimal('0')) - amount
            movements[t['to_account_id']] = movements.get(t['to_account_id'], Decimal('0')) + amount

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Account balances', _money(sum(movements.values()), currency))
    c2.metric('Income recorded', _money(total_income, currency))
    c3.metric('Expenses recorded', _money(total_expense, currency))
    c4.metric('Net cash flow', _money(total_income - total_expense, currency))
    st.caption('Figures are for all recorded dates in this workspace. Transfers do not count as income or expenses.')

    tabs = st.tabs(['➕ Record transaction', '📜 Transaction history', '🏦 Accounts', '📊 Reports', '⚙️ Workspace'])
    with tabs[0]:
        if not accounts:
            st.info('Create your first account under Accounts before recording transactions.')
        else:
            with st.form(f'cf_add_{kind}', clear_on_submit=True):
                tx_kind = st.radio('Transaction type', ['Expense', 'Income', 'Transfer'], horizontal=True)
                tx_date = st.date_input('Date money moved', value=date.today(), max_value=date.today())
                amount = st.number_input(f'Amount ({currency})', min_value=0.01, step=10.0, format='%.2f')
                account_ids = list(account_names)
                source_id = st.selectbox('Account' if tx_kind != 'Transfer' else 'From account', account_ids, format_func=lambda x: account_names[x])
                target_id = None
                if tx_kind == 'Transfer':
                    target_id = st.selectbox('To account', account_ids, format_func=lambda x: account_names[x], key=f'cf_target_{kind}')
                categories = (PERSONAL_INCOME if kind == 'personal' else BUSINESS_INCOME) if tx_kind == 'Income' else (PERSONAL_EXPENSE if kind == 'personal' else BUSINESS_EXPENSE)
                if tx_kind == 'Transfer':
                    category = 'Transfer'
                else:
                    chosen = st.selectbox('Category', categories + ['Custom category…'])
                    category = st.text_input('Custom category', placeholder='e.g. Building materials') if chosen == 'Custom category…' else chosen
                party = st.text_input('Paid to / received from', placeholder='e.g. Supermarket, client, employer, supplier')
                description = st.text_area('What was this for?', placeholder='Describe exactly what the money was spent on or received for')
                reference = st.text_input('Receipt / transaction reference (optional)')
                submitted = st.form_submit_button('Save transaction', type='primary', use_container_width=True)
            if submitted:
                if tx_kind == 'Transfer' and (len(accounts) < 2 or target_id == source_id):
                    st.error('Transfers require two different accounts.')
                elif not category.strip():
                    st.error('Enter a category.')
                else:
                    payload = {'user_id': user_id, 'workspace_id': ws['id'], 'kind': tx_kind.lower(),
                               'occurred_on': tx_date.isoformat(), 'amount': str(Decimal(str(amount)).quantize(Decimal('0.01'))),
                               'account_id': source_id, 'to_account_id': target_id, 'category': category.strip(),
                               'counterparty': party.strip(), 'description': description.strip(), 'reference': reference.strip()}
                    try:
                        _db().table('cf_transactions').insert(payload).execute()
                        st.success('Transaction saved.')
                        _rerun()
                    except Exception as exc:
                        st.error(f'Could not save transaction: {exc}')

    with tabs[1]:
        st.subheader('Transaction history')
        if not transactions:
            st.info('Your dated income and expense records will appear here.')
        else:
            a, b, c = st.columns(3)
            with a: start = st.date_input('From', value=min(date.fromisoformat(t['occurred_on']) for t in transactions), key=f'cf_from_{kind}')
            with b: end = st.date_input('To', value=date.today(), key=f'cf_to_{kind}')
            with c: kind_filter = st.selectbox('Type', ['All', 'Income', 'Expense', 'Transfer'], key=f'cf_filter_{kind}')
            search = st.text_input('Search merchant, payer, category, notes or reference', key=f'cf_search_{kind}')
            visible = [t for t in transactions if start.isoformat() <= t['occurred_on'] <= end.isoformat()
                       and (kind_filter == 'All' or t['kind'] == kind_filter.lower())
                       and search.lower() in ' '.join(str(t.get(k) or '') for k in ['category', 'counterparty', 'description', 'reference']).lower()]
            rows = [{'Date': t['occurred_on'], 'Type': t['kind'].title(), 'Amount': float(t['amount']),
                     'Account': account_names.get(t['account_id'], 'Deleted account'),
                     'To account': account_names.get(t.get('to_account_id'), '') if t.get('to_account_id') else '',
                     'Category': t.get('category') or '', 'Paid to / From': t.get('counterparty') or '',
                     'Description': t.get('description') or '', 'Reference': t.get('reference') or ''} for t in visible]
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button('Download filtered history (CSV)', df.to_csv(index=False).encode('utf-8-sig'),
                               file_name=f'investrack_{kind}_transactions.csv', mime='text/csv')
            if visible:
                options = {t['id']: f"{t['occurred_on']} · {t['kind']} · {_money(t['amount'], currency)} · {t.get('counterparty') or t.get('category')}" for t in visible}
                chosen_id = st.selectbox('Select transaction to correct or delete', list(options), format_func=lambda x: options[x], key=f'cf_edit_select_{kind}')
                selected = next(t for t in visible if t['id'] == chosen_id)
                with st.expander('Edit selected transaction'):
                    with st.form(f'cf_edit_{kind}_{chosen_id}'):
                        edit_date = st.date_input('Transaction date', date.fromisoformat(selected['occurred_on']))
                        edit_amount = st.number_input('Amount', min_value=0.01, value=float(selected['amount']), format='%.2f')
                        edit_category = st.text_input('Category', value=selected.get('category') or '')
                        edit_party = st.text_input('Paid to / received from', value=selected.get('counterparty') or '')
                        edit_description = st.text_area('Description', value=selected.get('description') or '')
                        edit_reference = st.text_input('Reference', value=selected.get('reference') or '')
                        save_edit = st.form_submit_button('Save changes')
                    if save_edit:
                        if not edit_category.strip():
                            st.error('Category is required.')
                        else:
                            try:
                                _db().table('cf_transactions').update({'occurred_on': edit_date.isoformat(), 'amount': str(Decimal(str(edit_amount)).quantize(Decimal('0.01'))), 'category': edit_category.strip(), 'counterparty': edit_party.strip(), 'description': edit_description.strip(), 'reference': edit_reference.strip()}).eq('id', chosen_id).eq('workspace_id', ws['id']).execute()
                                st.success('Transaction updated.')
                                _rerun()
                            except Exception as exc: st.error(f'Update failed: {exc}')
                with st.expander('Delete selected transaction'):
                    confirm = st.checkbox('I understand this permanently deletes the selected record.', key=f'cf_confirm_{kind}_{chosen_id}')
                    if st.button('Delete transaction', disabled=not confirm, key=f'cf_delete_{kind}_{chosen_id}'):
                        try:
                            _db().table('cf_transactions').delete().eq('id', chosen_id).eq('workspace_id', ws['id']).execute()
                            _rerun()
                        except Exception as exc: st.error(f'Delete failed: {exc}')

    with tabs[2]:
        st.subheader('Your accounts')
        if accounts:
            st.dataframe([{'Account': a['name'], 'Type': a['account_type'], 'Balance': _money(movements[a['id']], currency)} for a in accounts], use_container_width=True, hide_index=True)
        with st.form(f'cf_account_{kind}', clear_on_submit=True):
            name = st.text_input('Account name', placeholder='e.g. Main bank, Mobile money, Cash wallet')
            account_type = st.selectbox('Account type', ['Bank', 'Mobile money', 'Cash', 'Other'])
            opening = st.number_input('Opening balance', value=0.0, step=100.0, format='%.2f', help='Balance before your first recorded transaction. Do not add it again as income.')
            create = st.form_submit_button('Add account')
        if create:
            if not name.strip(): st.error('Enter an account name.')
            else:
                try:
                    _db().table('cf_accounts').insert({'user_id': user_id, 'workspace_id': ws['id'], 'name': name.strip(), 'account_type': account_type, 'opening_balance': str(Decimal(str(opening)).quantize(Decimal('0.01')))}).execute()
                    _rerun()
                except Exception as exc: st.error(f'Could not create account: {exc}')

        if accounts:
            st.divider()
            st.subheader('Remove an account')
            st.caption('Accounts with recorded income, expenses or transfers cannot be deleted. '
                       'This protects your transaction history and financial reports.')
            account_by_id = {a['id']: a for a in accounts}
            remove_id = st.selectbox('Account to remove', list(account_by_id),
                                     format_func=lambda aid: account_by_id[aid]['name'],
                                     key=f'cf_remove_account_{kind}')
            linked = [t for t in transactions if t.get('account_id') == remove_id
                      or t.get('to_account_id') == remove_id]
            if linked:
                st.warning(f'This account has {len(linked)} linked transaction(s). '
                           'It cannot be deleted until those records are handled.')
            else:
                confirm_remove = st.checkbox(
                    'I understand this will permanently remove the account and its opening balance.',
                    key=f'cf_remove_confirm_{kind}_{remove_id}')
                if st.button('Delete selected account', type='secondary',
                             disabled=not confirm_remove,
                             key=f'cf_remove_button_{kind}_{remove_id}'):
                    try:
                        # FK constraints also prevent deletion if any linked transaction
                        # was created since the page loaded.
                        _db().table('cf_accounts').delete().eq('id', remove_id).eq(
                            'workspace_id', ws['id']).eq('user_id', user_id).execute()
                        st.success('Account removed.')
                        _rerun()
                    except Exception:
                        st.error('Could not remove the account. Check for linked transactions.')

    with tabs[3]:
        st.subheader('Cash flow reports')
        if not transactions:
            st.info('Add transactions to see monthly trends and spending categories.')
        else:
            summary = pd.DataFrame([{'Month': t['occurred_on'][:7], 'Type': t['kind'], 'Amount': float(t['amount'])} for t in transactions if t['kind'] != 'transfer'])
            if not summary.empty:
                pivot = summary.pivot_table(index='Month', columns='Type', values='Amount', aggfunc='sum', fill_value=0)
                for col in ('income', 'expense'):
                    if col not in pivot.columns: pivot[col] = 0.0
                pivot['Net'] = pivot['income'] - pivot['expense']
                st.bar_chart(pivot[['income', 'expense']])
                st.dataframe(pivot.rename(columns={'income': 'Income', 'expense': 'Expenses'}), use_container_width=True)
            expenses = [t for t in transactions if t['kind'] == 'expense']
            if expenses:
                categories = pd.DataFrame([{'Category': t['category'], 'Amount': float(t['amount'])} for t in expenses])
                st.subheader('Where your money went')
                st.bar_chart(categories.groupby('Category')['Amount'].sum().sort_values(ascending=False))

    with tabs[4]:
        st.subheader('Workspace settings')
        st.write(f'Workspace: **{ws["name"]}** · Type: **{kind_label}**')
        st.caption('Each workspace has its own accounts, transactions and reporting currency.')
        if not transactions and not accounts:
            options = ['GHS', 'USD', 'GBP', 'EUR', 'NGN', 'PHP', 'KES', 'ZAR', 'CAD', 'AUD']
            choice = st.selectbox('Reporting currency', options, index=options.index(currency) if currency in options else 0)
            if st.button('Save currency', key=f'cf_currency_save_{kind}'):
                _db().table('cf_workspaces').update({'currency': choice}).eq('id', ws['id']).execute()
                _rerun()
        else:
            st.info('Currency is locked after accounts or transactions are created to prevent misleading totals. Currency conversion is planned for a later release.')
