"""Run with: python -m unittest discover -s . -p 'test_*.py' -v"""
import importlib.util
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch


class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


st = types.ModuleType('streamlit')
st.session_state = State()
fake_db = types.ModuleType('db')
fake_db.get_supabase = lambda: None

spec = importlib.util.spec_from_file_location('auth_under_test', Path(__file__).with_name('auth.py'))
auth = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'streamlit': st, 'db': fake_db}):
    spec.loader.exec_module(auth)


class GuardTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()

    def test_missing_clock_fails_closed(self):
        st.session_state.update(access_token='x', refresh_token='y')
        self.assertFalse(auth.ensure_auth())
        self.assertNotIn('access_token', st.session_state)

    def test_expired_clock_fails_closed(self):
        st.session_state.update(access_token='x', refresh_token='y',
                                _iv_last_activity_monotonic=time.monotonic() - 301)
        self.assertFalse(auth.ensure_auth())
        self.assertNotIn('refresh_token', st.session_state)

    def test_activity_does_not_revive_expired_session(self):
        st.session_state.update(access_token='x',
                                _iv_last_activity_monotonic=time.monotonic() - 301)
        before = st.session_state['_iv_last_activity_monotonic']
        auth.register_user_activity()
        self.assertEqual(before, st.session_state['_iv_last_activity_monotonic'])

    def test_activity_refreshes_active_clock(self):
        old = time.monotonic() - 30
        st.session_state.update(access_token='x', _iv_last_activity_monotonic=old)
        auth.register_user_activity()
        self.assertGreater(st.session_state['_iv_last_activity_monotonic'], old)

    def test_activity_does_not_create_missing_clock(self):
        st.session_state.update(access_token='x')
        auth.register_user_activity()
        self.assertNotIn('_iv_last_activity_monotonic', st.session_state)

    def test_watchdog_expires_stale_session(self):
        st.session_state.update(access_token='x', refresh_token='y',
                                _iv_last_activity_monotonic=time.monotonic() - 301)
        self.assertTrue(auth.session_inactivity_expired())
        self.assertNotIn('access_token', st.session_state)

    def test_watchdog_keeps_active_session(self):
        st.session_state.update(access_token='x', refresh_token='y',
                                _iv_last_activity_monotonic=time.monotonic() - 15)
        self.assertFalse(auth.session_inactivity_expired())
        self.assertIn('access_token', st.session_state)

    def test_clock_rollback_fails_closed(self):
        st.session_state.update(access_token='x', refresh_token='y',
                                _iv_last_activity_monotonic=time.monotonic() + 60)
        self.assertFalse(auth.ensure_auth())
        self.assertNotIn('access_token', st.session_state)


if __name__ == '__main__':
    unittest.main()
