import streamlit as st
import json
from core.database import init_db, get_profile, get_all_match_results
from core.ai_engine import generate_critical_path, chat_with_advisor

init_db()

st.title("🗺️ Guide")
st.subheader("Your critical path to your target role")

profile = get_profile()

if not profile:
    st.warning("You haven't set up your profile yet. Go to the Profile page and upload your resume first.")
    st.stop()

match_history = get_all_match_results()

if "critical_path" not in st.session_state:
    st.session_state.critical_path = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(f"**Target Role:** {profile['target_role']}")
    if profile.get('goals'):
        st.markdown(f"**Goals:** {profile['goals']}")
with col2:
    if st.button("🔄 Generate Critical Path", type="primary"):
        with st.spinner("Building your critical path..."):
            try:
                st.session_state.critical_path = generate_critical_path(profile, match_history)
                st.session_state.chat_history = []
                st.rerun()
            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")

if st.session_state.critical_path:
    cp = st.session_state.critical_path

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📍 Where You Are")
        st.info(cp.get("current_state", ""))
    with col2:
        st.markdown("### 🎯 Where You're Going")
        st.success(cp.get("target_state", ""))

    st.markdown("---")
    st.markdown("### 🔍 Gap Summary")
    st.markdown(cp.get("gap_summary", ""))

    st.markdown("---")
    st.markdown("### 🛤️ Critical Path Milestones")

    for milestone in cp.get("milestones", []):
        with st.expander(f"**Milestone {milestone['order']}: {milestone['title']}** — {milestone['timeline']}"):
            st.markdown(f"**What and Why:** {milestone['description']}")
            st.markdown("**Actions:**")
            for action in milestone.get("actions", []):
                st.markdown(f"- {action}")
            st.markdown(f"**✅ Done When:** {milestone['success_criteria']}")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎓 Critical Certifications")
        for cert in cp.get("critical_certs", []):
            st.markdown(f"- {cert}")
    with col2:
        st.markdown("### ⏱️ Timeline & Risk")
        st.markdown(f"**Estimated Timeline:** {cp.get('estimated_timeline', '')}")
        st.markdown(f"**Biggest Risk:** {cp.get('biggest_risk', '')}")

    st.markdown("---")
    st.markdown("### 💬 Ask Your Advisor")
    st.markdown("Drill down on any part of your critical path.")

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Ask anything about your critical path...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    api_history = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history[:-1]
                    ]
                    response = chat_with_advisor(
                        profile=profile,
                        critical_path=cp,
                        conversation_history=api_history,
                        user_message=user_input
                    )
                    st.markdown(response)
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Something went wrong: {str(e)}")

else:
    st.markdown("---")
    st.info("Click **Generate Critical Path** to build your personalized roadmap.")
    st.markdown("Telos will analyze your resume, target role, and match history to build a specific step-by-step path to your goal.")