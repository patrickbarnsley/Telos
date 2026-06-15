import streamlit as st
from core.app_styles import apply_theme

st.set_page_config(
    page_title="Telos",
    page_icon="🎯",
    layout="wide"
)

apply_theme()
if "tester_name" not in st.session_state:
    st.session_state.tester_name = ""

if not st.session_state.tester_name:
    st.markdown("## Welcome to Telos Beta")
    st.markdown("Enter your name to get started. This keeps your data separate from other testers.")
    name_input = st.text_input("Your name", placeholder="e.g. Sarah")
    if st.button("Start Testing"):
        if name_input.strip():
            st.session_state.tester_name = name_input.strip()
            st.rerun()
        else:
            st.error("Please enter your name.")
    st.stop()

st.markdown("""
<style>
.nav-card-link {
    text-decoration: none;
    display: block;
}

.nav-card {
    background-color: #0F1117;
    border: 2px solid #C9A84C;
    border-radius: 12px;
    padding: 40px 24px;
    text-align: center;
    transition: all 0.2s ease;
    cursor: pointer;
    min-height: 240px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.nav-card:hover {
    box-shadow: 0 0 28px rgba(201, 168, 76, 0.25);
    transform: translateY(-3px);
    background-color: #1A1D27;
}

.nav-card .icon {
    font-size: 56px;
    margin-bottom: 16px;
    display: block;
}

.nav-card .title {
    color: #C9A84C;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 10px;
}

.nav-card .desc {
    color: #A0A7B8;
    font-size: 13px;
    line-height: 1.5;
}

.hero-title {
    font-size: 52px;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 4px;
}

.hero-accent {
    color: #C9A84C;
}

.hero-sub {
    font-size: 18px;
    color: #A0A7B8;
    margin-bottom: 48px;
}

.footer {
    color: #A0A7B8;
    font-size: 13px;
    text-align: center;
    margin-top: 48px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero-title">🎯 <span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Your career campaign, organized.</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <a href="/Profile" target="_self" class="nav-card-link">
        <div class="nav-card">
            <span class="icon">👤</span>
            <div class="title">Profile</div>
            <div class="desc">Upload your resume and set your target role</div>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <a href="/Track" target="_self" class="nav-card-link">
        <div class="nav-card">
            <span class="icon">☑️</span>
            <div class="title">Track</div>
            <div class="desc">Log every job and manage your pipeline</div>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <a href="/Match" target="_self" class="nav-card-link">
        <div class="nav-card">
            <span class="icon">🎯</span>
            <div class="title">Match</div>
            <div class="desc">Score your resume against any job description</div>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <a href="/Guide" target="_self" class="nav-card-link">
        <div class="nav-card">
            <span class="icon">🗺️</span>
            <div class="title">Guide</div>
            <div class="desc">Get your AI-powered critical path to your goal</div>
        </div>
    </a>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown('<div class="footer">Telos — from the Greek for <em>ultimate purpose</em>. Built to help you find and reach yours.</div>', unsafe_allow_html=True)