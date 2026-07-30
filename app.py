import base64
import os
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from auth import ensure_auth, login_ui, logout


st.set_page_config(
    page_title="InvesTrack Pro",
    page_icon="📈",
    layout="wide",
)


# -----------------------------------------
# GLOBAL STYLING
# Keeps Streamlit's top-right menu for
# light/dark theme control.
# -----------------------------------------
st.markdown(
    """
    <style>
    :root {
        --iv-navy: #0f172a;
        --iv-green: #84cc16;
        --iv-muted: #64748b;
        --iv-border: rgba(148, 163, 184, 0.25);
    }

    footer { display: none !important; visibility: hidden !important; }
    #MainMenu { visibility: visible !important; }

    [data-testid="stStatusWidget"], [data-testid="stDecoration"],
    [data-testid="manage-app-button"], [data-testid="stToolbarActions"],
    .viewerBadge_container__1QSob, .styles_viewerBadge__1yB5_,
    .viewerBadge_link__1S137, div[class*="viewerBadge"],
    div[class*="ViewerBadge"], div[class*="stStatusWidget"],
    div[class*="stDecoration"], div[class*="deploy"],
    div[class*="Deploy"], div[class*="floating"],
    div[class*="Floating"], div[class*="badge"],
    div[class*="Badge"], div[class*="crown"],
    div[class*="Crown"], a[href*="streamlit.io"],
    a[href*="share.streamlit.io"], a[href*="github.com"] {
        display: none !important; visibility: hidden !important;
        opacity: 0 !important; pointer-events: none !important;
    }

    button[title*="Deploy"], button[aria-label*="Deploy"],
    button[title*="Fork"], button[aria-label*="Fork"],
    button[title*="GitHub"], button[aria-label*="GitHub"],
    button[title*="Upgrade"], button[aria-label*="Upgrade"],
    button[title*="Manage app"], button[aria-label*="Manage app"] {
        display: none !important; visibility: hidden !important;
        opacity: 0 !important; pointer-events: none !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #172554 55%, #0f172a 100%);
        border-right: 1px solid rgba(148,163,184,0.16);
    }
    [data-testid="stSidebar"] * { color: #e2e8f0; }
    [data-testid="stSidebar"] .stButton > button {
        width: 100%; min-height: 43px; border-radius: 12px;
        border: 1px solid rgba(148,163,184,0.18);
        background: rgba(255,255,255,0.06); color: #f8fafc;
        font-weight: 650; text-align: left; padding: .65rem .8rem;
        transition: transform .15s ease, background .15s ease;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        transform: translateX(2px);
        background: linear-gradient(90deg, rgba(132,204,22,.22), rgba(255,255,255,.08));
        border-color: rgba(132,204,22,.65);
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #65a30d, #84cc16);
        color: #0f172a; border-color: rgba(190,242,100,.65);
        box-shadow: 0 10px 25px rgba(132,204,22,.18);
    }

    .iv-sidebar-brand { text-align:center; padding:.45rem .3rem 1rem; }
    .iv-sidebar-logo {
        width:112px; height:112px; border-radius:24px; object-fit:cover;
        background:white; padding:4px; margin-bottom:.7rem;
        box-shadow:0 16px 35px rgba(0,0,0,.32);
    }
    .iv-sidebar-title { margin:0; color:white; font-size:1.18rem; font-weight:850; }
    .iv-sidebar-subtitle { margin:.22rem 0 0; color:#94a3b8; font-size:.77rem; }
    .iv-section-label {
        margin:.7rem 0 .35rem; text-transform:uppercase; letter-spacing:.12em;
        color:#94a3b8; font-size:.67rem; font-weight:750;
    }
    .iv-profile-wrap { text-align:center; padding:.55rem 0 .6rem; }
    .iv-avatar {
        width:58px; height:58px; margin:0 auto .5rem; border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        background:linear-gradient(135deg,#bef264,#65a30d); color:#172554;
        font-size:1.05rem; font-weight:900; border:3px solid rgba(255,255,255,.88);
        box-shadow:0 10px 25px rgba(132,204,22,.22);
    }
    .iv-profile-name { margin:0; color:white; font-weight:800; }
    .iv-profile-hint { margin:.15rem 0 0; color:#94a3b8; font-size:.74rem; }
    .iv-profile-panel {
        border:1px solid rgba(148,163,184,.18); border-radius:14px;
        padding:.75rem; margin:.25rem 0 .65rem; background:rgba(255,255,255,.06);
        overflow-wrap:anywhere;
    }

    .iv-hero {
        padding:clamp(2.2rem,6vw,4.4rem); border-radius:28px;
        background:radial-gradient(circle at 85% 20%,rgba(132,204,22,.3),transparent 26%),
                   radial-gradient(circle at 20% 100%,rgba(245,158,11,.18),transparent 35%),
                   linear-gradient(135deg,#0f172a,#172554 58%,#1e293b);
        color:white; margin-bottom:1.5rem; box-shadow:0 24px 55px rgba(15,23,42,.22);
    }
    .iv-hero-badge {
        display:inline-block; border-radius:999px; padding:.45rem .8rem;
        background:rgba(190,242,100,.13); border:1px solid rgba(190,242,100,.3);
        color:#d9f99d; font-size:.78rem; font-weight:800; margin-bottom:1rem;
    }
    .iv-hero h1 { font-size:clamp(2.35rem,7vw,5rem); line-height:1.01; margin:0 0 1rem; letter-spacing:-.045em; }
    .iv-hero p { font-size:clamp(1rem,2.2vw,1.2rem); max-width:760px; color:#dbeafe; }
    .iv-card {
        border:1px solid var(--iv-border); border-radius:20px; padding:1.35rem;
        min-height:190px; margin-bottom:1rem;
        background:linear-gradient(145deg,rgba(255,255,255,.86),rgba(248,250,252,.68));
        box-shadow:0 14px 35px rgba(15,23,42,.06); transition:.2s ease;
    }
    .iv-card:hover { transform:translateY(-3px); box-shadow:0 18px 42px rgba(15,23,42,.1); }
    .iv-card h3 { margin-top:0; }
    .iv-footer { border-top:1px solid var(--iv-border); margin-top:2.5rem; padding:1.5rem 0 2rem; text-align:center; font-size:.9rem; opacity:.82; }
    .iv-legal { max-width:900px; margin:0 auto; }
    </style>
    """,
    unsafe_allow_html=True,
)



