import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import save_profile, get_profile, create_career_path, get_career_paths, delete_career_path, save_resume_version, get_resume_versions, set_active_resume, delete_resume_version, get_active_resume
from core.models import Profile
from core.ai_engine import extract_resume_text

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

tab1, tab2, tab3 = st.tabs(["Resumes", "Career Paths", "Legacy Profile"])

with tab1:
    st.markdown("### Resume Versions")
    st.markdown("Store multiple resume versions and pick which one to use when scoring a match.")

    versions = get_resume_versions(tester_name)
    active = get_active_resume(tester_name)

    if versions:
        for v in versions:
            is_active = v["is_active"] == 1
            label = f"**{v['version_label']}** — {v['resume_filename']}"
            if is_active:
                label += " ✅ Active"
            with st.expander(label):
                st.markdown(f"**Uploaded:** {v['created_at']}")
                with st.expander("View resume text"):
                    st.text(v["resume_text"])
                col1, col2 = st.columns(2)
                with col1:
                    if not is_active:
                        if st.button("Set as Active", key=f"active_{v['id']}"):
                            set_active_resume(tester_name, v["id"])
                            existing_profile = get_profile(tester_name)
                            profile = Profile(
                                resume_text=v["resume_text"],
                                resume_filename=v["resume_filename"],
                                target_role=existing_profile["target_role"] if existing_profile else "Not set",
                                goals=existing_profile["goals"] if existing_profile else None
                            )
                            save_profile(profile, tester_name)
                            st.success(f"'{v['version_label']}' is now your active resume.")
                            st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"del_resume_{v['id']}"):
                        delete_resume_version(v["id"])
                        st.success("Resume version deleted. Match history using this version is preserved.")
                        st.rerun()
    else:
        st.info("No resume versions yet. Upload one below.")

    st.markdown("---")
    st.markdown("### Upload New Resume Version")
    with st.form("upload_resume_form", clear_on_submit=True):
        version_label = st.text_input("Version Label *", placeholder="e.g. Original, PM-focused, Security emphasis")
        uploaded_file = st.file_uploader("Resume file (PDF or .docx)", type=["pdf", "docx"])
        set_as_active = st.checkbox("Set as active resume", value=len(versions) == 0)
        if st.form_submit_button("Upload Resume"):
            if not version_label:
                st.error("Version label is required.")
            elif not uploaded_file:
                st.error("Please upload a file.")
            else:
                with st.spinner("Extracting resume text..."):
                    try:
                        resume_text = extract_resume_text(uploaded_file)
                        save_resume_version(tester_name, version_label, resume_text, uploaded_file.name, set_as_active)
                        if set_as_active:
                            existing_profile = get_profile(tester_name)
                            profile = Profile(
                                resume_text=resume_text,
                                resume_filename=uploaded_file.name,
                                target_role=existing_profile["target_role"] if existing_profile else "Not set",
                                goals=existing_profile["goals"] if existing_profile else None
                            )
                            save_profile(profile, tester_name)
                        st.success(f"Resume '{version_label}' uploaded successfully!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

with tab2:
    st.markdown("### Career Skill Tree")
    st.markdown("Map out your career paths — set your overarching goals at the top and the routes you can take to get there.")

    career_paths = get_career_paths(tester_name)
    main_paths = [p for p in career_paths if p["path_type"] == "main"]
    sub_paths = [p for p in career_paths if p["path_type"] == "sub"]

    if main_paths:
        st.markdown("#### 🎯 Overarching Goals")
        for path in main_paths:
            with st.expander(f"**{path['path_name']}** — {path['target_role']}"):
                st.markdown(f"**Ultimate Target:** {path['target_role']}")
                if path.get('goals'):
                    st.markdown(f"**Vision:** {path['goals']}")
                st.markdown(f"**Created:** {path['created_at']}")
                subs = [p for p in sub_paths if p.get("parent_path_id") == path["id"]]
                if subs:
                    st.markdown("**Sub Paths leading here:**")
                    for s in subs:
                        st.markdown(f"- {s['path_name']} → {s['target_role']}")
                if st.button("🗑️ Delete", key=f"del_main_{path['id']}"):
                    delete_career_path(path['id'])
                    st.rerun()

    if sub_paths:
        st.markdown("#### 🛤️ Sub Paths")
        for path in sub_paths:
            parent = next((p for p in main_paths if p["id"] == path.get("parent_path_id")), None)
            parent_label = f" → leads to **{parent['path_name']}**" if parent else ""
            with st.expander(f"**{path['path_name']}** — {path['target_role']}{parent_label}"):
                st.markdown(f"**Target Role:** {path['target_role']}")
                if path.get('goals'):
                    st.markdown(f"**Goals:** {path['goals']}")
                st.markdown(f"**Created:** {path['created_at']}")
                if st.button("🗑️ Delete", key=f"del_sub_{path['id']}"):
                    delete_career_path(path['id'])
                    st.rerun()

    if not career_paths:
        st.info("No career paths yet. Add an overarching goal below, then add sub paths beneath it.")

    st.markdown("---")
    st.markdown("### Add New Path")

    with st.form("add_career_path", clear_on_submit=True):
        path_type = st.radio("Path Type", ["Overarching Goal", "Sub Path"], horizontal=True)
        path_name = st.text_input("Path Name *", placeholder="e.g. Tech Leadership, APM Track, IT PM Now")
        path_target_role = st.text_input("Target Role *", placeholder="e.g. Senior Product Manager, Associate PM")
        path_goals = st.text_area("Goals", placeholder="e.g. Lead a product team at a Series B company within 5 years")

        parent_options = ["None"] + [p["path_name"] for p in main_paths]
        parent_selection = st.selectbox("Leads toward (for sub paths)", parent_options)

        if st.form_submit_button("Add Path"):
            if not path_name or not path_target_role:
                st.error("Path Name and Target Role are required.")
            else:
                ptype = "main" if path_type == "Overarching Goal" else "sub"
                parent_id = None
                if ptype == "sub" and parent_selection != "None":
                    parent_match = next((p for p in main_paths if p["path_name"] == parent_selection), None)
                    if parent_match:
                        parent_id = parent_match["id"]
                create_career_path(tester_name, path_name, path_target_role, ptype, path_goals, parent_id)
                st.success(f"Path '{path_name}' created!")
                st.rerun()

with tab3:
    st.markdown("### Legacy Profile")
    st.markdown("Your primary target role used by Guide when no specific career path is selected.")

    existing = get_profile(tester_name)
    if existing:
        st.success(f"✅ Primary profile set — Target role: **{existing['target_role']}**")

    with st.form("profile_form"):
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
        if st.form_submit_button("Save"):
            if not target_role:
                st.error("Target Role is required.")
            elif not existing:
                st.error("Upload a resume first in the Resumes tab.")
            else:
                profile = Profile(
                    resume_text=existing["resume_text"],
                    resume_filename=existing["resume_filename"],
                    target_role=target_role,
                    goals=goals if goals else None
                )
                save_profile(profile, tester_name)
                st.success("Profile saved!")
                st.rerun()

show_help("Profile")