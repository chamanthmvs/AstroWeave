from __future__ import annotations

import logging
from uuid import uuid4

import httpx
import streamlit as st

from auth import authenticate_user, create_user, load_users


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="AstroWeave | Personal astrology workspace",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&family=Playfair+Display:wght@600;700&display=swap');

    :root {
        --ink: #26323a;
        --muted: #68757c;
        --line: #d7dee0;
        --mint: #2f776d;
        --gold: #9a6d28;
        --coral: #b86652;
        --deep: #f5f7f6;
        --canvas: #f3f5f4;
        --surface: #ffffff;
        --surface-soft: #edf2f0;
        --shadow: 0 10px 30px rgba(39, 56, 59, .08);
    }

    .stApp {
        color: var(--ink);
        background: radial-gradient(circle at 88% 5%, rgba(154, 109, 40, .07), transparent 24rem),
                    radial-gradient(circle at 12% 78%, rgba(47, 119, 109, .06), transparent 28rem),
                    var(--canvas);
    }
    [data-testid="stHeader"] { background: rgba(243, 245, 244, .88); }
    [data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
    .block-container { max-width: 1180px; padding-top: 3.5rem; padding-bottom: 4rem; }
    .brand { display: flex; align-items: center; gap: .7rem; margin-bottom: 2.6rem; color: var(--ink); font: 800 1.05rem Manrope, sans-serif; }
    .brand-mark { display: block; width: 2.25rem; height: 2.25rem; position: relative; border: 1px solid var(--mint); border-radius: 50%; transform: rotate(-24deg); background: var(--surface-soft); }
    .brand-mark::before, .brand-mark::after { content: ''; position: absolute; border: 1px solid var(--gold); border-radius: 50%; }
    .brand-mark::before { inset: .42rem -.22rem; }
    .brand-mark::after { width: .36rem; height: .36rem; top: .08rem; right: .15rem; border: 0; background: var(--coral); box-shadow: -.95rem 1.7rem 0 -.04rem var(--mint); }
    .eyebrow { color: var(--gold); font: 500 .7rem 'DM Mono', monospace; letter-spacing: .14em; text-transform: uppercase; }
    h1, h2, h3 { font-family: 'Playfair Display', serif !important; letter-spacing: -.025em; }
    h1 { font-size: clamp(2.6rem, 5vw, 4.8rem) !important; line-height: .98 !important; max-width: 720px; }
    h1 em { color: var(--mint); font-style: normal; }
    h2 { font-size: 1.8rem !important; }
    .intro { max-width: 690px; color: var(--muted); font-size: 1.05rem; }
    .workspace-label { margin: 2.8rem 0 .7rem; color: var(--muted); font: .7rem 'DM Mono', monospace; letter-spacing: .12em; text-transform: uppercase; }
    .profile { padding: 1.1rem; border: 1px solid var(--line); background: var(--surface-soft); box-shadow: var(--shadow); }
    .avatar { display: grid; width: 2.8rem; height: 2.8rem; place-items: center; margin-bottom: .75rem; border: 1px solid var(--gold); border-radius: 50%; color: var(--gold); background: #fbf4e7; font: 700 1rem Manrope, sans-serif; }
    .profile-name { color: var(--ink); font-weight: 800; }
    .profile-email { overflow: hidden; color: var(--muted); font-size: .75rem; text-overflow: ellipsis; white-space: nowrap; }
    .side-meta { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin: 1.1rem 0; }
    .meta-item { padding: .65rem; border-top: 1px solid var(--line); }
    .meta-value { display: block; margin-top: .22rem; color: var(--ink); font-weight: 700; }
    .meta-label { color: var(--muted); font: .63rem 'DM Mono', monospace; letter-spacing: .05em; text-transform: uppercase; }
    .panel { padding: 1.5rem; border: 1px solid var(--line); background: var(--surface); box-shadow: var(--shadow); }
    .panel-title { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
    .panel-title h3 { margin: 0; color: var(--ink); font-size: 1.25rem; }
    .status { color: var(--mint); font: .7rem 'DM Mono', monospace; text-transform: uppercase; }
    .stTextArea textarea, .stTextInput input { border-color: var(--line); color: var(--ink); background: var(--surface); }
    .stTextArea textarea:focus, .stTextInput input:focus { border-color: var(--mint); box-shadow: 0 0 0 1px var(--mint); }
    .stButton > button, .stFormSubmitButton > button { min-height: 2.7rem; border: 1px solid var(--mint); border-radius: .35rem; color: #ffffff; background: var(--mint); font-weight: 800; }
    .stButton > button:hover, .stFormSubmitButton > button:hover { border-color: #245e57; color: #ffffff; background: #245e57; }
    div[data-testid="stExpander"] { border-color: var(--line); background: var(--surface); }
    .hint { padding: .95rem 1rem; border-left: 2px solid var(--gold); color: var(--muted); background: #fbf4e7; font-size: .84rem; }
    .stAlert { border-radius: .35rem; }
    @media (prefers-color-scheme: dark) {
        :root { --ink: #e4ecea; --muted: #a2b3b2; --line: rgba(164, 210, 198, .16); --mint: #8ccbb4; --gold: #e0b66e; --coral: #e08d77; --deep: #07131e; --canvas: #0b1822; --surface: #10252f; --surface-soft: #142e37; --shadow: 0 10px 30px rgba(0, 0, 0, .2); }
        .stApp { background: radial-gradient(circle at 84% 9%, rgba(224, 141, 119, .1), transparent 26rem), linear-gradient(135deg, #07131e 0%, #0d222d 58%, #102f37 100%); }
        [data-testid="stHeader"] { background: rgba(7, 19, 30, .72); }
        [data-testid="stSidebar"] { background: rgba(5, 16, 26, .9); }
        .avatar { background: rgba(224, 182, 110, .1); }
        .hint { background: rgba(224, 182, 110, .08); }
    }
    .auth-shell { max-width: 500px; margin: 10vh auto 0; }
    .auth-note { margin: .9rem 0 1.5rem; color: var(--muted); }
    @media (max-width: 700px) { .block-container { padding-top: 2rem; } h1 { font-size: 3rem !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


if "users" not in st.session_state:
    st.session_state.users = load_users()
if "user" not in st.session_state:
    st.session_state.user = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "Sign in"


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper() or "AW"


def render_auth() -> None:
    st.markdown('<div class="auth-shell">', unsafe_allow_html=True)
    st.markdown('<div class="brand"><span class="brand-mark" aria-hidden="true"></span> AstroWeave</div>', unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">Specialist astrology, thoughtfully coordinated</div>', unsafe_allow_html=True)
    st.title("Your questions, read from every angle.")
    st.markdown('<p class="auth-note">Sign in to continue your astrology workspace, or create an account to begin a new reading.</p>', unsafe_allow_html=True)

    mode = st.radio("Account access", ["Sign in", "Create account"], horizontal=True, label_visibility="collapsed")
    with st.form("auth_form"):
        name = st.text_input("Your name", placeholder="e.g. Maya Patel") if mode == "Create account" else ""
        email = st.text_input("Email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Continue", use_container_width=True)

    if submitted:
        normalized_email = email.strip().lower()
        if not normalized_email or not password:
            st.error("Enter your email and password to continue.")
        elif mode == "Create account" and not name.strip():
            st.error("Tell us your name first.")
        elif mode == "Create account" and len(password) < 8:
            st.error("Use at least 8 characters for your password.")
        elif mode == "Create account":
            if normalized_email in st.session_state.users:
                st.error("An account with that email already exists.")
            else:
                create_user(st.session_state.users, normalized_email, name.strip(), password)
                st.session_state.user = {"email": normalized_email, "name": name.strip()}
                st.rerun()
        else:
            authenticated_user = authenticate_user(
                st.session_state.users, normalized_email, password
            )
            if authenticated_user is None:
                st.error("That email and password combination was not found.")
            else:
                st.session_state.user = authenticated_user
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


if st.session_state.user is None:
    render_auth()
    st.stop()


user = st.session_state.user
with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark" aria-hidden="true"></span> AstroWeave</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="profile"><div class="avatar">{initials(user["name"])}</div><div class="profile-name">{user["name"]}</div><div class="profile-email">{user["email"]}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="workspace-label">Your workspace</div>', unsafe_allow_html=True)
    st.markdown('<div class="side-meta"><div class="meta-item"><span class="meta-label">Method</span><span class="meta-value">Vedic + KP</span></div><div class="meta-item"><span class="meta-label">Readings</span><span class="meta-value">01</span></div></div>', unsafe_allow_html=True)
    api_url = st.text_input("API URL", value="http://127.0.0.1:8000")
    with st.expander("Session details"):
        conversation_id = st.text_input("Conversation ID", value="conversation-1")
        session_id = st.text_input("Session ID", value="session-1")
    with st.expander("Birth details", expanded=True):
        birth_date = st.date_input("Birth date")
        birth_time = st.time_input("Birth time")
        place_name = st.text_input("Birth place", placeholder="e.g. Chennai, India")
        birth_latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=0.0, format="%.4f")
        birth_longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=0.0, format="%.4f")
        utc_offset_hours = st.number_input("UTC offset (hours)", min_value=-12.0, max_value=14.0, value=5.5, step=0.5)
    if st.button("Sign out", use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.markdown('<div class="eyebrow">Personal astrology workspace</div>', unsafe_allow_html=True)
st.title("Make room for the answer.")
st.markdown('<p class="intro">Ask one clear question. AstroWeave coordinates the right specialists and methodologies, then brings the signal back to you.</p>', unsafe_allow_html=True)

st.markdown('<div class="workspace-label">New reading</div>', unsafe_allow_html=True)
with st.container(border=True):
    st.markdown('<div class="panel-title"><h3>What is on your mind?</h3><span class="status">● Workspace ready</span></div>', unsafe_allow_html=True)
    with st.form("query_form"):
        query = st.text_area(
            "Astrology question",
            placeholder="Ask about your career, relationships, finances, or next chapter...",
            height=150,
            label_visibility="collapsed",
        )
        first_column, second_column = st.columns([1, 1])
        with first_column:
            methodology = st.selectbox("Methodology", ["Let the system decide", "Vedic", "KP", "Both"])
        with second_column:
            submitted = st.form_submit_button("Start reading  →", use_container_width=True)

if submitted:
    if not query.strip():
        st.warning("Enter an astrology question first.")
    elif not place_name.strip():
        st.warning("Enter your birth place so a chart can be computed.")
    else:
        payload = {
            "query": query,
            "conversation_id": conversation_id,
            "session_id": session_id,
            "username": user["email"],
            "methodology": methodology,
            "message_id": str(uuid4()),
            "birth_details": {
                "date": birth_date.isoformat(),
                "time": birth_time.strftime("%H:%M:%S"),
                "latitude": birth_latitude,
                "longitude": birth_longitude,
                "utc_offset_hours": utc_offset_hours,
                "place_name": place_name.strip(),
            },
        }
        logger.info(
            "Submitting reading request username=%s conversation_id=%s session_id=%s methodology=%s",
            user["email"],
            conversation_id,
            session_id,
            methodology,
        )
        try:
            with st.spinner("Consulting the specialists..."):
                response = httpx.post(f"{api_url.rstrip('/')}/run", json=payload, timeout=120)
        except httpx.RequestError as error:
            logger.exception("Could not connect to the API at %s", api_url)
            st.error(f"Could not connect to the API: {error}")
        else:
            logger.info("API responded with status %s", response.status_code)
            if response.is_success:
                body = response.json()
                st.markdown('<div class="workspace-label">Your reading</div>', unsafe_allow_html=True)
                st.success(body.get("answer", "Request completed."))
                with st.expander("Final state"):
                    st.json(body.get("state", {}))
            else:
                logger.error("API returned HTTP %s: %s", response.status_code, response.text)
                st.error(f"API returned HTTP {response.status_code}: {response.text}")

st.markdown('<div class="hint">Your account and workspace are local to this demo. Connect the API from the sidebar when the backend is running.</div>', unsafe_allow_html=True)
