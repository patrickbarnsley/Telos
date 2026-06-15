import streamlit as st
from core.app_styles import apply_theme

st.set_page_config(
    page_title="Telos",
    page_icon="🎯",
    layout="wide"
)

apply_theme()

st.markdown("""
<style>
.nav-card {
    background-color: #1A1D27;
    border: 1px solid #2D3148;
    border-radius: 12px;
    padding: 32px 24px;
    text-align: center;
    transition: all 0.2s ease;
    cursor: pointer;
    height: 200px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}
.nav-card:hover {
    border-color: #C9A84C;
    box-shadow: 0 0 20px rgba(201, 168, 76, 0.15);
    transform: translateY(-2px);
}
.nav-card .icon {
    font-size: 48px;
    margin-bottom: 12px;
}
.nav-card .title {
    color: #FFFFFF;
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 8px;
}
.nav-card .desc {
    color: #A0A7B8;
    font-size: 13px;
    line-height: 1.4;
}
.hero-title {
    font-size: 48px;
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
    margin-bottom: 40px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero-title">🎯 <span class="hero-accent">Telos</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Your career campaign, organized.</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div class="nav-card">
        <div class="icon">👤</div>
        <div class="title">Profile</div>
        <div class="desc">Upload your resume and set your target role</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/0_Profile.py", label="Go to Profile →")

with col2:
    st.markdown("""
    <div class="nav-card">
        <div class="icon">☑️</div>
        <div class="title">Track</div>
        <div class="desc">Log every job and manage your pipeline</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_Track.py", label="Go to Track →")

with col3:
    st.markdown("""
    <div class="nav-card">
        <div class="icon">🎯</div>
        <div class="title">Match</div>
        <div class="desc">Score your resume against any job description</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_Match.py", label="Go to Match →")

with col4:
    st.markdown("""
    <div class="nav-card">
        <div class="icon">🗺️</div>
        <div class="title">Guide</div>
        <div class="desc">Get your AI-powered critical path to your goal</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/3_Guide.py", label="Go to Guide →")

st.markdown("---")
st.markdown('<p style="color: #A0A7B8; font-size: 13px; text-align: center;">Telos — from the Greek for <em>ultimate purpose</em>. Built to help you find and reach yours.</p>', unsafe_allow_html=True)