import streamlit as st
from core.app_styles import apply_theme, show_help
import json
from core.database import init_db, get_jobs, get_profile, save_match_result, get_all_match_results, get_resume_versions, get_active_resume, delete_match_result
from core.ai_engine import score_match, check_company_legitimacy

init_db()
apply_theme()

st.title("🎯 Match")
st.subheader("Score your resume against any job description")

if "tester_name" not in st.session_state or not st.session_state.tester_name:
    params = st.query_params
    if "tester" in params and params["tester"]:
        st.session_state.tester_name = params["tester"]
    else:
        st.warning("Please start from the home page first.")
        st.page_link("app.py", label="← Go to Home")
        st.stop()

tester_name = st.session_state.tester_name
profile = get_profile(tester_name)

if not profile:
    st.warning("You haven't set up your profile yet. Go to the Profile page and upload your resume first.")
    st.stop()

jobs = get_jobs(tester_name)

if not jobs:
    st.warning("No jobs in your tracker yet. Go to Track and add a job first.")
    st.stop()

resume_versions = get_resume_versions(tester_name)
active_resume = get_active_resume(tester_name)

st.markdown("### Paste a Job Description")

with st.form("match_form"):
    job_options = {f"{j['company']} — {j['role']}": j for j in jobs}
    selected_job_label = st.selectbox("Select a job from your tracker", list(job_options.keys()))

    jd_text = st.text_area("Job Description", height=300, placeholder="Paste the full job description here...")
    st.caption("📏 Maximum 10,000 characters analyzed. Most job descriptions are well within this limit.")

    if resume_versions:
        version_options = {f"{v['version_label']} — {v['resume_filename']}{'  ✅' if v['is_active'] else ''}": v for v in resume_versions}
        default_idx = next((i for i, v in enumerate(resume_versions) if v["is_active"]), 0)
        selected_version_label = st.selectbox("Resume Version to Score", list(version_options.keys()), index=default_idx)
        selected_version = version_options[selected_version_label]
    else:
        selected_version = None
        st.info("No resume versions found. Upload a resume in Profile first.")

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
                resume_to_use = selected_version["resume_text"] if selected_version else profile["resume_text"]
                resume_label = selected_version["version_label"] if selected_version else "Default"
                resume_id = selected_version["id"] if selected_version else None

                result = score_match(
                    resume_text=resume_to_use,
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
                    role=role,
                    resume_version_id=resume_id,
                    resume_version_label=resume_label,
                    resume_snapshot=resume_to_use
                )

                st.markdown("### Match Results")

                st.info("ℹ️ **About this score:** Telos scores your resume the way a real ATS system would — strictly. Industry estimates suggest 70-75% of resumes are automatically rejected by ATS before a human ever sees them. A score below 70% means a real ATS may filter out your application. A score of 75%+ improves your chances of passing initial screening, but is not a guarantee.")

                if len(jd_text) > 10000:
                    st.warning(f"⚠️ Your job description was {len(jd_text):,} characters. Only the first 10,000 were analyzed.")
                else:
                    st.caption(f"📏 {len(jd_text):,} characters analyzed.")

                score = result["overall_score"]
                if score >= 75:
                    st.success(f"### {score}% Match")
                elif score >= 60:
                    st.warning(f"### {score}% Match — May be filtered by ATS")
                else:
                    st.error(f"### {score}% Match — High risk of ATS rejection")

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
                    st.caption("⚠️ AI-generated — verify each certification exists before pursuing it.")
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
        version = r.get("resume_version_label") or "Original"

        with st.expander(f"**{label}** | {score}% Match | {version} | {date}"):
            col_main, col_del = st.columns([10, 1])
            with col_del:
                if st.button("🗑️", key=f"del_match_{r['id']}"):
                    delete_match_result(r["id"])
                    st.rerun()

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

show_help("Match")