# Web-triggered Android interstitial timer.
ANDROID_AD_TIMER_SECONDS = 180  # 3 minutes


# -----------------------------------------
# SAFE CONFIG LOADER
# Works with Render environment variables
# and Streamlit secrets.
# -----------------------------------------
def get_secret(key, default=""):
    environment_value = os.getenv(key)

    if environment_value:
        return environment_value

    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


LOGO_CANDIDATES = [
    Path("assets/investrack_logo.png"),
    Path("investrack_logo.png"),
    Path("INVSTRK  LOGO.png"),
]


def get_logo_path():
    for candidate in LOGO_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def image_to_data_uri(path):
    if not path:
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def get_user_initials(email):
    local = (email or "User").split("@")[0]
    cleaned = "".join(ch for ch in local if ch.isalnum())
    return (cleaned[:2] or "U").upper()


WEB_ADS_ENABLED = False

ADSENSE_CLIENT = get_secret("ADSENSE_CLIENT", "")
ADSENSE_TOP_SLOT = get_secret("ADSENSE_TOP_SLOT", "")
ADSENSE_BOTTOM_SLOT = get_secret("ADSENSE_BOTTOM_SLOT", "")
ADSENSE_SIDEBAR_SLOT = get_secret("ADSENSE_SIDEBAR_SLOT", "")


