import streamlit as st
from core.app_styles import apply_theme
from core.database import init_db, save_profile, get_profile
from core.models import Profile
from core.ai_engine import extract_resume_text

init_db()
apply_theme()

st.title("👤 Profile")
st.subheader("Your career profile")

existing = get_profile()

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
        "Target Role *",
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
            save_profile(profile)
            st.success("Profile saved!")
            st.rerun()