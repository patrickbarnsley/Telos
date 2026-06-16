import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import init_db, save_profile, get_profile, create_career_path, get_career_paths, delete_career_path
from core.models import Profile
from core.ai_engine import extract_resume_text

init_db()
apply_theme()

st.title("👤 Profile")
st.subheader("Your career profile")

if "tester_name" not in st.session_state or not st.session_state.tester_name:
    params = st.query_params
    if "tester" in params and params["tester"]:
        st.session_state.tester_name = params["tester"]
    else:
        st.warning("Please start from the home page first.")
        st.page_link("app.py", label="← Go to Home")
        st.stop()

tester_name = st.session_state.tester_name

tab1, tab2 = st.tabs(["Resume & Goals", "Career Paths"])

with tab1:
    existing = get_profile(tester_name)

    if existing:
        st.success(f"✅ Profile loaded — **{existing['resume_filename']}** uploaded. Target role: **{existing['target_role']}**")
        with st.expander("View extracted resume text"):
            st.text(existing["resume_text"])
        st.markdown("---")
        st.markdown("Upload a new resume or update your details below to replace your current profile.")

    with st.form("profile_form"):
        st.markdown("### Resume")
        uploaded_file = st.file_uploader("Upload your resume (PDF or .docx)", type=["pdf", "docx"])

        st.markdown("### Career Goals")
        target_role = st.text_input(
            "Primary Target Role *",
            value=existing["target_role"] if existing else "",
            placeholder="e.g. Associate Product Manager"
        )
        goals = st.text_area(
            "Career Goals",
            value=existing["goals"] if existing and existing["goals"] else "",
            placeholder="e.g. Break into product management at a tech company within 12 months..."
        )
        submitted = st.form_submit_button("Save Profile")

        if submitted:
            if not target_role:
                st.error("Target Role is required.")
            elif not uploaded_file and not existing:
                st.error("Please upload your resume.")
            else:
                if uploaded_file:
                    with st.spinner("Extracting resume text..."):
                        try:
                            resume_text = extract_resume_text(uploaded_file)
                            resume_filename = uploaded_file.name
                        except ValueError as e:
                            st.error(str(e))
                            st.stop()
                else:
                    resume_text = existing["resume_text"]
                    resume_filename = existing["resume_filename"]

                profile = Profile(
                    resume_text=resume_text,
                    resume_filename=resume_filename,
                    target_role=target_role,
                    goals=goals if goals else None
                )
                save_profile(profile, tester_name)
                st.success("Profile saved!")
                st.rerun()

with tab2:
    st.markdown("### Career Paths")
    st.markdown("Create separate campaign tracks for different target roles. Each path can be tagged to jobs in your tracker.")

    career_paths = get_career_paths(tester_name)

    if career_paths:
        for path in career_paths:
            with st.expander(f"**{path['path_name']}** — {path['target_role']}"):
                st.markdown(f"**Target Role:** {path['target_role']}")
                if path.get('goals'):
                    st.markdown(f"**Goals:** {path['goals']}")
                st.markdown(f"**Created:** {path['created_at']}")
                if st.button("🗑️ Delete Path", key=f"del_path_{path['id']}"):
                    delete_career_path(path['id'])
                    st.rerun()
    else:
        st.info("No career paths yet. Add one below.")

    st.markdown("---")
    st.markdown("### Add New Career Path")
    with st.form("add_career_path"):
        path_name = st.text_input("Path Name *", placeholder="e.g. APM Track, IT PM Track, Admin Track")
        path_target_role = st.text_input("Target Role *", placeholder="e.g. Associate Product Manager")
        path_goals = st.text_area("Goals for this path", placeholder="e.g. Land an APM role at a Series B tech company within 12 months")
        if st.form_submit_button("Add Career Path"):
            if not path_name or not path_target_role:
                st.error("Path Name and Target Role are required.")
            else:
                create_career_path(tester_name, path_name, path_target_role, path_goals)
                st.success(f"Career path '{path_name}' created!")
                st.rerun()

show_help("Profile")