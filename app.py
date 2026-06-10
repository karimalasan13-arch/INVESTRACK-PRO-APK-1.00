import streamlit as st
import time
import streamlit.components.v1 as components

from auth import login_ui, ensure_auth, logout


st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide",
)


SHOW_AD_PLACEHOLDERS = True
INTERSTITIAL_COOLDOWN_SECONDS = 300


def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


ADSENSE_CLIENT = get_secret("ADSENSE_CLIENT", "")
ADSENSE_TOP_SLOT = get_secret("ADSENSE_TOP_SLOT", "")
ADSENSE_BOTTOM_SLOT = get_secret("ADSENSE_BOTTOM_SLOT", "")
ADSENSE_SIDEBAR_SLOT = get_secret("ADSENSE_SIDEBAR_SLOT", "")


def render_ad_slot(label="Sponsored", slot_id="", height=120):
    if ADSENSE_CLIENT and slot_id:
        ad_html = f"""
        <div style="width:100%; text-align:center; margin:10px 0;">
            <script async
                src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}"
                crossorigin="anonymous"></script>

            <ins class="adsbygoogle"
                style="display:block"
                data-ad-client="{ADSENSE_CLIENT}"
                data-ad-slot="{slot_id}"
                data-ad-format="auto"
                data-full-width-responsive="true"></ins>

            <script>
                (adsbygoogle = window.adsbygoogle || []).push({{}});
            </script>
        </div>
        """
        components.html(ad_html, height=height)

    elif SHOW_AD_PLACEHOLDERS:
        st.markdown(
            f"""
            <div style="
                border:1px dashed #cfcfcf;
                border-radius:12px;
                padding:14px;
                text-align:center;
                color:#777;
                background:#fafafa;
                margin:10px 0;
            ">
                <strong>{label}</strong><br>
                Ad placement ready
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_partner_cta():
    st.markdown(
        """
        <div style="
            border-radius:14px;
            padding:18px;
            background:linear-gradient(135deg,#0f172a,#1e293b);
            color:white;
            margin:14px 0;
        ">
            <h4 style="margin:0 0 8px 0;">🚀 Pro Investor Tools Coming Soon</h4>
            <p style="margin:0; color:#d1d5db;">
                Advanced analytics, exportable reports, portfolio scoring, and market insights.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def request_interstitial(reason="mode_switch"):
    now = time.time()
    last_trigger = st.session_state.get("last_interstitial_trigger", 0)

    if now - last_trigger < INTERSTITIAL_COOLDOWN_SECONDS:
        return

    st.session_state.last_interstitial_trigger = now
    st.session_state.pending_interstitial_reason = reason
    st.session_state.pending_interstitial_time = int(now)


def render_pending_interstitial():
    reason = st.session_state.pop("pending_interstitial_reason", None)
    trigger_time = st.session_state.pop("pending_interstitial_time", None)

    if not reason or not trigger_time:
        return

    components.html(
        f"""
        <script>
            setTimeout(function() {{
                try {{
                    window.top.location.href =
                        "investrackpro://show-interstitial?reason={reason}&t={trigger_time}";
                }} catch (e) {{
                    window.location.href =
                        "investrackpro://show-interstitial?reason={reason}&t={trigger_time}";
                }}
            }}, 500);
        </script>
        """,
        height=0,
    )


if not ensure_auth():
    login_ui()
    st.stop()


if "user" not in st.session_state or "user_id" not in st.session_state:
    st.error("Session expired. Please login again.")
    logout()
    st.stop()

user = st.session_state.user
user_id = st.session_state.user_id


REFRESH_INTERVAL = 60
now = time.time()

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = now
elif now - st.session_state.last_refresh > REFRESH_INTERVAL:
    st.session_state.last_refresh = now
    st.rerun()


MODE_OPTIONS = ["Crypto", "Stocks"]

if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = "Crypto"

if st.session_state.selected_mode not in MODE_OPTIONS:
    st.session_state.selected_mode = "Crypto"


def on_mode_change():
    new_mode = st.session_state.mode_radio
    old_mode = st.session_state.get("selected_mode", "Crypto")

    if new_mode in MODE_OPTIONS:
        st.session_state.selected_mode = new_mode

    if old_mode != new_mode:
        request_interstitial("mode_switch")


st.sidebar.success(f"Logged in as\n{user.email}")

if st.sidebar.button("Logout"):
    logout()
    st.stop()

st.sidebar.radio(
    "Select Mode",
    MODE_OPTIONS,
    index=MODE_OPTIONS.index(st.session_state.selected_mode),
    key="mode_radio",
    on_change=on_mode_change,
)

mode = st.session_state.selected_mode

render_pending_interstitial()

st.sidebar.markdown("---")

render_ad_slot(
    label="Sidebar Sponsored Slot",
    slot_id=ADSENSE_SIDEBAR_SLOT,
    height=120,
)

st.sidebar.markdown(
    """
    ---
    🗑 **Delete Account**

    Email **hassbuildllc@gmail.com**
    """
)


render_ad_slot(
    label="Top Sponsored Slot",
    slot_id=ADSENSE_TOP_SLOT,
    height=120,
)


try:
    if mode == "Crypto":
        from crypto_mode import crypto_app
        crypto_app()

    elif mode == "Stocks":
        from stock_mode import stock_app
        stock_app()

except Exception as e:
    st.error("Something went wrong. Please refresh the app.")
    print("APP ERROR:", type(e).__name__, e)


st.markdown("---")

render_partner_cta()

render_ad_slot(
    label="Bottom Sponsored Slot",
    slot_id=ADSENSE_BOTTOM_SLOT,
    height=120,
)
