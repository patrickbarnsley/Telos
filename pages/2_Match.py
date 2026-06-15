import streamlit as st
from core.app_styles import apply_theme
import json
from core.database import init_db, get_jobs, get_profile, save_match_result, get_all_match_results
from core.ai_engine import score_match, check_company_legitimacy

init_db()
apply_theme()

st.title("🎯 Match")
st.subheader("Score your resume against any job description")

tester_name = st.session_state.get("tester_name", "default")
profile = get_profile(tester_name)
if not profile:
    st.warning("You haven't set up your profile yet. Go to the Profile page and upload your resume first.")
    st.stop()

jobs = get_jobs(tester_name)

if not jobs:
    st.warning("No jobs in your tracker yet. Go to Track and add a job first.")
    st.stop()

st.markdown("### Paste a Job Description")

with st.form("match_form"):
    job_options = {f"{j['company']} — {j['role']}": j for j in jobs}
    selected_job_label = st.selectbox("Select a job from your tracker", list(job_options.keys()))

    jd_text = st.text_area("Job Description", height=300, placeholder="Paste the full job description here...")
    submitted = st.form_submit_button("Score My Match")

if submitted:
    if not jd_text.strip():
        st.error("Please paste a job description.")
    else:
        selected_job = job_options[selected_job_label]
        job_id = selected_job["id"]
        company = selected_job["company"]
        role = selected_job["role"]

        with st.spinner("Checking company legitimacy..."):
            try:
                scam_result = check_company_legitimacy(company, jd_text)
            except Exception as e:
                scam_result = {
                    "verdict": "unknown",
                    "confidence": "low",
                    "summary": f"Could not complete company check: {str(e)}",
                    "green_flags": [],
                    "red_flags": []
                }

        verdict = scam_result.get("verdict", "unknown")
        confidence = scam_result.get("confidence", "unknown").capitalize()
        if verdict == "legitimate":
            st.success(f"✅ **Company Verified** (Confidence: {confidence})")
        elif verdict == "suspicious":
            st.warning(f"⚠️ **Proceed With Caution** (Confidence: {confidence})")
        elif verdict == "likely_scam":
            st.error(f"🚨 **Likely Scam** (Confidence: {confidence})")
        else:
            st.info("ℹ️ **Check Unavailable** — could not complete company verification.")

        st.markdown(f"_{scam_result.get('summary', '')}_")

        if scam_result.get("green_flags") or scam_result.get("red_flags"):
            col1, col2 = st.columns(2)
            with col1:
                if scam_result.get("green_flags"):
                    st.markdown("**✅ Green Flags**")
                    for flag in scam_result["green_flags"]:
                        st.markdown(f"- {flag}")
            with col2:
                if scam_result.get("red_flags"):
                    st.markdown("**🚩 Red Flags**")
                    for flag in scam_result["red_flags"]:
                        st.markdown(f"- {flag}")

        st.markdown("---")

        with st.spinner("Scoring your match..."):
            try:
                result = score_match(
                    resume_text=profile["resume_text"],
                    job_description=jd_text,
                    target_role=profile["target_role"]
                )

                save_match_result(
                    score=result["overall_score"],
                    summary=result["match_summary"],
                    matched=result["matched_requirements"],
                    missing=result["missing_requirements"],
                    certs=result.get("recommended_certs", []),
                    actions=result["recommended_actions"],
                    jd_text=jd_text,
                    tester_name=tester_name,
                    job_id=job_id,
                    company=company,
                    role=role
                )

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

                if result.get("recommended_certs"):
                    st.markdown("### 🎓 Recommended Certifications")
                    for cert in result["recommended_certs"]:
                        st.markdown(f"- {cert}")
                    st.markdown("---")

                st.markdown("### 🔧 Recommended Actions")
                for action in result["recommended_actions"]:
                    st.markdown(f"- {action}")

            except Exception as e:
                st.error(f"Something went wrong: {str(e)}")

st.markdown("---")
st.markdown("### 📋 Match History")

all_results = get_all_match_results(tester_name)

if not all_results:
    st.info("No matches scored yet. Select a job and paste a description above to get started.")
else:
    for r in all_results:
        label = f"{r['company']} — {r['role']}" if r['company'] and r['role'] else "Unlinked Job"
        score = r["overall_score"]
        date = r["scored_at"]

        with st.expander(f"**{label}** | {score}% Match | {date}"):
            st.markdown(f"**Summary:** {r['match_summary']}")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**✅ What You Had**")
                for item in json.loads(r["matched_reqs"]):
                    st.markdown(f"- {item}")
            with col2:
                st.markdown("**❌ What Was Missing**")
                for item in json.loads(r["missing_reqs"]):
                    st.markdown(f"- {item}")

            certs = json.loads(r["recommended_certs"]) if r["recommended_certs"] else []
            if certs:
                st.markdown("**🎓 Recommended Certs**")
                for cert in certs:
                    st.markdown(f"- {cert}")

            st.markdown("**🔧 Recommended Actions**")
            for action in json.loads(r["recommended_actions"]):
                st.markdown(f"- {action}")