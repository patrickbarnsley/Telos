import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import init_db
from core.auth import sign_in, sign_up

st.set_page_config(
    page_title="Telos",
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

# --- Login / sign-up gate ---
if not st.session_state.user_email:
    st.markdown("## Welcome to Telos")
    st.markdown("Sign in or create an account to get started.")

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

    st.stop()

# --- Logged-in home page ---
st.markdown("""
<style>
.hero-title {
    font-size: 52px;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 4px;
}
.hero-accent { color: #C9A84C; }
.hero-sub {
    font-size: 18px;
    color: #A0A7B8;
    margin-bottom: 24px;
}
.footer {
    color: #A0A7B8;
    font-size: 13px;
    text-align: center;
    margin-top: 48px;
}
</style>
""", unsafe_allow_html=True)

top_l, top_r = st.columns([5, 1])
with top_r:
    if st.button("Log out"):
        st.session_state.user_email = ""
        st.session_state.tester_name = ""
        st.rerun()

st.markdown('<div class="hero-title">🎯 <span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Your career campaign, organized.</div>', unsafe_allow_html=True)
st.caption(f"Signed in as {st.session_state.user_email}")

st.markdown("---")
st.markdown("### Where to next?")

st.page_link("pages/0_Profile.py", label="👤  Profile — Upload your resume and set your target role")
st.page_link("pages/1_Track.py", label="☑️  Track — Log every job and manage your pipeline")
st.page_link("pages/2_Match.py", label="🎯  Match — Score your resume against any job description")
st.page_link("pages/3_Guide.py", label="🗺️  Guide — Get your AI-powered critical path to your goal")

st.markdown("---")
st.markdown('<div class="footer">Telos — from the Greek for <em>ultimate purpose</em>. Built to help you find and reach yours.</div>', unsafe_allow_html=True)

show_help("app")