"""Bridge real authenticated browser activity into Streamlit's server clock.

No credentials or entitlement data is passed into the browser component.
The component is mounted only after ensure_auth() succeeds in app.py.
"""
import streamlit as st
from auth import register_user_activity

# v2 executes in the main document, not an iframe, and supports a native
# Python callback. Streamlit 1.66.1 is pinned in requirements.txt.
# Client-side activity signals are UX hints, NOT an authentication credential.
_ACTIVITY_JS = r"""
export default function (component) {
    const {setTriggerValue} = component;
    let lastReportMs = -Infinity;
    const MIN_REPORT_INTERVAL_MS = 12000;

    const onRealActivity = (event) => {
        // Ignore programmatic clicks (including native WebView's JS auth click),
        // invisible tabs, synthetic events and all passive page rerenders.
        if (!event.isTrusted || document.visibilityState !== 'visible') return;

        const now = performance.now();
        if (now - lastReportMs < MIN_REPORT_INTERVAL_MS) return;
        lastReportMs = now;
        // No user data or tokens: a fresh trigger merely runs the server
        // callback, which rechecks the existing server-side session clock.
        setTriggerValue('activity', Math.round(now));
    };

    const listeners = ['pointerdown', 'touchstart', 'keydown', 'wheel'];
    for (const type of listeners) {
        document.addEventListener(type, onRealActivity, {capture: true, passive: true});
    }
    return () => {
        for (const type of listeners) {
            document.removeEventListener(type, onRealActivity, {capture: true});
        }
    };
}
"""

activity_bridge = st.components.v2.component(
    'iv_authenticated_activity_bridge',
    html='<span hidden aria-hidden="true"></span>',
    js=_ACTIVITY_JS,
)


def render_authenticated_activity_watch():
    """Update server clock only on a real frontend input event."""
    activity_bridge(
        key='iv_authenticated_activity_bridge_widget',
        on_activity_change=register_user_activity,
    )