# -----------------------------------------
# AD SLOT
# -----------------------------------------
def render_ad_slot(label="Sponsored", slot_id="", height=120):
    # Web ad areas remain fully hidden during AdSense review.
    # Change WEB_ADS_ENABLED to True only after approval and valid slots exist.
    if not WEB_ADS_ENABLED:
        return

    if not ADSENSE_CLIENT or not slot_id:
        return

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

    components.html(
        ad_html,
        height=height,
    )


# -----------------------------------------
# COMMON SITE NAVIGATION
# -----------------------------------------
PUBLIC_PAGES = [
    ("Home", "🏠"),
    ("About", "ℹ️"),
    ("Privacy", "🔒"),
    ("Terms", "📜"),
    ("Contact", "✉️"),
    ("Login", "🔑"),
]


def navigate(page_name):
    st.session_state.pending_public_page = page_name
    st.rerun()


def apply_pending_navigation(valid_pages, authenticated):
    pending_page = st.session_state.pop("pending_public_page", None)
    if pending_page:
        if pending_page == "Dashboard" and not authenticated:
            pending_page = "Login"
        if pending_page in valid_pages:
            st.session_state.public_navigation = pending_page


def render_sidebar_brand():
    logo_uri = image_to_data_uri(get_logo_path())
    logo_html = (
        f'<img class="iv-sidebar-logo" src="{logo_uri}" alt="InvesTrack Pro logo">'
        if logo_uri else '<div class="iv-avatar">IP</div>'
    )
    st.sidebar.markdown(
        f"""
        <div class="iv-sidebar-brand">
            {logo_html}
            <p class="iv-sidebar-title">InvesTrack Pro</p>
            <p class="iv-sidebar-subtitle">Smart portfolio tracking</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_navigation_buttons(items, selected_page):
    st.sidebar.markdown('<div class="iv-section-label">Navigation</div>', unsafe_allow_html=True)
    for page_name, icon in items:
        if st.sidebar.button(
            f"{icon}  {page_name}",
            key=f"nav_{page_name.lower()}",
            type="primary" if page_name == selected_page else "secondary",
            use_container_width=True,
        ):
            navigate(page_name)


def render_profile_section(user):
    email = getattr(user, "email", "") or ""
    initials = get_user_initials(email)
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"""
        <div class="iv-profile-wrap">
            <div class="iv-avatar">{initials}</div>
            <p class="iv-profile-name">My profile</p>
            <p class="iv-profile-hint">Tap below for account details</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if "profile_panel_open" not in st.session_state:
        st.session_state.profile_panel_open = False
    if st.sidebar.button("👤  Profile", key="toggle_profile_panel", use_container_width=True):
        st.session_state.profile_panel_open = not st.session_state.profile_panel_open
        st.rerun()
    if st.session_state.profile_panel_open:
        st.sidebar.markdown(
            f'<div class="iv-profile-panel"><strong>Signed in</strong><br><small>{email}</small></div>',
            unsafe_allow_html=True,
        )
        if st.sidebar.button("📈  Open Dashboard", key="profile_open_dashboard", use_container_width=True):
            navigate("Dashboard")
        if st.sidebar.button("🚪  Logout", key="profile_logout", use_container_width=True):
            logout()
            st.stop()


def render_public_navigation():
    authenticated = ensure_auth()
    navigation_items = PUBLIC_PAGES.copy()
    if authenticated:
        navigation_items.append(("Dashboard", "📈"))
    valid_pages = [name for name, _ in navigation_items]
    apply_pending_navigation(valid_pages, authenticated)
    default_page = "Dashboard" if authenticated else "Home"
    selected_page = st.session_state.get("public_navigation", default_page)
    if selected_page not in valid_pages:
        selected_page = default_page
        st.session_state.public_navigation = selected_page
    render_sidebar_brand()
    render_navigation_buttons(navigation_items, selected_page)
    if authenticated:
        user = st.session_state.get("user")
        if user:
            render_profile_section(user)
    else:
        st.sidebar.markdown("---")
        st.sidebar.caption("Create a free account to track your portfolio.")
        if st.sidebar.button("✨  Start Free", key="sidebar_start_free", type="primary", use_container_width=True):
            navigate("Login")
    return selected_page, authenticated


# -----------------------------------------
# PUBLIC FOOTER
# -----------------------------------------
def render_public_footer():
    st.markdown(
        """
        <div class="iv-footer">
            <strong>InvesTrack Pro</strong><br>
            Portfolio tracking for stocks, cryptocurrency and cash holdings.<br><br>
            © 2026 InvesTrack Pro. All rights reserved.
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------
# HOME PAGE
# -----------------------------------------
def render_home_page(authenticated):
    st.markdown(
        """
        <div class="iv-hero">
            <div class="iv-hero-badge">ONE PORTFOLIO • EVERY ASSET</div>
            <h1>Know where your money stands.</h1>
            <p>
                Track stocks, cryptocurrency and cash holdings from one
                polished dashboard. See your portfolio clearly and make
                better-informed decisions with less effort.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    first_button, second_button, spacer = st.columns(
        [1, 1, 2]
    )

    with first_button:
        if authenticated:
            if st.button(
                "Open Dashboard",
                key="home_open_dashboard",
                type="primary",
                use_container_width=True,
            ):
                navigate("Dashboard")
        else:
            if st.button(
                "Start Tracking Free",
                key="home_start_tracking",
                type="primary",
                use_container_width=True,
            ):
                navigate("Login")

    with second_button:
        if st.button(
            "Explore Features",
            key="home_learn_more",
            use_container_width=True,
        ):
            navigate("About")

    st.markdown("## Everything you need to monitor your portfolio")

    feature_one, feature_two, feature_three = st.columns(3)

    with feature_one:
        st.markdown(
            """
            <div class="iv-card">
                <h3>📊 Unified portfolio</h3>
                Track stocks, cryptocurrency and cash holdings from one
                secure account.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with feature_two:
        st.markdown(
            """
            <div class="iv-card">
                <h3>📈 Performance insights</h3>
                Review portfolio value, gains, losses and historical
                performance over time.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with feature_three:
        st.markdown(
            """
            <div class="iv-card">
                <h3>🌍 Multi-currency view</h3>
                View your investment portfolio in a currency that is
                meaningful to you.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("## Built for investors who value clarity")

    st.write(
        """
        Whether you are tracking your first cryptocurrency holding or
        monitoring a growing stock portfolio, InvesTrack Pro gives you
        a clearer view of your investments without unnecessary complexity.
        """
    )

    render_ad_slot(
        label="Sponsored",
        slot_id=ADSENSE_BOTTOM_SLOT,
        height=120,
    )

    render_public_footer()


# -----------------------------------------
# ABOUT PAGE
# -----------------------------------------
def render_about_page():
    st.title("About InvesTrack Pro")

    st.markdown(
        """
        <div class="iv-legal">
        InvesTrack Pro is a portfolio management platform created to make
        investment tracking simpler, clearer and more accessible.

        The platform allows users to monitor cryptocurrency, stock and cash
        holdings through a unified dashboard. Users can review portfolio
        values, performance history and asset allocation without maintaining
        separate spreadsheets or switching between multiple applications.

        ### Our mission

        Our mission is to give everyday investors a convenient and
        understandable way to monitor their financial assets.

        ### What InvesTrack Pro provides

        - Cryptocurrency portfolio tracking
        - Stock portfolio tracking
        - Cash holding records
        - Portfolio value and performance summaries
        - Historical portfolio tracking
        - Multi-currency portfolio display
        - Secure account authentication

        ### Important information

        InvesTrack Pro is an information and portfolio-tracking service.
        It does not provide personalised financial, investment, tax or
        legal advice. Users remain responsible for their own investment
        decisions.
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_public_footer()


# -----------------------------------------
# PRIVACY POLICY
# -----------------------------------------
def render_privacy_page():
    st.title("Privacy Policy")
    st.caption("Last updated: January 2026")

    st.markdown(
        """
        <div class="iv-legal">

        InvesTrack Pro respects your privacy and is committed to protecting
        your personal data.

        ### Information we collect

        We collect only information reasonably necessary to operate and
        improve the service. This may include:

        - Your email address, used for account registration and authentication
        - Portfolio information entered by you, including stocks,
          cryptocurrency holdings, cash values and related portfolio data
        - Technical and usage information such as app version, device type,
          session activity and feature usage
        - Advertising identifiers and related information where advertising
          services are enabled

        ### How we use your information

        We use information to:

        - Authenticate and manage user accounts
        - Save and display portfolio information
        - Calculate and present portfolio analytics
        - Maintain, secure and improve the service
        - Diagnose technical problems
        - Understand how users interact with InvesTrack Pro
        - Display and measure advertising where advertising is enabled

        ### Authentication and data storage

        InvesTrack Pro uses Supabase for account authentication and data
        storage. Information submitted through the platform may be processed
        and stored through Supabase infrastructure.

        ### Analytics

        InvesTrack Pro may use Firebase Analytics and similar technologies
        to understand app usage, session activity, device information and
        feature engagement.

        Analytics information helps us improve performance, reliability and
        user experience.

        ### Advertising

        InvesTrack Pro may use Google AdMob in the Android application and
        Google advertising services on the website.

        Google and its advertising partners may use cookies, advertising
        identifiers, device information or similar technologies for:

        - Advertising delivery
        - Ad measurement
        - Fraud and abuse prevention
        - Frequency management
        - Reporting and analytics

        We do not use the Android Advertising ID to personally identify
        individual users.

        Users may reset or limit the use of advertising identifiers through
        their Android device settings.

        ### Cookies and local storage

        The website may use cookies, browser storage or similar technologies
        to maintain sessions, support authentication, remember preferences,
        measure usage and provide advertising.

        ### Data sharing

        We do not sell or rent personal information.

        Information may be processed by service providers that help operate
        InvesTrack Pro, including hosting, authentication, database,
        analytics and advertising providers.

        We may disclose information where required by law, regulation,
        legal process or a valid governmental request.

        ### Data security

        We use reasonable technical and organisational safeguards to protect
        information. Data is transmitted over encrypted connections where
        supported.

        No online service can guarantee absolute security, and users should
        protect their login credentials and devices.

        ### User control and account deletion

        Users may request deletion of their account and associated personal
        information by contacting us.

        Some information may be retained where required for security, legal,
        fraud-prevention or regulatory purposes.

        ### Children's privacy

        InvesTrack Pro is not intended for children under the minimum age
        required to independently consent to online services in their
        jurisdiction.

        ### Third-party services

        InvesTrack Pro may use third-party services including:

        - Supabase
        - Firebase
        - Google Analytics for Firebase
        - Google AdMob
        - Google AdSense
        - Render
        - Market-data and financial-data providers

        These services process information according to their own privacy
        policies and legal obligations.

        ### Changes to this policy

        We may update this Privacy Policy to reflect changes in the service,
        technology, legal requirements or business practices.

        The updated date displayed on this page will be revised when
        material changes are made.

        ### Contact

        Questions, privacy requests and account-deletion requests may be
        sent to:

        **Email:** hassbuildllc@gmail.com

        </div>
        """,
        unsafe_allow_html=True,
    )

    render_public_footer()


# -----------------------------------------
# TERMS PAGE
# -----------------------------------------
def render_terms_page():
    st.title("Terms and Conditions")
    st.caption("Last updated: January 2026")

    st.markdown(
        """
        <div class="iv-legal">

        These Terms and Conditions govern access to and use of InvesTrack Pro.

        By creating an account or using the platform, you agree to these
        terms.

        ### 1. Service description

        InvesTrack Pro provides tools for recording, organising and reviewing
        investment portfolio information.

        The platform may include stock tracking, cryptocurrency tracking,
        cash holdings, charts, portfolio history, analytics and related
        informational features.

        ### 2. Not financial advice

        Information displayed by InvesTrack Pro is provided for general
        informational and portfolio-tracking purposes only.

        InvesTrack Pro does not provide personalised:

        - Financial advice
        - Investment advice
        - Trading advice
        - Tax advice
        - Legal advice

        Users should obtain appropriate professional advice before making
        financial decisions.

        ### 3. Market data

        Prices, exchange rates, charts and other market information may be
        obtained from third-party data providers.

        Market information may be delayed, incomplete or inaccurate.
        InvesTrack Pro does not guarantee the accuracy, completeness or
        availability of market data.

        ### 4. User accounts

        Users are responsible for:

        - Providing accurate account information
        - Maintaining the confidentiality of login credentials
        - Protecting access to their devices
        - All activity performed through their account

        Users should contact us promptly if they believe their account has
        been accessed without authorisation.

        ### 5. User-submitted information

        Users are responsible for portfolio information they enter into the
        platform.

        InvesTrack Pro is not responsible for losses or incorrect analysis
        resulting from inaccurate, incomplete or outdated user entries.

        ### 6. Acceptable use

        Users must not:

        - Attempt to gain unauthorised access to the platform or its systems
        - Interfere with service operation or security
        - Introduce malicious software
        - Scrape, reverse engineer or abuse the service
        - Use the platform for unlawful or fraudulent purposes
        - Attempt to manipulate advertising impressions or clicks

        ### 7. Intellectual property

        The InvesTrack Pro name, software, design, branding and original
        content are protected by applicable intellectual-property laws.

        These terms do not transfer ownership of InvesTrack Pro or its
        intellectual property to users.

        ### 8. Third-party services

        The platform may rely on third-party services for hosting,
        authentication, analytics, advertising, market data and related
        functions.

        We are not responsible for interruptions, errors or actions caused
        by third-party providers.

        ### 9. Advertising

        InvesTrack Pro may display advertisements supplied by third-party
        advertising platforms.

        Users must not artificially generate impressions, clicks or other
        advertising interactions.

        ### 10. Availability and changes

        We may update, modify, suspend or discontinue parts of the service.

        We do not guarantee uninterrupted or error-free availability.

        ### 11. Limitation of liability

        To the fullest extent permitted by law, InvesTrack Pro and its
        operators will not be liable for investment losses, trading losses,
        lost profits, lost data or indirect, incidental, special or
        consequential damages arising from use of the platform.

        ### 12. Account suspension or termination

        We may restrict or terminate access where a user violates these terms,
        threatens platform security, abuses advertising systems or engages in
        unlawful activity.

        ### 13. Changes to these terms

        We may update these Terms and Conditions periodically.

        Continued use after an update constitutes acceptance of the revised
        terms.

        ### 14. Contact

        Questions about these terms may be sent to:

        **Email:** hassbuildllc@gmail.com

        </div>
        """,
        unsafe_allow_html=True,
    )

    render_public_footer()


# -----------------------------------------
# CONTACT PAGE
# -----------------------------------------
def render_contact_page():
    st.title("Contact InvesTrack Pro")

    st.write(
        """
        Contact us for technical support, account assistance, privacy
        enquiries, feedback or business enquiries.
        """
    )

    left_column, right_column = st.columns([1, 1])

    with left_column:
        st.markdown(
            """
            ### Support

            **Email:** hassbuildllc@gmail.com

            Please include:

            - A brief description of the issue
            - Your device type
            - Your app version, where relevant
            - Any error message you received

            Never send your password or full authentication credentials.
            """
        )

    with right_column:
        st.markdown(
            """
            ### Account and privacy requests

            You may use the same email address for:

            - Account assistance
            - Account deletion requests
            - Privacy enquiries
            - Data-access requests
            - Advertising or partnership enquiries

            We aim to review genuine enquiries as promptly as reasonably
            possible.
            """
        )

    render_public_footer()


# -----------------------------------------
# PARTNER CTA
# -----------------------------------------
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
            <h4 style="margin:0 0 8px 0;">
                🚀 Pro Investor Tools Coming Soon
            </h4>

            <p style="margin:0; color:#d1d5db;">
                Advanced analytics, exportable reports, portfolio scoring,
                and market insights.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------
# ANDROID AD TIMER
# Only active after authentication.
# -----------------------------------------
def render_android_ad_timer():
    components.html(
        f"""
        <script>
            (function() {{
                if (window.__investrackAdTimerStarted) {{
                    return;
                }}

                window.__investrackAdTimerStarted = true;

                function triggerAndroidAd() {{
                    var now = Math.floor(Date.now() / 1000);

                    var intentUrl =
                        "intent://show-ad?reason=active_usage&t=" + now +
                        "#Intent;" +
                        "scheme=investrackpro;" +
                        "package=com.investrackpro.app;" +
                        "end";

                    try {{
                        window.top.location.href = intentUrl;
                    }} catch (e) {{
                        try {{
                            window.parent.location.href = intentUrl;
                        }} catch (e2) {{
                            window.location.href = intentUrl;
                        }}
                    }}
                }}

                setInterval(
                    triggerAndroidAd,
                    {ANDROID_AD_TIMER_SECONDS * 1000}
                );
            }})();
        </script>
        """,
        height=0,
    )


# -----------------------------------------
# AUTHENTICATED DASHBOARD
# -----------------------------------------
def render_dashboard():
    if not ensure_auth():
        st.warning(
            "Please log in to access your portfolio dashboard."
        )

        if st.button(
            "Go to Login",
            key="dashboard_go_to_login",
            type="primary",
        ):
            navigate("Login")

        return

    if (
        "user" not in st.session_state
        or "user_id" not in st.session_state
    ):
        st.error("Session expired. Please log in again.")
        logout()
        st.stop()

    user = st.session_state.user

    render_android_ad_timer()

    refresh_interval = 60
    current_time = time.time()

    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = current_time

    elif (
        current_time - st.session_state.last_refresh
        > refresh_interval
    ):
        st.session_state.last_refresh = current_time
        st.rerun()

    mode_options = ["Crypto", "Stocks"]

    if "selected_mode" not in st.session_state:
        st.session_state.selected_mode = "Crypto"

    if st.session_state.selected_mode not in mode_options:
        st.session_state.selected_mode = "Crypto"

    def on_mode_change():
        new_mode = st.session_state.mode_radio

        if new_mode in mode_options:
            st.session_state.selected_mode = new_mode


    st.sidebar.radio(
        "Select Mode",
        mode_options,
        index=mode_options.index(
            st.session_state.selected_mode
        ),
        key="mode_radio",
        on_change=on_mode_change,
    )

    mode = st.session_state.selected_mode

    render_ad_slot(
        label="Sidebar Sponsored Slot",
        slot_id=ADSENSE_SIDEBAR_SLOT,
        height=120,
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

    except Exception as error:
        st.error(
            "Something went wrong. Please refresh the app."
        )
        print(
            "APP ERROR:",
            type(error).__name__,
            error,
        )

    st.markdown("---")

    render_partner_cta()

    render_ad_slot(
        label="Bottom Sponsored Slot",
        slot_id=ADSENSE_BOTTOM_SLOT,
        height=120,
    )


# -----------------------------------------
# MAIN ROUTER
# -----------------------------------------
selected_page, user_is_authenticated = (
    render_public_navigation()
)

if selected_page == "Home":
    render_home_page(user_is_authenticated)

elif selected_page == "About":
    render_about_page()

elif selected_page == "Privacy":
    render_privacy_page()

elif selected_page == "Terms":
    render_terms_page()

elif selected_page == "Contact":
    render_contact_page()

elif selected_page == "Login":
    if user_is_authenticated:
        st.success(
            "You are already logged in."
        )

        if st.button(
            "Go to Dashboard",
            key="login_go_to_dashboard",
            type="primary",
        ):
            navigate("Dashboard")

    else:
        login_ui()

    render_public_footer()

elif selected_page == "Dashboard":
    render_dashboard()

else:
    render_home_page(user_is_authenticated)
