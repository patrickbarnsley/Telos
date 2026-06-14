import streamlit as st

st.set_page_config(
    page_title="Telos",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Telos")
st.subheader("Your career campaign, organized.")

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📋 Track")
    st.markdown("Log every job you're pursuing. Track status, contacts, and notes in one place.")

with col2:
    st.markdown("### 🎯 Match")
    st.markdown("Paste a job description and see how your profile stacks up — before you apply.")

with col3:
    st.markdown("### 🗺️ Guide")
    st.markdown("Get an AI-powered roadmap to close skill gaps and reach your target role.")

st.markdown("---")
st.markdown("Use the sidebar to navigate between pillars.")