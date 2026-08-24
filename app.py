import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import init_db
from core.auth import (sign_in, sign_up, send_password_reset, verify_recovery,
                       set_password_with_client, remember_session, resume_session,
                       forget_session, MIN_PASSWORD)
from core.demo import enter_demo, is_demo, DEMO_EMAIL
from core.plans import (get_plan, plan_label, join_waitlist, used_this_month,
                        limit_for, PLANS, MATCH, ROADMAP, UNLIMITED, SUPPORT_EMAIL)

st.set_page_config(
    page_title="Telos: Know what to fix before you apply again",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_theme()


@st.cache_resource
def initialize_database():
    init_db()


initialize_database()

for key, default in [("user_email", ""), ("tester_name", ""), ("session_token", "")]:
    if key not in st.session_state:
        st.session_state[key] = default

params = st.query_params

st.markdown("""
<style>
.hero-title { font-size: 46px; font-weight: 800; color: #FFFFFF; margin-bottom: 2px;
  letter-spacing: -0.03em; display: flex; align-items: center; gap: 14px; }
.hero-accent { color: #C9A84C; }
.hero-sub { font-size: 17px; color: #A0A7B8; margin-bottom: 22px; }

/* The same ring the landing page uses. A person who clicks through from the
   site should not feel they have landed somewhere else. */
.logo-mark { width: 38px; height: 38px; border-radius: 50%; border: 4px solid #C9A84C;
  position: relative; flex: none; display: inline-block; }
.logo-mark::after { content: ""; position: absolute; inset: 9px; border-radius: 50%; background: #C9A84C; }

.footer { color: #A0A7B8; font-size: 13px; text-align: center; margin-top: 44px; line-height: 1.7; }
/* Streamlit paints raw anchors the browser default blue, which fights the theme. */
.footer a { color: #E0BC5E; text-decoration: none; }
.footer a:hover { color: #C9A84C; text-decoration: underline; }
.footer a:focus-visible { outline: 2px solid #E0BC5E; outline-offset: 2px; border-radius: 3px; }
.plan-chip { display:inline-block; padding:3px 11px; border-radius:100px; font-size:12px; font-weight:600;
  background:rgba(201,168,76,.12); border:1px solid rgba(201,168,76,.3); color:#C9A84C; }
.demo-bar { background:rgba(201,168,76,.1); border:1px solid rgba(201,168,76,.35);
  border-radius:8px; padding:13px 17px; margin-bottom:22px; font-size:14.5px; color:#E8E4DA; }
</style>
""", unsafe_allow_html=True)


def _persist_login(email, remember=True):
    """Put the account in session state and, optionally, mint a durable token."""
    st.session_state.user_email = email
    st.session_state.tester_name = email
    if remember:
        token = remember_session(email)
        st.session_state.session_token = token
        st.query_params["s"] = token


# --------------------------------------------------------------- deep links
# ?demo=1                        open the read-only demo
# ?waitlist=1                    Pro waitlist form
# ?token_hash=...&type=recovery  password reset landing, from the email
# ?s=...                         a remembered session, restored on refresh

if params.get("demo") and not st.session_state.user_email:
    enter_demo()
    st.query_params.clear()
    st.rerun()

if not st.session_state.user_email and params.get("s"):
    restored = resume_session(params.get("s"))
    if restored:
        st.session_state.user_email = restored
        st.session_state.tester_name = restored
        st.session_state.session_token = params.get("s")

show_waitlist = bool(params.get("waitlist"))
recovery_token = params.get("token_hash") if params.get("type") == "recovery" else None


def waitlist_form():
    st.markdown("### Join the Pro waitlist")
    st.caption("Pro is not taking payments yet. Leave your email and you will hear before it launches.")
    with st.form("waitlist_form"):
        wl_email = st.text_input("Email", value="" if is_demo() else st.session_state.get("user_email", ""))
        wl_note = st.text_area("What would make Pro worth paying for? (optional)", height=90)
        if st.form_submit_button("Join the waitlist"):
            if not wl_email or "@" not in wl_email:
                st.error("Enter a valid email address.")
            else:
                try:
                    join_waitlist(wl_email, wl_note)
                    st.success("You are on the list. That note genuinely shapes what gets built.")
                except Exception:
                    st.error(f"Could not save that. Email {SUPPORT_EMAIL} and we will add you by hand.")


# ------------------------------------------------------- password reset page
if recovery_token and not st.session_state.user_email:
    st.markdown('<div class="hero-title">Choose a new <span class="hero-accent">password</span></div>',
                unsafe_allow_html=True)

    if "recovery_client" not in st.session_state:
        result = verify_recovery(recovery_token)
        if not result["ok"]:
            st.error(result["error"])
            st.page_link("app.py", label="Back to sign in")
            st.stop()
        st.session_state.recovery_client = result["client"]
        st.session_state.recovery_email = result["email"]

    st.caption(f"Resetting the password for {st.session_state.recovery_email}")
    with st.form("reset_form"):
        p1 = st.text_input("New password", type="password")
        p2 = st.text_input("Confirm new password", type="password")
        st.caption(f"At least {MIN_PASSWORD} characters. A short phrase works better than a complicated word.")
        if st.form_submit_button("Set new password", type="primary"):
            if p1 != p2:
                st.error("Those do not match.")
            else:
                res = set_password_with_client(st.session_state.recovery_client, p1)
                if res["ok"]:
                    email = st.session_state.recovery_email
                    del st.session_state.recovery_client
                    del st.session_state.recovery_email
                    st.query_params.clear()
                    _persist_login(email)
                    st.success("Password changed. Signing you in.")
                    st.rerun()
                else:
                    st.error(res["error"])
    st.stop()


# --------------------------------------------------------------- signed out
if not st.session_state.user_email:
    st.markdown('<div class="hero-title"><span class="logo-mark"></span><span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Know exactly what to fix before you apply again.</div>',
                unsafe_allow_html=True)

    if show_waitlist:
        waitlist_form()
        st.markdown("---")

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("#### Just looking?")
        st.markdown(
            "Open the demo and see a full pipeline, a scored match and a generated "
            "roadmap. No signup, no email, nothing to install."
        )
        if st.button("Open the live demo", type="primary", use_container_width=True):
            enter_demo()
            st.rerun()
        st.caption("Read only. AI actions are pre-generated, so the demo costs nothing to run.")

    with right:
        st.markdown("#### Use it on your own search")
        tab_login, tab_signup, tab_forgot = st.tabs(["Sign in", "Create account", "Forgot password"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                stay = st.checkbox("Keep me signed in", value=True)
                if st.form_submit_button("Sign in"):
                    if not email or not password:
                        st.error("Enter your email and password.")
                    else:
                        result = sign_in(email.strip().lower(), password)
                        if result["ok"]:
                            _persist_login(result["user"].email, remember=stay)
                            st.rerun()
                        else:
                            st.error(result["error"])

        with tab_signup:
            with st.form("signup_form"):
                new_email = st.text_input("Email", key="su_email")
                new_password = st.text_input("Password", type="password", key="su_pw")
                new_password2 = st.text_input("Confirm password", type="password", key="su_pw2")
                st.caption(f"At least {MIN_PASSWORD} characters. A short phrase is easier to remember and harder to guess.")
                agreed = st.checkbox("I agree to the terms of service and privacy policy")
                if st.form_submit_button("Create account"):
                    if not new_email or not new_password:
                        st.error("Enter an email and password.")
                    elif not agreed:
                        st.error("Please accept the terms and privacy policy to continue.")
                    elif new_password != new_password2:
                        st.error("Those passwords do not match.")
                    else:
                        result = sign_up(new_email.strip().lower(), new_password)
                        if not result["ok"]:
                            st.error(result["error"])
                        elif result.get("needs_confirmation"):
                            st.success("Account created. Check your inbox for a confirmation link, then sign in.")
                        else:
                            _persist_login(result["user"].email)
                            st.rerun()
            st.caption("[Terms](https://usetelosapp.com/terms.html) · [Privacy](https://usetelosapp.com/privacy.html)")

        with tab_forgot:
            with st.form("forgot_form"):
                fp_email = st.text_input("Email", key="fp_email")
                if st.form_submit_button("Email me a reset link"):
                    if not fp_email or "@" not in fp_email:
                        st.error("Enter a valid email address.")
                    else:
                        send_password_reset(fp_email)
                        st.success(
                            "If that address has an account, a reset link is on its way. "
                            "The link is valid for one hour."
                        )
            st.caption("We do not confirm whether an address is registered. That would reveal who is job hunting.")

        st.caption("Free plan: unlimited job tracking, 10 AI match scores a month.")

    st.markdown("---")
    st.markdown(
        f'<div class="footer">Telos, from the Greek for <em>ultimate purpose</em>. '
        f'Built to help you find and reach yours.<br>'
        f'<a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a> · '
        f'<a href="https://usetelosapp.com/privacy.html">Privacy</a> · '
        f'<a href="https://usetelosapp.com/terms.html">Terms</a></div>',
        unsafe_allow_html=True
    )
    st.stop()


# ---------------------------------------------------------------- signed in
tester_name = st.session_state.tester_name

# The sign-out control sits in its own column rather than a narrow slice: at
# [6, 1] the label wrapped onto three lines on a laptop, which reads as broken.
top_l, top_r = st.columns([7, 1.7])
with top_r:
    if st.button("Exit demo" if is_demo() else "Sign out", use_container_width=True):
        if st.session_state.get("session_token"):
            forget_session(st.session_state.session_token)
        st.session_state.user_email = ""
        st.session_state.tester_name = ""
        st.session_state.session_token = ""
        st.query_params.clear()
        st.rerun()

st.markdown('<div class="hero-title"><span class="logo-mark"></span><span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Your career campaign, organized.</div>', unsafe_allow_html=True)

if is_demo():
    st.markdown(
        '<div class="demo-bar">👋 <strong>You are in the demo account.</strong> '
        'The pipeline, match scores and roadmap below are real product output for a fictional '
        'candidate. Browsing is fully enabled; running new AI actions needs a free account.</div>',
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
    with st.expander("Need more than the Free plan allows?"):
        waitlist_form()
elif show_waitlist:
    st.markdown("---")
    waitlist_form()

st.markdown("---")
st.markdown(
    f'<div class="footer">Telos, from the Greek for <em>ultimate purpose</em>.<br>'
    f'<a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a> · '
    f'<a href="https://usetelosapp.com/privacy.html">Privacy</a> · '
    f'<a href="https://usetelosapp.com/terms.html">Terms</a></div>',
    unsafe_allow_html=True
)

show_help("app")
