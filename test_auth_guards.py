"""Run: python -m unittest discover -s . -p 'test_*.py'"""
import importlib.util
import pathlib
import sys
import time
import types
import unittest

class State(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

st = types.ModuleType('streamlit')
st.session_state = State()
sys.modules['streamlit'] = st
fake_db = types.ModuleType('db')
fake_db.get_supabase = lambda: None
sys.modules['db'] = fake_db
spec = importlib.util.spec_from_file_location('auth_under_test', pathlib.Path(__file__).with_name('auth.py'))
auth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth)

class GuardTests(unittest.TestCase):
    def setUp(self):
        st.session_state.clear()
    def test_missing_clock_fails_closed(self):
        st.session_state.update(access_token='x', refresh_token='y')
        self.assertFalse(auth.ensure_auth())
        self.assertNotIn('access_token', st.session_state)
    def test_expired_clock_fails_closed(self):
        st.session_state.update(access_token='x', refresh_token='y', _iv_last_activity_monotonic=time.monotonic()-301)
        self.assertFalse(auth.ensure_auth())
        self.assertNotIn('refresh_token', st.session_state)
    def test_activity_does_not_revive_expired_session(self):
        st.session_state.update(access_token='x', _iv_last_activity_monotonic=time.monotonic()-301)
        before=st.session_state['_iv_last_activity_monotonic']
        auth.register_user_activity()
        self.assertEqual(before, st.session_state['_iv_last_activity_monotonic'])
    def test_activity_refreshes_active_clock(self):
        old=time.monotonic()-30
        st.session_state.update(access_token='x', _iv_last_activity_monotonic=old)
        auth.register_user_activity()
        self.assertGreater(st.session_state['_iv_last_activity_monotonic'],old)

if __name__ == '__main__': unittest.main()
