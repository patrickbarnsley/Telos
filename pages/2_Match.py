import streamlit as st
from core.app_styles import apply_theme, show_help
import json
from core.database import get_jobs, get_profile, save_match_result, get_all_match_results, get_resume_versions, get_active_resume, delete_match_result, get_match_page_data
from core.ai_engine import score_match, check_company_legitimacy
from core.auth import require_login
from core.demo import demo_banner
from core.plans import quota_gate, quota_caption, record_usage, check_quota, MATCH, SCAM_CHECK

apply_theme()

st.title("🎯 Match")
st.subheader("Score your resume against any job description")

require_login()
tester_name = st.session_state.tester_name
demo_banner()

page_data = get_match_page_data(tester_name)
profile = page_data["profile"]

if not profile:
    st.warning("You haven't set up your profile yet. Go to the Profile page and upload your resume first.")
    st.stop()

jobs = page_data["jobs"]

if not jobs:
    st.warning("No jobs in your tracker yet. Go to Track and add a job first.")
    st.stop()

resume_versions = page_data["resume_versions"]
active_resume = next((v for v in resume_versions if v["is_active"] == 1), None)

st.markdown("### Score a Job")

job_options = {f"{j['company']} — {j['role']}": j for j in jobs}
selected_job_label = st.selectbox("Select a job from your tracker", list(job_options.keys()))
selected_job = job_options[selected_job_label]
saved_jd = selected_job.get("jd_text") or ""

if saved_jd:
    st.caption("✅ Loaded the description saved for this job in Track. You can edit it here for this score — your saved version won't change.")
else:
    st.caption("No description saved for this job yet. Paste one below, or add it in Track and it'll auto-load next time.")

with st.form("match_form"):
    jd_text = st.text_area("Job Description", value=saved_jd, height=300, key=f"jd_input_{selected_job['id']}", placeholder="Paste the full job description here...")
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
    st.caption(quota_caption(tester_name, MATCH))

if submitted:
    if not jd_text.strip():
        st.error("Please paste a job description.")
    elif not quota_gate(tester_name, MATCH):
        pass
    else:
        job_id = selected_job["id"]
        company = selected_job["company"]
        role = selected_job["role"]

        scam_allowed, _scam_used, _scam_limit = check_quota(tester_name, SCAM_CHECK)
        with st.spinner("Checking company legitimacy..."):
            try:
                if not scam_allowed:
                    raise RuntimeError("monthly employer-check limit reached")
                scam_result = check_company_legitimacy(company, jd_text)
                record_usage(tester_name, SCAM_CHECK)
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
                record_usage(tester_name, MATCH)

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
st.markdown("---")
st.markdown("### 📋 Match History")

all_results = page_data["match_results"]

if not all_results:
    st.info("No matches scored yet. Select a job and paste a description above to get started.")
else:
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        all_versions = sorted(list(set([r.get("resume_version_label") or "Original" for r in all_results])))
        version_filter = st.selectbox("Filter by resume version", ["All"] + all_versions)

    with col_f2:
        all_dates = sorted(list(set([r["scored_at"] for r in all_results if r["scored_at"]])), reverse=True)
        date_filter = st.selectbox("Filter by date", ["All"] + all_dates)

    with col_f3:
        search_term = st.text_input("Search by company or role", placeholder="e.g. Google, Product Manager")

    filtered_results = all_results
    if version_filter != "All":
        filtered_results = [r for r in filtered_results if (r.get("resume_version_label") or "Original") == version_filter]
    if date_filter != "All":
        filtered_results = [r for r in filtered_results if r["scored_at"] == date_filter]
    if search_term:
        search_lower = search_term.lower()
        filtered_results = [r for r in filtered_results if
            search_lower in (r.get("company") or "").lower() or
            search_lower in (r.get("role") or "").lower()]

    if not filtered_results:
        st.info("No matches found with current filters.")
    else:
        if "compare_selected" not in st.session_state:
            st.session_state.compare_selected = []

        st.caption("☑️ Check up to 2 results to compare them side by side.")

        selected_ids = []

        for r in filtered_results:
            label = f"{r.get('company', 'Unknown')} — {r.get('role', 'Unknown')}"
            score = r["overall_score"]
            date = r["scored_at"]
            version = r.get("resume_version_label") or "Original"

            if score >= 75:
                score_label = f"✅ {score}%"
            elif score >= 60:
                score_label = f"⚠️ {score}%"
            else:
                score_label = f"🔴 {score}%"

            col_check, col_content = st.columns([1, 11])

            with col_check:
                checked = st.checkbox("Compare", key=f"compare_{r['id']}", value=r["id"] in st.session_state.compare_selected, label_visibility="collapsed")
                if checked and r["id"] not in selected_ids:
                    selected_ids.append(r["id"])

            with col_content:
                with st.expander(f"**{label}** | {score_label} | {version} | {date}"):
                    st.markdown(f"**Summary:** {r['match_summary']}")

                    matched = json.loads(r["matched_reqs"]) if r["matched_reqs"] else []
                    missing = json.loads(r["missing_reqs"]) if r["missing_reqs"] else []
                    certs = json.loads(r["recommended_certs"]) if r["recommended_certs"] else []
                    actions = json.loads(r["recommended_actions"]) if r["recommended_actions"] else []

                    if matched:
                        st.markdown("**✅ What You Had**")
                        for item in matched:
                            st.markdown(f"- {item}")

                    if missing:
                        st.markdown("**❌ What Was Missing**")
                        for item in missing:
                            st.markdown(f"- {item}")

                    if certs:
                        st.markdown("**🎓 Recommended Certs**")
                        st.caption("⚠️ AI-generated — verify before pursuing.")
                        for cert in certs:
                            st.markdown(f"- {cert}")

                    if actions:
                        st.markdown("**🔧 Recommended Actions**")
                        for action in actions:
                            st.markdown(f"- {action}")

                    if st.button("🗑️ Delete", key=f"del_match_{r['id']}"):
                        delete_match_result(r["id"], tester_name)
                        st.rerun()

        st.session_state.compare_selected = selected_ids

        if len(selected_ids) == 2:
            st.markdown("---")
            st.markdown("### 🔄 Comparison View")
            results_to_compare = [r for r in all_results if r["id"] in selected_ids]

            col1, col2 = st.columns(2)
            for i, r in enumerate(results_to_compare):
                col = col1 if i == 0 else col2
                with col:
                    version = r.get("resume_version_label") or "Original"
                    score = r["overall_score"]
                    st.markdown(f"#### {version}")
                    if score >= 75:
                        st.success(f"**{score}% Match**")
                    elif score >= 60:
                        st.warning(f"**{score}% Match**")
                    else:
                        st.error(f"**{score}% Match**")
                    st.markdown(f"_{r['match_summary']}_")
                    missing = json.loads(r["missing_reqs"]) if r["missing_reqs"] else []
                    if missing:
                        st.markdown("**❌ Gaps:**")
                        for item in missing:
                            st.markdown(f"- {item}")
        elif len(selected_ids) > 2:
            st.warning("Select only 2 results to compare.")

show_help("Match")