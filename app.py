import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import init_db
from core.auth import sign_in, sign_up
from core.demo import enter_demo, is_demo, DEMO_EMAIL
from core.plans import (get_plan, plan_label, join_waitlist, used_this_month,
                        limit_for, PLANS, MATCH, ROADMAP, UNLIMITED)

st.set_page_config(
    page_title="Telos: Run your job search like a campaign",
    page_icon="🎯",
    layout="wide"
)

apply_theme()

@st.cache_resource
def initialize_database():
    init_db()

initialize_database()

# --- Auth state ---
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "tester_name" not in st.session_state:
    st.session_state.tester_name = ""

# --- Deep links from the marketing site (usetelosapp.com) ---
# ?demo=1     -> drop straight into the read-only demo account, no signup
# ?waitlist=1 -> open the Pro waitlist form
params = st.query_params
if params.get("demo") and not st.session_state.user_email:
    enter_demo()
    st.query_params.clear()
    st.rerun()
show_waitlist = bool(params.get("waitlist"))

st.markdown("""
<style>
.hero-title { font-size: 52px; font-weight: 800; color: #FFFFFF; margin-bottom: 4px; letter-spacing: -0.03em; }
.hero-accent { color: #C9A84C; }
.hero-sub { font-size: 18px; color: #A0A7B8; margin-bottom: 24px; }
.footer { color: #A0A7B8; font-size: 13px; text-align: center; margin-top: 48px; }
.plan-chip {
  display:inline-block; padding:3px 11px; border-radius:100px; font-size:12px; font-weight:600;
  background:rgba(201,168,76,.12); border:1px solid rgba(201,168,76,.3); color:#C9A84C;
}
.demo-bar {
  background:rgba(201,168,76,.1); border:1px solid rgba(201,168,76,.35);
  border-radius:8px; padding:13px 17px; margin-bottom:22px; font-size:14.5px; color:#E8E4DA;
}
</style>
""", unsafe_allow_html=True)


# --- Pro waitlist (reachable logged in or out) ---
def waitlist_form():
    st.markdown("### Join the Pro waitlist")
    st.caption("Pro isn't taking payments yet. Leave your email and you'll hear before it launches.")
    with st.form("waitlist_form"):
        wl_email = st.text_input("Email", value=st.session_state.get("user_email", "") if not is_demo() else "")
        wl_note = st.text_area("What would make Pro worth paying for? (optional)", height=90)
        if st.form_submit_button("Join the waitlist"):
            if not wl_email or "@" not in wl_email:
                st.error("Enter a valid email address.")
            else:
                try:
                    join_waitlist(wl_email, wl_note)
                    st.success("You're on the list. Thanks. That note genuinely shapes what gets built.")
                except Exception as e:
                    st.error(f"Couldn't save that: {e}")


# --- Login / sign-up gate ---
if not st.session_state.user_email:
    st.markdown('<div class="hero-title">🎯 <span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Run your job search like a campaign, not a guessing game.</div>',
                unsafe_allow_html=True)

    if show_waitlist:
        waitlist_form()
        st.markdown("---")

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("#### Just looking?")
        st.markdown(
            "Open the demo account and see a full pipeline, a real match score, and a generated "
            "roadmap. No signup, no email, nothing to install."
        )
        if st.button("🔍  Open the live demo", type="primary", use_container_width=True):
            enter_demo()
            st.rerun()
        st.caption("Read-only. AI actions are pre-generated so the demo is free to run.")

    with right:
        st.markdown("#### Use it on your own search")
        tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Log in"):
                    if not email or not password:
                        st.error("Enter your email and password.")
                    else:
                        result = sign_in(email.strip(), password)
                        if result["ok"]:
                            st.session_state.user_email = result["user"].email
                            st.session_state.tester_name = result["user"].email
                            st.rerun()
                        else:
                            st.error(result["error"])

        with tab_signup:
            with st.form("signup_form"):
                new_email = st.text_input("Email", key="su_email")
                new_password = st.text_input("Password (at least 6 characters)", type="password", key="su_pw")
                new_password2 = st.text_input("Confirm password", type="password", key="su_pw2")
                if st.form_submit_button("Create account"):
                    if not new_email or not new_password:
                        st.error("Enter an email and password.")
                    elif new_password != new_password2:
                        st.error("Passwords don't match.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        result = sign_up(new_email.strip(), new_password)
                        if result["ok"]:
                            st.session_state.user_email = result["user"].email
                            st.session_state.tester_name = result["user"].email
                            st.success("Account created!")
                            st.rerun()
                        else:
                            st.error(result["error"])
        st.caption("Free plan: unlimited job tracking, 10 AI match scores a month.")

    st.markdown("---")
    st.markdown(
        '<div class="footer">Telos, from the Greek for <em>ultimate purpose</em>. '
        'Built to help you find and reach yours.</div>',
        unsafe_allow_html=True
    )
    st.stop()

# --- Logged-in home page ---
tester_name = st.session_state.tester_name

top_l, top_r = st.columns([5, 1])
with top_r:
    if st.button("Exit demo" if is_demo() else "Log out"):
        st.session_state.user_email = ""
        st.session_state.tester_name = ""
        st.rerun()

st.markdown('<div class="hero-title">🎯 <span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Your career campaign, organized.</div>', unsafe_allow_html=True)

if is_demo():
    st.markdown(
        '<div class="demo-bar">👋 <strong>You\'re in the demo account.</strong> '
        'The pipeline, match scores, and roadmap below are real product output for a fictional '
        'candidate. Browsing is fully enabled; running new AI actions requires a free account.</div>',
        unsafe_allow_html=True
    )
else:
    st.caption(f"Signed in as {st.session_state.user_email}")
    st.markdown(f'<span class="plan-chip">{plan_label(tester_name)} plan</span>', unsafe_allow_html=True)

    plan = get_plan(tester_name)
    if plan != "owner":
        m_lim, r_lim = limit_for(tester_name, MATCH), limit_for(tester_name, ROADMAP)
        c1, c2, c3 = st.columns(3)
        c1.metric("Match scores this month", f"{used_this_month(tester_name, MATCH)} / {m_lim}")
        c2.metric("Roadmaps this month", f"{used_this_month(tester_name, ROADMAP)} / {r_lim}")
        c3.metric("Job tracking", "Unlimited")

st.markdown("---")
st.markdown("### Where to next?")

st.page_link("pages/0_Profile.py", label="👤  Profile: Upload your resume and set your target role")
st.page_link("pages/1_Track.py", label="☑️  Track: Log every job and manage your pipeline")
st.page_link("pages/2_Match.py", label="🎯  Match: Score your resume against any job description")
st.page_link("pages/3_Guide.py", label="🗺️  Guide: Get your AI-powered critical path to your goal")

if is_demo():
    st.markdown("---")
    st.markdown("#### Ready to run this on your own resume?")
    if st.button("Create a free account", type="primary"):
        st.session_state.user_email = ""
        st.session_state.tester_name = ""
        st.rerun()
elif get_plan(tester_name) == "free":
    st.markdown("---")
    with st.expander("⚡ Need more than the Free plan allows?"):
        waitlist_form()
elif show_waitlist:
    st.markdown("---")
    waitlist_form()

st.markdown("---")
st.markdown(
    '<div class="footer">Telos, from the Greek for <em>ultimate purpose</em>. '
    'Built to help you find and reach yours.</div>',
    unsafe_allow_html=True
)

show_help("app")
