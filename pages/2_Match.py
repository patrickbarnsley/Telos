import streamlit as st
import json
from core.database import init_db, get_jobs, get_profile, save_match_result, get_match_results
from core.ai_engine import score_match

init_db()

st.title("🎯 Match")
st.subheader("Score your resume against any job description")

profile = get_profile()

if not profile:
    st.warning("You haven't set up your profile yet. Go to the Profile page and upload your resume first.")
    st.stop()

jobs = get_jobs()

st.markdown("### Paste a Job Description")

with st.form("match_form"):
    job_id = None
    if jobs:
        job_options = {f"{j['company']} — {j['role']}": j['id'] for j in jobs}
        selected_job = st.selectbox("Link to a job in your tracker (optional)", ["None"] + list(job_options.keys()))
        if selected_job != "None":
            job_id = job_options[selected_job]

    jd_text = st.text_area("Job Description", height=300, placeholder="Paste the full job description here...")
    submitted = st.form_submit_button("Score My Match")

if submitted:
    if not jd_text.strip():
        st.error("Please paste a job description.")
    else:
        with st.spinner("Analyzing your match... this takes a few seconds."):
            try:
                result = score_match(
                    resume_text=profile["resume_text"],
                    job_description=jd_text,
                    target_role=profile["target_role"]
                )

                if job_id:
                    save_match_result(
                        job_id=job_id,
                        score=result["overall_score"],
                        summary=result["match_summary"],
                        matched=result["matched_requirements"],
                        missing=result["missing_requirements"],
                        actions=result["recommended_actions"],
                        jd_text=jd_text
                    )

                st.markdown("---")
                st.markdown("### Match Results")

                score = result["overall_score"]
                if score >= 75:
                    st.success(f"### {score}% Match")
                elif score >= 50:
                    st.warning(f"### {score}% Match")
                else:
                    st.error(f"### {score}% Match")

                st.markdown(f"**Summary:** {result['match_summary']}")
                st.markdown("---")

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("### ✅ What You Have")
                    for item in result["matched_requirements"]:
                        st.markdown(f"- {item}")

                with col2:
                    st.markdown("### ❌ What You're Missing")
                    for item in result["missing_requirements"]:
                        st.markdown(f"- {item}")

                st.markdown("---")
                st.markdown("### 🔧 Recommended Actions")
                for action in result["recommended_actions"]:
                    st.markdown(f"- {action}")

            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")