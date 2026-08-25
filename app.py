import base64
import html
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

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

    /* Sidebar form controls: keep white fields but force readable dark text. */
    [data-testid="stSidebar"] input {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        caret-color: #0f172a !important;
        opacity: 1 !important;
    }

    [data-testid="stSidebar"] input::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }

    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: #ffffff !important;
        color: #0f172a !important;
    }

    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }

    [data-testid="stSidebar"] [data-testid="stNumberInput"] button {
        background: #ffffff !important;
        color: #334155 !important;
    }

    [data-testid="stSidebar"] [data-testid="stNumberInput"] button svg,
    [data-testid="stSidebar"] [data-baseweb="select"] svg {
        fill: #334155 !important;
        color: #334155 !important;
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

    .iv-section-shell {border:1px solid var(--iv-border);border-radius:22px;padding:1.4rem;margin:1rem 0 1.4rem;background:linear-gradient(145deg,rgba(255,255,255,.88),rgba(248,250,252,.72));box-shadow:0 14px 35px rgba(15,23,42,.05);}
    .iv-kicker {display:inline-block;padding:.32rem .7rem;border-radius:999px;background:rgba(132,204,22,.12);border:1px solid rgba(132,204,22,.25);color:#4d7c0f;font-size:.75rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;margin-bottom:.55rem;}
    .iv-info-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin:1rem 0 1.4rem;}
    .iv-info-card {border:1px solid var(--iv-border);border-radius:18px;padding:1.15rem;background:rgba(255,255,255,.82);box-shadow:0 10px 28px rgba(15,23,42,.05);}
    .iv-info-card h4 {margin:.1rem 0 .45rem;}
    .iv-info-card p {margin:.1rem 0;color:#475569;line-height:1.55;}
    .iv-impact-high,.iv-impact-medium,.iv-impact-low {display:inline-block;border-radius:999px;padding:.2rem .55rem;font-size:.7rem;font-weight:800;}
    .iv-impact-high {background:#fee2e2;color:#991b1b;}
    .iv-impact-medium {background:#fef3c7;color:#92400e;}
    .iv-impact-low {background:#dcfce7;color:#166534;}
    .iv-article {border:1px solid var(--iv-border);border-radius:20px;padding:1.35rem;margin:1rem 0;background:rgba(255,255,255,.82);}
    .iv-article h3 {margin-top:.15rem;}
    .iv-note {border-left:4px solid #84cc16;background:rgba(132,204,22,.08);border-radius:10px;padding:.9rem 1rem;margin:1rem 0;color:#334155;}
    .iv-news-card {border:1px solid var(--iv-border);border-radius:18px;padding:1.1rem 1.2rem;margin:.8rem 0;background:rgba(255,255,255,.86);box-shadow:0 10px 28px rgba(15,23,42,.05);}
    .iv-news-card h4 {margin:.25rem 0 .45rem;line-height:1.35;}
    .iv-news-meta {font-size:.78rem;color:#64748b;margin-bottom:.5rem;}
    .iv-news-desc {color:#475569;line-height:1.55;margin:.2rem 0 .7rem;}
    .iv-live-dot {display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;margin-right:.35rem;box-shadow:0 0 0 4px rgba(34,197,94,.12);}
    .iv-ad-label {font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;text-align:center;margin:.35rem 0 .2rem;}
    .iv-trust-strip {border:1px solid var(--iv-border);border-radius:16px;padding:.9rem 1rem;margin:1rem 0 1.4rem;background:rgba(248,250,252,.72);color:#475569;line-height:1.55;}
    @media (max-width:900px){.iv-info-grid{grid-template-columns:1fr;}}
    </style>
    """,
    unsafe_allow_html=True,
)



# Web-triggered Android interstitial timer.
ANDROID_AD_TIMER_SECONDS = 180  # 3 minutes

# Official InvesTrack Pro Google Play listing
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.investrackpro.app&pcampaignid=web_share"
PLAY_STORE_BADGE = Path(__file__).parent / "static" / "google-play-badge.png"


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


MARKETAUX_API_TOKEN = get_secret("MARKETAUX_API_TOKEN", "")
MARKETAUX_NEWS_URL = "https://api.marketaux.com/v1/news/all"

# -----------------------------------------
# ADSENSE CONFIGURATION
# Public web ads stay off by default. After AdSense approval, set
# WEB_ADS_ENABLED=true and provide the client + slot IDs in Render
# environment variables or Streamlit secrets.
# -----------------------------------------
WEB_ADS_ENABLED = str(get_secret("WEB_ADS_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
ADSENSE_CLIENT = get_secret("ADSENSE_CLIENT", "")
ADSENSE_TOP_SLOT = get_secret("ADSENSE_TOP_SLOT", "")
ADSENSE_MID_SLOT = get_secret("ADSENSE_MID_SLOT", "")
ADSENSE_BOTTOM_SLOT = get_secret("ADSENSE_BOTTOM_SLOT", "")


def render_ad_slot(slot_id="", height=120):
    """Render an AdSense unit only when web advertising is explicitly enabled."""
    if not WEB_ADS_ENABLED or not ADSENSE_CLIENT or not slot_id:
        return

    safe_client = html.escape(str(ADSENSE_CLIENT), quote=True)
    safe_slot = html.escape(str(slot_id), quote=True)
    components.html(
        f"""
        <div style="width:100%;text-align:center;margin:10px 0 18px;">
          <div style="font:10px Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;margin-bottom:4px;">Advertisement</div>
          <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={safe_client}" crossorigin="anonymous"></script>
          <ins class="adsbygoogle" style="display:block" data-ad-client="{safe_client}" data-ad-slot="{safe_slot}" data-ad-format="auto" data-full-width-responsive="true"></ins>
          <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
        </div>
        """,
        height=height,
    )


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_marketaux_news():
    """
    Fetch a quota-conscious, cached snapshot of the latest English-language
    financial-market news. The free Marketaux plan currently returns up to
    three articles per request, so one cached request supplies both the
    homepage and Markets & Economy page.
    """
    if not MARKETAUX_API_TOKEN:
        return {
            "ok": False,
            "articles": [],
            "message": "Live market news is not configured yet.",
        }

    params = {
        "api_token": MARKETAUX_API_TOKEN,
        "language": "en",
        "limit": 3,
        "sort": "published_at",
    }

    try:
        response = requests.get(
            MARKETAUX_NEWS_URL,
            params=params,
            timeout=12,
        )

        if response.status_code != 200:
            return {
                "ok": False,
                "articles": [],
                "message": "Live market news is temporarily unavailable.",
            }

        payload = response.json()
        articles = payload.get("data", [])

        if not isinstance(articles, list):
            articles = []

        return {
            "ok": True,
            "articles": articles,
            "message": "",
        }

    except (requests.RequestException, ValueError):
        return {
            "ok": False,
            "articles": [],
            "message": "Live market news is temporarily unavailable.",
        }


def format_news_time(value):
    if not value:
        return ""

    try:
        normalized = value.replace("Z", "+00:00")
        published = datetime.fromisoformat(normalized)

        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        published = published.astimezone(timezone.utc)
        return published.strftime("%d %b %Y · %H:%M UTC")
    except Exception:
        return ""


def render_live_market_news(compact=False):
    """
    Render the cached Marketaux news snapshot.
    `compact=True` is used on the homepage; the full version is shown
    on Markets & Economy.
    """
    result = fetch_marketaux_news()
    articles = result.get("articles", [])

    if not result.get("ok") or not articles:
        if not compact:
            st.markdown(
                f"""
                <div class="iv-note">
                    <strong>Live news:</strong>
                    {html.escape(result.get("message", "Live market news is temporarily unavailable."))}
                    The educational market guides below remain available.
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    if compact:
        st.markdown("## Latest Market News")
        st.caption("A live snapshot of global financial-market headlines.")
    else:
        st.markdown("### Latest Market News")
        st.markdown(
            """
            <div class="iv-note">
                <span class="iv-live-dot"></span>
                <strong>Live feed:</strong> Headlines are supplied by Marketaux
                and link to the original publishers. InvesTrack Pro does not
                rewrite or present them as investment recommendations.
            </div>
            """,
            unsafe_allow_html=True,
        )

    visible_articles = articles[:3]

    for index, article in enumerate(visible_articles):
        title = html.escape(str(article.get("title") or "Market update"))
        description = article.get("description") or article.get("snippet") or ""
        description = html.escape(str(description)).strip()
        source = html.escape(str(article.get("source") or "Source"))
        published = html.escape(format_news_time(str(article.get("published_at") or "")))
        url = str(article.get("url") or "").strip()

        if compact and len(description) > 180:
            description = description[:177].rstrip() + "…"
        elif len(description) > 320:
            description = description[:317].rstrip() + "…"

        meta_parts = [part for part in [source, published] if part]
        meta = " · ".join(meta_parts)

        st.markdown(
            f"""
            <div class="iv-news-card">
                <div class="iv-news-meta">{meta}</div>
                <h4>{title}</h4>
                <div class="iv-news-desc">{description}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if url:
            st.link_button(
                "Read original article ↗",
                url,
                key=f"marketaux_article_{'home' if compact else 'markets'}_{index}",
            )


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


# -----------------------------------------
# SEO + SHAREABLE PUBLIC URL ROUTING
# -----------------------------------------
SITE_URL = "https://investrackpro.com"

PAGE_QUERY_MAP = {
    "Home": "home",
    "Markets & Economy": "markets",
    "Investor Tools": "tools",
    "Learn": "learn",
    "Editorial": "editorial",
    "About": "about",
    "Privacy": "privacy",
    "Terms": "terms",
    "Contact": "contact",
    "Login": "login",
    "Dashboard": "dashboard",
}
QUERY_PAGE_MAP = {value: key for key, value in PAGE_QUERY_MAP.items()}

def sync_route_from_url():
    """Read shareable query parameters into Streamlit session state."""
    article_slug = str(st.query_params.get("article", "") or "").strip()
    page_key = str(st.query_params.get("page", "") or "").strip().lower()

    if article_slug and article_slug in LEARN_ARTICLES:
        st.session_state.public_navigation = "Learn"
        st.session_state.learn_article_slug = article_slug
        return

    if page_key in QUERY_PAGE_MAP:
        st.session_state.public_navigation = QUERY_PAGE_MAP[page_key]
        if QUERY_PAGE_MAP[page_key] != "Learn":
            st.session_state.pop("learn_article_slug", None)

def write_route_to_url(page_name, article_slug=None):
    """Keep the browser URL shareable without changing the Streamlit app structure."""
    st.query_params.clear()
    if article_slug:
        st.query_params["article"] = article_slug
    elif page_name != "Home":
        page_key = PAGE_QUERY_MAP.get(page_name)
        if page_key:
            st.query_params["page"] = page_key

# -----------------------------------------
# COMMON SITE NAVIGATION
# -----------------------------------------
PUBLIC_PAGES = [
    ("Home", "🏠"),
    ("Markets & Economy", "🌐"),
    ("Investor Tools", "🧮"),
    ("Learn", "📚"),
    ("Editorial", "🛡️"),
    ("About", "ℹ️"),
    ("Privacy", "🔒"),
    ("Terms", "📜"),
    ("Contact", "✉️"),
    ("Login", "🔑"),
]


def navigate(page_name):
    if page_name != "Learn":
        st.session_state.pop("learn_article_slug", None)

    write_route_to_url(page_name)
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
            Portfolio tracking for stocks, ETFs, bonds, cryptocurrency and cash holdings.<br><br>
        </div>
        """,
        unsafe_allow_html=True,
    )

    footer_left, footer_store, footer_right = st.columns([1.5, 1, 1.5])
    with footer_store:
        if PLAY_STORE_BADGE.exists():
            st.image(
                str(PLAY_STORE_BADGE),
                width=190,
                link=PLAY_STORE_URL,
            )
        else:
            st.link_button(
                "Get it on Google Play",
                PLAY_STORE_URL,
                use_container_width=True,
            )

    footer_policy_left, footer_policy_mid, footer_policy_right = st.columns(3)
    with footer_policy_left:
        if st.button("Editorial Policy", key=f"footer_editorial_{st.session_state.get('public_navigation','page')}_{st.session_state.get('learn_article_slug','')}", use_container_width=True):
            navigate("Editorial")
    with footer_policy_mid:
        if st.button("Privacy", key=f"footer_privacy_{st.session_state.get('public_navigation','page')}_{st.session_state.get('learn_article_slug','')}", use_container_width=True):
            navigate("Privacy")
    with footer_policy_right:
        if st.button("Contact", key=f"footer_contact_{st.session_state.get('public_navigation','page')}_{st.session_state.get('learn_article_slug','')}", use_container_width=True):
            navigate("Contact")

    st.markdown(
        """
        <div class="iv-footer" style="border-top:none;margin-top:.4rem;padding-top:.4rem;">
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
                Track stocks, cryptocurrency and cash holdings from one polished dashboard —
                and use InvesTrack Pro's public market education, investor tools and economic
                insights to understand the forces moving markets.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    first_button, second_button, third_button = st.columns([1, 1, 1])
    with first_button:
        if authenticated:
            if st.button("Open Dashboard", key="home_open_dashboard", type="primary", use_container_width=True):
                navigate("Dashboard")
        else:
            if st.button("Start Tracking Free", key="home_start_tracking", type="primary", use_container_width=True):
                navigate("Login")
    with second_button:
        if st.button("Markets & Economy", key="home_markets", use_container_width=True):
            navigate("Markets & Economy")
    with third_button:
        if st.button("Investor Tools", key="home_tools", use_container_width=True):
            navigate("Investor Tools")

    store_left, store_button, store_right = st.columns([1, 1.25, 1])
    with store_button:
        if PLAY_STORE_BADGE.exists():
            st.image(str(PLAY_STORE_BADGE), width=240, link=PLAY_STORE_URL)
        else:
            st.link_button("Get InvesTrack Pro on Google Play", PLAY_STORE_URL, use_container_width=True)

    st.markdown(
        """
        <div class="iv-trust-strip">
            <strong>Independent portfolio tools + original investor education.</strong>
            InvesTrack Pro combines personal portfolio tracking, practical calculators,
            educational market guides and clearly attributed third-party headlines.
            Educational content is separate from advertising and is not personalised investment advice.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Your public market companion")
    st.markdown(
        """
        <div class="iv-info-grid">
            <div class="iv-info-card"><div class="iv-kicker">Markets & Economy</div><h4>Understand what moves markets</h4><p>Learn how inflation, employment, GDP, central-bank policy, bond yields and currencies can influence stocks, crypto, gold and the wider economy.</p></div>
            <div class="iv-info-card"><div class="iv-kicker">Investor Tools</div><h4>Turn numbers into decisions</h4><p>Calculate investment returns, compound growth, dollar-cost averaging outcomes and profit or loss without leaving the site.</p></div>
            <div class="iv-info-card"><div class="iv-kicker">Learn</div><h4>Build financial understanding</h4><p>Explore clear guides to portfolio allocation, stocks, crypto, risk, diversification and macroeconomic indicators.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_ad_slot(ADSENSE_TOP_SLOT, height=130)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Explore Markets & Economy →", key="home_go_markets", use_container_width=True): navigate("Markets & Economy")
    with c2:
        if st.button("Open Investor Tools →", key="home_go_tools", use_container_width=True): navigate("Investor Tools")
    with c3:
        if st.button("Visit Learning Centre →", key="home_go_learn", use_container_width=True): navigate("Learn")

    st.markdown("## Browse by topic")
    st.markdown(
        """
        <div class="iv-info-grid">
            <div class="iv-info-card"><div class="iv-kicker">Portfolio</div><h4>Performance & diversification</h4><p>Understand returns, allocation, concentration, realized and unrealized results, and currency effects.</p></div>
            <div class="iv-info-card"><div class="iv-kicker">Economy</div><h4>Rates, inflation & growth</h4><p>Learn how central-bank decisions, inflation, employment and economic activity feed into financial markets.</p></div>
            <div class="iv-info-card"><div class="iv-kicker">Markets</div><h4>Stocks, ETFs, bonds & crypto</h4><p>Build a clearer picture of what different assets represent, what drives them and how their risks differ.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Everything you need to monitor your portfolio")
    feature_one, feature_two, feature_three = st.columns(3)
    with feature_one:
        st.markdown("""<div class="iv-card"><h3>📊 Unified portfolio</h3>Track stocks, cryptocurrency and cash holdings from one secure account.</div>""", unsafe_allow_html=True)
    with feature_two:
        st.markdown("""<div class="iv-card"><h3>📈 Performance insights</h3>Review portfolio value, gains, losses and historical performance over time.</div>""", unsafe_allow_html=True)
    with feature_three:
        st.markdown("""<div class="iv-card"><h3>🌍 Multi-currency view</h3>View your investment portfolio in a currency that is meaningful to you.</div>""", unsafe_allow_html=True)

    render_live_market_news(compact=True)

    render_ad_slot(ADSENSE_MID_SLOT, height=130)

    st.markdown("## What investors should watch each week")
    st.markdown(
        """
        <div class="iv-section-shell">
            <div class="iv-kicker">Economic Calendar Guide</div>
            <h3 style="margin-top:.2rem;">The releases that often shape the trading week</h3>
            <p>Market attention tends to cluster around a small number of recurring economic releases. Understanding them helps investors interpret market moves instead of reacting to headlines alone.</p>
            <div class="iv-info-grid">
                <div class="iv-info-card"><span class="iv-impact-high">HIGH IMPACT</span><h4>Inflation & central banks</h4><p>CPI, PCE inflation, interest-rate decisions and policy statements can alter rate expectations across global markets.</p></div>
                <div class="iv-info-card"><span class="iv-impact-high">HIGH IMPACT</span><h4>Employment</h4><p>Payrolls, unemployment and wage growth offer clues about demand, inflation pressure and the likely policy path.</p></div>
                <div class="iv-info-card"><span class="iv-impact-medium">MEDIUM / HIGH</span><h4>Growth & activity</h4><p>GDP, PMI, retail sales and industrial data help investors judge whether economic momentum is strengthening or weakening.</p></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("See the full Markets & Economy guide", key="home_calendar_guide", use_container_width=True): navigate("Markets & Economy")

    st.markdown("## Popular Investment Guides")

    featured_guides = [
        "portfolio-performance",
        "interest-rates",
        "economic-calendar",
    ]

    guide_columns = st.columns(3)

    for column, slug in zip(guide_columns, featured_guides):
        article = LEARN_ARTICLES[slug]

        with column:
            st.markdown(
                f"""
                <div class="iv-info-card">
                    <div class="iv-kicker">{article["category"]}</div>
                    <h4>{article["title"]}</h4>
                    <p>{article["summary"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Read guide →",
                key=f"home_guide_{slug}",
                use_container_width=True,
            ):
                open_learn_article(slug)

    st.markdown("## Built for investors who value clarity")
    st.write("""Whether you are tracking your first cryptocurrency holding or monitoring a growing stock portfolio, InvesTrack Pro combines portfolio tracking with practical financial education so you can understand both your holdings and the wider market environment.""")
    render_ad_slot(ADSENSE_BOTTOM_SLOT, height=130)
    render_public_footer()


# -----------------------------------------
# MARKETS & ECONOMY
# -----------------------------------------
def render_markets_economy_page():
    st.title("Markets & Economy")
    st.caption("A practical guide to the economic releases and policy decisions that investors watch.")
    st.markdown("""<div class="iv-section-shell"><div class="iv-kicker">Economic Calendar Framework</div><h2 style="margin-top:.2rem;">What belongs on an investor's weekly calendar?</h2><p>A useful economic calendar is more than a list of dates. It should help investors understand what each release measures, why markets care, and which assets may be sensitive to a surprise.</p></div>""", unsafe_allow_html=True)

    render_live_market_news(compact=False)
    render_ad_slot(ADSENSE_TOP_SLOT, height=130)

    st.markdown("### High-impact releases")
    rows=[
        ("Inflation","CPI / PCE inflation","High","Rates, bonds, USD, stocks, gold and crypto"),
        ("Central banks","Rate decisions / policy statements","High","Broad cross-asset impact"),
        ("Employment","Payrolls / unemployment / wages","High","Rates, USD, equities and risk assets"),
        ("Growth","GDP","Medium / High","Equities, currencies and yields"),
        ("Business activity","PMI / ISM","Medium / High","Cyclical stocks, currencies and yields"),
        ("Consumer demand","Retail sales","Medium","Consumer stocks, GDP expectations and rates"),
        ("Labour market","Jobless claims","Medium","Rates, USD and equities"),
    ]
    st.dataframe({"Theme":[r[0] for r in rows],"Release":[r[1] for r in rows],"Typical impact":[r[2] for r in rows],"Why investors watch":[r[3] for r in rows]},use_container_width=True,hide_index=True)

    st.markdown("### How to read an economic release")
    st.markdown("""
    <div class="iv-article"><h3>1. Compare actual vs forecast</h3><p>Markets often react more to the <strong>surprise</strong> than to the number itself. An inflation reading can be bullish or bearish depending on what investors expected beforehand.</p></div>
    <div class="iv-article"><h3>2. Consider the policy implication</h3><p>Ask whether the release makes rate cuts, rate hikes or unchanged policy more likely. This link between data and policy expectations is often what moves bond yields, currencies and growth assets.</p></div>
    <div class="iv-article"><h3>3. Watch the market's first reaction carefully</h3><p>The first move is not always the lasting move. Investors may initially react to the headline figure and then reassess revisions, components, guidance and positioning.</p></div>
    """, unsafe_allow_html=True)

    st.markdown("### Economic news themes worth following")
    st.markdown("""
    <div class="iv-info-grid">
        <div class="iv-info-card"><h4>🏦 Monetary policy</h4><p>Interest rates, balance sheets, central-bank guidance and bond-market expectations.</p></div>
        <div class="iv-info-card"><h4>📉 Inflation</h4><p>Consumer prices, producer prices, services inflation, wages and inflation expectations.</p></div>
        <div class="iv-info-card"><h4>👷 Employment</h4><p>Job creation, unemployment, wages, participation and claims data.</p></div>
        <div class="iv-info-card"><h4>🏭 Growth</h4><p>GDP, business surveys, industrial activity, consumer spending and recession risk.</p></div>
        <div class="iv-info-card"><h4>💵 Currencies & yields</h4><p>Exchange-rate moves and government-bond yields often transmit macroeconomic news across markets.</p></div>
        <div class="iv-info-card"><h4>🛢️ Commodities</h4><p>Oil, gold and other commodities can reflect inflation, geopolitics, demand and safe-haven flows.</p></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("""<div class="iv-note"><strong>Calendar data note:</strong> Live financial news is now connected through Marketaux. The economic-calendar section remains educational until a suitable licensed calendar source is connected, so InvesTrack Pro does not display fabricated or stale release values.</div>""", unsafe_allow_html=True)
    render_public_footer()


# -----------------------------------------
# INVESTOR TOOLS
# -----------------------------------------
def render_investor_tools_page():
    st.title("Investor Tools")
    st.caption("Free calculators for common investing questions.")
    tab_return,tab_compound,tab_dca,tab_pnl=st.tabs(["Investment Return","Compound Growth","DCA","Profit / Loss"])

    with tab_return:
        st.subheader("Investment Return Calculator")
        c1,c2=st.columns(2)
        with c1: initial=st.number_input("Initial investment",min_value=0.0,value=1000.0,step=100.0,key="tool_return_initial")
        with c2: final=st.number_input("Final value",min_value=0.0,value=1250.0,step=100.0,key="tool_return_final")
        gain=final-initial; pct=((gain/initial)*100) if initial>0 else 0.0
        m1,m2=st.columns(2); m1.metric("Gain / Loss",f"{gain:,.2f}"); m2.metric("Return",f"{pct:,.2f}%")
        st.caption("Return = (final value − initial investment) ÷ initial investment.")

    with tab_compound:
        st.subheader("Compound Growth Calculator")
        c1,c2,c3=st.columns(3)
        with c1: principal=st.number_input("Starting amount",min_value=0.0,value=1000.0,step=100.0,key="tool_compound_principal")
        with c2: annual_rate=st.number_input("Annual return (%)",value=8.0,step=0.5,key="tool_compound_rate")
        with c3: years=st.number_input("Years",min_value=0,value=10,step=1,key="tool_compound_years")
        future_value=principal*((1+annual_rate/100)**years); growth=future_value-principal
        m1,m2=st.columns(2); m1.metric("Estimated future value",f"{future_value:,.2f}"); m2.metric("Estimated growth",f"{growth:,.2f}")
        st.caption("This is a mathematical illustration, not a forecast of future investment performance.")

    with tab_dca:
        st.subheader("Dollar-Cost Averaging Calculator")
        c1,c2,c3=st.columns(3)
        with c1: monthly=st.number_input("Monthly contribution",min_value=0.0,value=100.0,step=25.0,key="tool_dca_monthly")
        with c2: annual_rate_dca=st.number_input("Assumed annual return (%)",value=8.0,step=0.5,key="tool_dca_rate")
        with c3: years_dca=st.number_input("Years",min_value=1,value=10,step=1,key="tool_dca_years")
        months=years_dca*12; monthly_rate=annual_rate_dca/100/12
        estimated_value=monthly*months if abs(monthly_rate)<1e-12 else monthly*(((1+monthly_rate)**months-1)/monthly_rate)
        contributed=monthly*months; estimated_growth=estimated_value-contributed
        m1,m2,m3=st.columns(3); m1.metric("Total contributed",f"{contributed:,.2f}"); m2.metric("Estimated value",f"{estimated_value:,.2f}"); m3.metric("Estimated growth",f"{estimated_growth:,.2f}")
        st.caption("Assumes contributions are made at the end of each month and the selected return is constant.")

    with tab_pnl:
        st.subheader("Profit / Loss Calculator")
        c1,c2,c3=st.columns(3)
        with c1: buy_price=st.number_input("Buy price",min_value=0.0,value=100.0,step=1.0,key="tool_pnl_buy")
        with c2: sell_price=st.number_input("Current / sell price",min_value=0.0,value=120.0,step=1.0,key="tool_pnl_sell")
        with c3: quantity=st.number_input("Quantity",min_value=0.0,value=10.0,step=1.0,key="tool_pnl_qty")
        cost=buy_price*quantity; value=sell_price*quantity; pnl=value-cost; pnl_pct=((pnl/cost)*100) if cost>0 else 0.0
        m1,m2,m3=st.columns(3); m1.metric("Cost basis",f"{cost:,.2f}"); m2.metric("Current / sale value",f"{value:,.2f}"); m3.metric("Profit / Loss",f"{pnl:,.2f}",f"{pnl_pct:,.2f}%")

    st.markdown("""<div class="iv-note">These tools are for general educational use. They do not include taxes, fees, spreads, slippage or every real-world investing cost.</div>""", unsafe_allow_html=True)
    render_public_footer()



LEARN_ARTICLES = {
    "portfolio-performance": {
        "title": "How to Track Investment Portfolio Performance",
        "category": "Portfolio Management",
        "summary": "A practical framework for separating contributions, withdrawals, market performance and currency effects.",
        "body": """
### Start with the right baseline

Portfolio performance is not simply today's account balance minus the amount you remember investing. Deposits and withdrawals change the account value without representing investment gains or losses. A useful review starts with a clear record of capital contributed, capital withdrawn and the current portfolio value.

### Separate cash flows from investment performance

Suppose a portfolio rises from 10,000 to 14,000 during the year, but the investor added another 3,000 during that period. The apparent 40% increase in account value is not a 40% investment return. Most of the increase came from new capital.

Tracking contributions separately makes the performance figure more meaningful.

### Understand unrealized and realized results

An unrealized gain or loss belongs to an investment that is still held. A realized result occurs after a position is closed. Both matter, but they answer different questions. Unrealized performance describes the changing value of current holdings; realized performance records completed investment outcomes.

### Account for currencies

Investors holding foreign assets can experience two simultaneous changes: the underlying asset price and the exchange rate between the asset's currency and their reporting currency. A US stock can rise in dollars while producing a smaller gain—or even a loss—when translated into another currency.

### Review allocation as well as return

Performance should be considered alongside concentration. A portfolio can post a strong return because one asset became unusually large. That may also mean the portfolio has become more dependent on that asset.

A regular review should therefore ask: What produced the return? How concentrated is the portfolio now? Has the risk profile changed?

### Use consistent periods

Compare performance over consistent periods such as month-to-date, year-to-date and since inception. Short periods can be heavily influenced by market noise, while longer periods provide more context.

### A simple review checklist

Record contributions and withdrawals, update current values, calculate gains and losses, review asset allocation, consider currency effects and compare the result with your original investment objective. The purpose is not to chase the best recent performer; it is to understand what has actually happened to your capital.
""",
    },
    "diversification": {
        "title": "Portfolio Diversification Explained",
        "category": "Portfolio Management",
        "summary": "Why owning many investments is not necessarily the same as being diversified.",
        "body": """
### What diversification means

Diversification is the practice of spreading investment exposure so that one company, sector, asset class or economic outcome does not dominate the portfolio.

Owning ten securities does not automatically create diversification. Ten technology companies may still respond to many of the same forces: interest rates, semiconductor demand, advertising spending or expectations for economic growth.

### Look at the drivers behind each holding

A better question than “How many assets do I own?” is “What makes each asset rise or fall?” Holdings driven by different economic factors may provide more meaningful diversification than a long list of closely related investments.

### Concentration can develop gradually

Even a portfolio that began diversified can become concentrated when one investment substantially outperforms the others. Reviewing allocation percentages helps reveal when this happens.

### Diversification has limits

Diversification cannot guarantee profits or prevent losses. During broad market stress, correlations between assets can increase and many investments may fall together. Its purpose is risk management, not loss elimination.

### Rebalancing

Rebalancing means bringing a portfolio back toward a chosen allocation after market movements change its weights. This can involve adding to underweight areas, trimming overweight areas or directing new contributions toward parts of the portfolio that have become relatively small.

A sensible allocation depends on an investor's objectives, time horizon, liquidity needs and ability to tolerate losses. There is no single allocation that is appropriate for everyone.
""",
    },
    "realized-unrealized": {
        "title": "Realized vs Unrealized Gains and Losses",
        "category": "Investing Basics",
        "summary": "Understand the difference between changing market value and completed investment outcomes.",
        "body": """
### Unrealized gains and losses

An unrealized gain exists when an investment is worth more than its cost but has not been sold. An unrealized loss exists when its market value is below cost while the position remains open.

Because market prices change, unrealized results can expand, shrink or reverse.

### Realized gains and losses

A gain or loss generally becomes realized when the investment is sold or otherwise closed. The difference matters because realized transactions affect available cash and may have tax consequences depending on the investor's jurisdiction.

### Why portfolio dashboards show both concepts

A portfolio tracker usually needs current market values to show what the holdings are worth today. That naturally includes unrealized performance. Investors should avoid treating every displayed gain as cash already earned.

### Cost basis matters

To interpret a gain or loss, the investor needs a reliable cost basis: what was paid for the investment, adjusted where appropriate for transaction costs and other relevant events.

Keeping accurate transaction records makes portfolio performance much easier to understand.
""",
    },
    "dca": {
        "title": "Dollar-Cost Averaging Explained",
        "category": "Investing Basics",
        "summary": "How regular fixed contributions work, and what DCA can and cannot do.",
        "body": """
### The basic idea

Dollar-cost averaging, commonly called DCA, means investing a fixed amount at regular intervals rather than committing the entire amount at one time.

When the asset price is lower, the fixed contribution purchases more units. When the price is higher, it purchases fewer.

### Why investors use it

DCA can create a repeatable contribution habit and reduce the pressure to identify a perfect entry point. It can be particularly practical when investment capital becomes available gradually through monthly income.

### What DCA does not guarantee

Regular investing does not guarantee a profit and does not protect a portfolio from falling markets. If an asset experiences a sustained decline, repeated purchases can also lose value.

### DCA and lump-sum investing are different decisions

An investor who already has a large amount available faces a different decision from someone investing part of each monthly salary. The appropriate approach depends on circumstances, risk tolerance and the purpose of the capital.

The InvesTrack Pro DCA calculator provides a mathematical illustration of regular contributions and assumed growth; it is not a forecast of actual returns.
""",
    },
    "interest-rates": {
        "title": "How Interest Rates Affect Stocks, Crypto and Markets",
        "category": "Macroeconomics",
        "summary": "A clear guide to the transmission of central-bank rates through financial markets.",
        "body": """
### Interest rates are a price for money

Central-bank policy rates influence borrowing costs throughout an economy. Changes in expected rates can affect mortgages, business financing, government bonds, currencies and the valuation of financial assets.

### Stocks

Higher rates can increase corporate borrowing costs and raise the return available on lower-risk assets such as government debt. They also increase the discount rate investors may apply to future company cash flows. Growth companies whose expected profits lie far in the future can therefore be particularly sensitive to changing rate expectations.

### Crypto and other risk assets

Crypto does not have one mechanical relationship with interest rates. However, easier financial conditions and abundant liquidity can support demand for risk assets, while tighter conditions can reduce risk appetite. Other factors—including adoption, regulation and market-specific flows—also matter.

### Currencies and bonds

Higher expected rates can increase a currency's relative attractiveness, although growth, inflation and risk sentiment complicate the relationship. Bond prices and yields also respond directly to changing expectations about inflation and monetary policy.

### The reason for a rate change matters

A rate cut caused by falling inflation and stable growth can be interpreted differently from an emergency cut during severe economic weakness. Investors should therefore consider the economic backdrop rather than treating “cuts” as automatically bullish or “hikes” as automatically bearish.
""",
    },
    "inflation": {
        "title": "How Inflation Can Affect Your Investment Portfolio",
        "category": "Macroeconomics",
        "summary": "Why inflation influences purchasing power, interest rates, company costs and asset valuations.",
        "body": """
### Purchasing power

Inflation describes a broad increase in prices over time. When prices rise, a fixed amount of money buys fewer goods and services. Investors therefore care about returns after considering inflation, not only nominal gains.

### Central-bank policy

Persistent inflation can lead central banks to maintain higher interest rates or tighten policy. Because interest-rate expectations influence bonds, currencies and equity valuations, inflation releases can move several markets at once.

### Companies experience inflation differently

Some businesses can pass higher costs to customers; others cannot. Energy prices, wages, raw materials and financing costs can therefore affect industries differently.

### Inflation and bonds

Unexpected inflation can be particularly important for fixed-income investments because future fixed payments may have less purchasing power. Bond yields may rise when investors demand greater compensation for inflation risk.

### There is no universal inflation hedge

Assets often described as inflation hedges can behave differently across time periods. The source of inflation, policy response, valuation and investor positioning all matter.

For portfolio analysis, inflation is best treated as part of the wider economic environment rather than as a signal that one specific asset must rise or fall.
""",
    },
    "pnl": {
        "title": "Understanding Investment P&L",
        "category": "Investing Basics",
        "summary": "How profit and loss figures are calculated and why percentage returns need context.",
        "body": """
### What P&L means

P&L means profit and loss. At its simplest, investment P&L compares the value received or currently held with the cost of acquiring the investment.

If 10 units were purchased at 100 each, the basic cost is 1,000. If those units are later worth 120 each, the position value is 1,200 and the simple unrealized gain is 200 before fees, taxes and other costs.

### Percentage return

Percentage return puts the gain or loss in relation to the amount invested. A gain of 200 means something very different on a 1,000 investment than on a 100,000 investment.

### P&L can be distorted by cash flows

Adding new money increases portfolio value but is not investment profit. Withdrawing money reduces account value but is not necessarily an investment loss. Portfolio-level P&L therefore needs transaction records.

### Fees and taxes

Real-world returns can differ from simplified calculations because of commissions, spreads, slippage, taxes and currency conversion. InvesTrack Pro's public calculator is designed as an educational estimate rather than a tax or accounting calculation.
""",
    },
    "stocks-etfs-crypto": {
        "title": "Stocks vs ETFs vs Crypto: Understanding the Differences",
        "category": "Markets",
        "summary": "Compare three widely followed investment types without treating them as interchangeable.",
        "body": """
### Stocks

A share of stock represents an ownership interest in a company. Its value can be influenced by earnings, cash flows, competition, management, interest rates and expectations about the company's future.

### ETFs

An exchange-traded fund is a pooled investment vehicle traded on an exchange. Depending on its mandate, an ETF may hold many stocks, bonds, commodities or other assets. Some ETFs provide broad diversification; others are highly concentrated.

### Cryptoassets

Cryptoassets are digital assets whose characteristics vary considerably. Their prices may be influenced by network usage, token economics, liquidity, regulation, technology, market sentiment and broader financial conditions.

### Risk is not determined by the label alone

A diversified broad-market ETF can have a very different risk profile from a single speculative stock. Likewise, cryptoassets differ greatly from one another.

When comparing investments, consider what the asset represents, what drives its value, its volatility, liquidity, concentration and how it fits with the rest of the portfolio.
""",
    },
    "fx-foreign-investments": {
        "title": "How Exchange Rates Affect Foreign Investments",
        "category": "Portfolio Management",
        "summary": "Why the return on a foreign asset can look different in your home currency.",
        "body": """
### Two sources of movement

When you invest in an asset priced in a foreign currency, your home-currency result can depend on both the investment price and the exchange rate.

A stock may rise in US dollars while the dollar weakens against your reporting currency. The currency movement can reduce the home-currency gain. The reverse can also occur.

### Why this matters for international portfolios

Investors often compare assets using the currency in which they trade, but personal wealth and spending may be measured in another currency. Viewing the portfolio in a meaningful reporting currency can therefore reveal a different picture.

### Currency movements have their own drivers

Exchange rates respond to relative interest rates, inflation, economic growth, trade flows, risk sentiment and policy expectations. They can add volatility to foreign investments even when the underlying asset is unchanged.

### Track both views

Where possible, review the asset's native-currency performance and the translated portfolio performance. This helps distinguish whether a result came from the investment itself, the currency, or both.
""",
    },
    "market-cap": {
        "title": "Understanding Market Capitalization",
        "category": "Investing Basics",
        "summary": "What market cap measures, how it is calculated and what it does not tell you.",
        "body": """
### The calculation

For a publicly traded company, market capitalization is broadly calculated as share price multiplied by shares outstanding. It represents the market value investors collectively place on the company's equity at that time.

### Why investors use it

Market cap provides a convenient way to compare the relative size of listed companies. Index providers may also use market capitalization when determining index weights.

### A high share price does not mean a larger company

Share price alone says little about company size because companies have different numbers of shares outstanding. A company trading at 50 per share can have a larger market capitalization than one trading at 500.

### Market cap is not the same as business value

Market capitalization focuses on equity. Measures such as enterprise value incorporate other balance-sheet items such as debt and cash. Market cap also does not tell investors whether a company is cheap, expensive, profitable or financially strong.

It is a useful starting statistic, not a complete valuation framework.
""",
    },
    "economic-indicators": {
        "title": "Economic Indicators Investors Should Understand",
        "category": "Macroeconomics",
        "summary": "A practical introduction to inflation, employment, GDP, PMI, retail sales and central-bank decisions.",
        "body": """
### Inflation

CPI and other inflation measures help investors assess changes in prices and possible central-bank responses. Markets often focus on whether the release differs from expectations.

### Employment

Payroll growth, unemployment, wage growth and jobless claims provide information about labour demand and household income. Strong labour data can support growth while also affecting inflation and rate expectations.

### GDP

Gross domestic product measures broad economic output. Investors watch both the growth rate and the components behind it.

### PMI and business surveys

Purchasing Managers' Index surveys can provide relatively timely information about business activity, new orders, employment and prices.

### Retail sales

Retail data offer clues about consumer demand, an important part of many economies.

### Central-bank decisions

Rate decisions and policy statements can influence borrowing costs, bond yields, currencies and risk appetite. The guidance surrounding a decision can sometimes matter more than the decision itself.

No indicator should be interpreted in isolation. Markets combine new data with expectations, previous releases and the broader policy environment.
""",
    },
    "economic-calendar": {
        "title": "How to Read an Economic Calendar",
        "category": "Macroeconomics",
        "summary": "Learn how previous, forecast and actual values help investors interpret scheduled economic releases.",
        "body": """
### What an economic calendar does

An economic calendar organizes scheduled releases and policy events by date and time. Common entries include inflation reports, employment data, GDP, business surveys and central-bank decisions.

### Previous

The previous value shows the earlier reported reading. It provides context but may later be revised.

### Forecast

The forecast represents the market or surveyed expectation before the release. Because financial markets continuously price expectations, the gap between the actual result and the forecast can matter more than the absolute number.

### Actual

The actual figure is the newly released value. A result above forecast is not automatically bullish or bearish. Interpretation depends on the indicator.

For example, stronger-than-expected growth may support company earnings expectations but could also increase expectations for higher interest rates.

### Impact labels

Calendars commonly classify events by expected market impact. These labels are useful for prioritization, but an event marked “medium” can still produce a large move if the surprise is substantial.

### Build context before the release

Before a major event, know the previous value, consensus forecast and why the indicator matters. After release, compare actual with forecast, check revisions and consider the likely policy implication.

An economic calendar is most useful as a preparation tool, not as a prediction engine.
""",
    },
}


def open_learn_article(slug):
    if slug in LEARN_ARTICLES:
        write_route_to_url("Learn", article_slug=slug)
        st.session_state.learn_article_slug = slug
        st.session_state.pending_public_page = "Learn"
        st.rerun()


def close_learn_article():
    st.session_state.pop("learn_article_slug", None)
    write_route_to_url("Learn")
    st.session_state.public_navigation = "Learn"
    st.rerun()


def render_learn_article(slug):
    article = LEARN_ARTICLES.get(slug)

    if not article:
        st.session_state.pop("learn_article_slug", None)
        return False

    if st.button("← Back to Learning Centre", key=f"article_back_{slug}"):
        close_learn_article()

    st.caption(article["category"])
    st.title(article["title"])
    st.markdown(f"**{article['summary']}**")
    st.markdown(article["body"])
    render_ad_slot(ADSENSE_MID_SLOT, height=130)

    st.markdown(
        """
        <div class="iv-note">
            <strong>Educational information only.</strong> This guide is intended
            to explain general investing concepts and does not provide personalised
            financial, investment, tax or legal advice.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Track your own portfolio with InvesTrack Pro",
        key=f"article_cta_{slug}",
        type="primary",
        use_container_width=True,
    ):
        navigate("Login")

    render_public_footer()
    return True



# -----------------------------------------
# LEARNING CENTRE
# -----------------------------------------
def render_learn_page():
    article_slug = st.session_state.get("learn_article_slug")

    if article_slug:
        if render_learn_article(article_slug):
            return

    st.title("InvesTrack Learning Centre")
    st.caption(
        "Original, practical financial education for investors building long-term understanding."
    )

    st.markdown(
        """
        <div class="iv-section-shell">
            <div class="iv-kicker">Investor Education</div>
            <h2 style="margin-top:.2rem;">Learn the concepts behind the numbers</h2>
            <p>
                Portfolio dashboards show what changed. The Learning Centre is
                designed to explain why the numbers matter — from investment
                performance and diversification to inflation, interest rates,
                currencies and scheduled economic releases.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    categories = [
        ("Portfolio Management", "📊"),
        ("Investing Basics", "📘"),
        ("Macroeconomics", "🌐"),
        ("Markets", "📈"),
    ]

    for category, icon in categories:
        st.markdown(f"### {icon} {category}")

        category_articles = [
            (slug, article)
            for slug, article in LEARN_ARTICLES.items()
            if article["category"] == category
        ]

        for slug, article in category_articles:
            left, right = st.columns([4, 1])

            with left:
                st.markdown(f"**{article['title']}**")
                st.caption(article["summary"])

            with right:
                if st.button(
                    "Read guide",
                    key=f"learn_open_{slug}",
                    use_container_width=True,
                ):
                    open_learn_article(slug)

        st.markdown("")

    render_ad_slot(ADSENSE_MID_SLOT, height=130)

    st.markdown(
        """
        <div class="iv-note">
            InvesTrack Pro's educational material is written to explain general
            financial concepts clearly. It does not tell readers what to buy or
            sell and should not be treated as personalised investment advice.
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_public_footer()


# -----------------------------------------
# EDITORIAL POLICY & CONTENT METHODOLOGY
# -----------------------------------------
def render_editorial_page():
    st.title("Editorial Policy & Content Methodology")
    st.caption("How InvesTrack Pro creates, reviews and presents financial education and market information.")

    st.markdown(
        """
        <div class="iv-section-shell">
            <div class="iv-kicker">Editorial Standards</div>
            <h2 style="margin-top:.2rem;">Clear information before market noise</h2>
            <p>
                InvesTrack Pro publishes educational material to help readers understand
                investing, portfolio management and the economic forces that can affect
                financial markets. Our public content is designed to explain concepts,
                not to tell readers what they should buy or sell.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Our editorial principles")
    st.markdown(
        """
        **Accuracy and context.** We aim to explain financial concepts in plain language
        without removing important qualifications. Where a topic depends on changing
        market conditions, readers should distinguish educational explanation from
        current market data.

        **Original educational value.** InvesTrack Pro guides are prepared for this
        platform and are intended to add practical explanation rather than simply
        reproduce third-party material.

        **Neutrality.** Educational articles are not written as recommendations to buy,
        sell or hold a particular security, cryptocurrency or other financial asset.

        **Clear separation of sources.** Third-party market headlines are identified as
        external content and link to their original publishers. They are not presented
        as InvesTrack Pro articles.

        **Corrections.** Material may be revised when an explanation is incomplete,
        inaccurate or no longer reflects the information the page is intended to teach.
        """
    )

    st.markdown("### Content methodology")
    st.markdown(
        """
        Our educational guides focus on established investing and macroeconomic concepts
        such as portfolio returns, diversification, inflation, interest rates, currencies
        and economic indicators. Articles are structured around the questions an investor
        needs to understand: what a concept means, how it is commonly measured, why it
        matters and what its limitations are.

        Live financial headlines displayed on InvesTrack Pro are supplied through the
        Marketaux news service. Headline cards identify the source and direct readers to
        the original publisher. InvesTrack Pro does not treat an external headline as a
        trading recommendation.

        Calculator outputs are mathematical illustrations based on the values entered by
        the user. They do not predict future returns and may exclude taxes, fees, spreads,
        slippage and other real-world costs.
        """
    )

    st.markdown("### Financial-content standard")
    st.markdown(
        """
        InvesTrack Pro does not provide personalised financial, investment, trading, tax
        or legal advice. Readers remain responsible for evaluating information in light of
        their own circumstances and, where appropriate, obtaining advice from a qualified
        professional.
        """
    )

    st.markdown("### Publisher & contact")
    st.markdown(
        """
        **Publisher:** InvesTrack Pro  
        **Website:** app.investrackpro.com  
        **Editorial and correction enquiries:** hassbuildllc@gmail.com
        """
    )

    st.markdown(
        """<div class="iv-note"><strong>Transparency note:</strong> Advertising, when enabled, does not change the educational purpose of our articles or the distinction between InvesTrack Pro content and third-party market headlines.</div>""",
        unsafe_allow_html=True,
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

        The platform allows users to monitor cryptocurrency, stock, ETF, bond and cash
        holdings through a unified dashboard. Users can review portfolio
        values, performance history and asset allocation without maintaining
        separate spreadsheets or switching between multiple applications.

        ### Our mission

        Our mission is to give everyday investors a convenient and
        understandable way to monitor their financial assets.

        ### What InvesTrack Pro provides

        - Cryptocurrency portfolio tracking
        - Stock portfolio tracking
        - ETF portfolio tracking
        - Bond portfolio tracking
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

    st.markdown("### Publishing standards")
    st.write(
        "InvesTrack Pro maintains a dedicated Editorial Policy & Content Methodology "
        "page explaining how its educational material, calculators and third-party "
        "market headlines are presented."
    )
    if st.button("Read our Editorial Policy", key="about_editorial_policy", use_container_width=True):
        navigate("Editorial")

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
        (
            '<div style="border-radius:14px;padding:18px;'
            'background:linear-gradient(135deg,#0f172a,#1e293b);'
            'color:white;margin:14px 0;">'
            '<h4 style="margin:0 0 8px 0;color:white;">'
            '🚀 Pro Investor Tools Coming Soon</h4>'
            '<p style="margin:0;color:#d1d5db;line-height:1.6;">'
            'Advanced analytics, exportable reports, portfolio scoring '
            'and market insights.</p>'
            '</div>'
        ),
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

    mode_options = ["Overview", "Crypto", "Stocks", "ETFs", "Bonds"]

    if "selected_mode" not in st.session_state:
        st.session_state.selected_mode = "Overview"

    if st.session_state.selected_mode not in mode_options:
        st.session_state.selected_mode = "Overview"

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

    try:
        if mode == "Overview":
            from overview_mode import overview_app

            overview_app()

        elif mode == "Crypto":
            from crypto_mode import crypto_app

            crypto_app()

        elif mode == "Stocks":
            from stock_mode import stock_app

            stock_app()

        elif mode == "ETFs":
            from etf_mode import etf_app

            etf_app()

        elif mode == "Bonds":
            from bond_mode import bond_app

            bond_app()

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


# -----------------------------------------
# MAIN ROUTER
# -----------------------------------------
sync_route_from_url()

selected_page, user_is_authenticated = (
    render_public_navigation()
)

if selected_page == "Home":
    render_home_page(user_is_authenticated)

elif selected_page == "Markets & Economy":
    render_markets_economy_page()

elif selected_page == "Investor Tools":
    render_investor_tools_page()

elif selected_page == "Learn":
    render_learn_page()

elif selected_page == "Editorial":
    render_editorial_page()

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
