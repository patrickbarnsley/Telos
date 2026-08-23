import streamlit as st
from core.app_styles import apply_theme, show_help
import json
from core.database import get_profile, get_all_match_results, save_milestone_progress, get_milestone_progress, save_critical_path, get_critical_path, get_career_paths, get_resume_versions, get_guide_data
from core.ai_engine import generate_critical_path, chat_with_advisor
from core.auth import require_login
from core.demo import demo_banner
from core.plans import quota_gate, record_usage, ROADMAP, ADVISOR

apply_theme()

st.title("🗺️ Guide")
st.subheader("Your career skill tree")

require_login()
tester_name = st.session_state.tester_name
demo_banner()

guide_data = get_guide_data(tester_name)
profile = guide_data["profile"]

if not profile:
    st.warning("You haven't set up your profile yet. Go to the Profile page and upload your resume first.")
    st.stop()

match_history = guide_data["match_history"]
career_paths = guide_data["career_paths"]
resume_versions = guide_data["resume_versions"]

main_paths = [p for p in career_paths if p["path_type"] == "main"]
sub_paths = [p for p in career_paths if p["path_type"] == "sub"]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "active_path_id" not in st.session_state:
    st.session_state.active_path_id = None

path_options = {"Master Roadmap (All Paths)": None}
for p in main_paths:
    path_options[f"🎯 {p['path_name']} - {p['target_role']}"] = p["id"]
for p in sub_paths:
    parent = next((m for m in main_paths if m["id"] == p.get("parent_path_id")), None)
    parent_label = f" → {parent['path_name']}" if parent else ""
    path_options[f"🛤️ {p['path_name']} - {p['target_role']}{parent_label}"] = p["id"]

selected_path_label = st.selectbox("Which path are you working on?", list(path_options.keys()))
selected_path_id = path_options[selected_path_label]

if selected_path_id != st.session_state.active_path_id:
    st.session_state.active_path_id = selected_path_id
    if selected_path_id not in st.session_state.chat_history:
        st.session_state.chat_history[selected_path_id] = []

current_path_obj = next((p for p in career_paths if p["id"] == selected_path_id), None)

if selected_path_id is None:
    target_role = profile["target_role"]
    goals = profile.get("goals", "")
    path_label = "Master Roadmap"
elif current_path_obj:
    target_role = current_path_obj["target_role"]
    goals = current_path_obj.get("goals", "")
    path_label = current_path_obj["path_name"]
else:
    target_role = profile["target_role"]
    goals = profile.get("goals", "")
    path_label = "Master Roadmap"

st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown(f"**Path:** {path_label}")
    st.markdown(f"**Target Role:** {target_role}")
    if goals:
        st.markdown(f"**Goals:** {goals}")

    saved = get_critical_path(tester_name, selected_path_id)
    if saved:
        st.markdown(f"_Last generated: {saved['generated_at']}_")

with col2:
    if st.button("🔄 Generate Critical Path", type="primary") and quota_gate(tester_name, ROADMAP):
        with st.spinner("Building your critical path..."):
            try:
                path_profile = {
                    "target_role": target_role,
                    "goals": goals,
                    "resume_text": profile["resume_text"],
                    "all_paths": [{"name": p["path_name"], "role": p["target_role"], "type": p["path_type"]} for p in career_paths],
                    "resume_versions": [v["version_label"] for v in resume_versions]
                }
                new_path = generate_critical_path(path_profile, match_history)
                record_usage(tester_name, ROADMAP)
                save_critical_path(tester_name, new_path, selected_path_id)
                st.session_state.chat_history[selected_path_id] = []
                st.rerun()
            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")

saved = get_critical_path(tester_name, selected_path_id)
if saved:
    cp = saved["path"]

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

    progress = get_milestone_progress(tester_name, selected_path_id)

    for milestone in cp.get("milestones", []):
        order = milestone['order']
        is_complete = progress.get(order, False)
        label = f"~~Milestone {order}: {milestone['title']}~~ ✅" if is_complete else f"Milestone {order}: {milestone['title']} ({milestone['timeline']})"

        with st.expander(label):
            completed = st.checkbox(
                "Mark as complete",
                value=is_complete,
                key=f"milestone_{selected_path_id}_{order}"
            )
            if completed != is_complete:
                save_milestone_progress(tester_name, order, milestone['title'], completed, selected_path_id)
                st.rerun()

            st.markdown(f"**What and Why:** {milestone['description']}")
            st.markdown("**Actions:**")
            for action in milestone.get("actions", []):
                st.markdown(f"- {action}")
            st.markdown(f"**Done when:** {milestone['success_criteria']}")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎓 Critical Certifications")
        st.caption("⚠️ AI-generated. Verify each certification exists before pursuing it.")
        for cert in cp.get("critical_certs", []):
            st.markdown(f"- {cert}")
    with col2:
        st.markdown("### ⏱️ Timeline & Risk")
        st.markdown(f"**Estimated Timeline:** {cp.get('estimated_timeline', '')}")
        st.markdown(f"**Biggest Risk:** {cp.get('biggest_risk', '')}")

    st.markdown("---")
    st.markdown("### 💬 Ask Your Advisor")
    st.markdown("Ask about this path, how it connects to others, or say **'update my roadmap'** to regenerate based on new information.")

    chat_key = selected_path_id
    if chat_key not in st.session_state.chat_history:
        st.session_state.chat_history[chat_key] = []

    for message in st.session_state.chat_history[chat_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Ask anything about your career path...")

    if user_input and quota_gate(tester_name, ADVISOR):
        st.session_state.chat_history[chat_key].append({"role": "user", "content": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    path_context = {
                        "target_role": target_role,
                        "goals": goals,
                        "resume_text": profile["resume_text"],
                        "all_paths": [{"name": p["path_name"], "role": p["target_role"], "type": p["path_type"]} for p in career_paths],
                        "current_path_name": path_label
                    }

                    api_history = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.chat_history[chat_key][:-1]
                    ]

                    response = chat_with_advisor(
                        profile=path_context,
                        critical_path=cp,
                        conversation_history=api_history,
                        user_message=user_input
                    )
                    record_usage(tester_name, ADVISOR)
                    st.markdown(response)
                    st.session_state.chat_history[chat_key].append({"role": "assistant", "content": response})

                    if any(phrase in user_input.lower() for phrase in ["update my roadmap", "update the roadmap", "regenerate", "update my critical path"]):
                        with st.spinner("Updating your roadmap..."):
                            new_path = generate_critical_path(path_context, match_history)
                            record_usage(tester_name, ROADMAP)
                            save_critical_path(tester_name, new_path, selected_path_id)
                            st.success("Roadmap updated and saved.")
                            st.rerun()

                except Exception as e:
                    st.error(f"Something went wrong: {str(e)}")

else:
    st.markdown("---")
    st.info(f"Click **Generate Critical Path** to build your roadmap for **{path_label}**.")

show_help("Guide")