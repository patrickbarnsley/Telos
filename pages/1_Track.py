import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import create_job, get_jobs, update_job, delete_job, get_career_paths, get_company_stats, get_match_results
from core.models import Job
from core.ai_engine import extract_jd_from_image

apply_theme()

st.title("📋 Track")
st.subheader("Your job pipeline")

if "tester_name" not in st.session_state or not st.session_state.tester_name:
    params = st.query_params
    if "tester" in params and params["tester"]:
        st.session_state.tester_name = params["tester"]
    else:
        st.warning("Please start from the home page first.")
        st.page_link("app.py", label="← Go to Home")
        st.stop()

tester_name = st.session_state.tester_name

STATUSES = ["applied", "screening", "interview", "offer", "rejected", "withdrawn", "recruiter_outreach"]
OUTCOME_STATUSES = ["offer", "rejected"]


def fmt_salary(lo, hi):
    """Format a salary range for display. Returns None if both ends are empty."""
    if not lo and not hi:
        return None
    if lo and hi:
        return f"${lo:,} – ${hi:,}"
    if lo:
        return f"${lo:,}+"
    return f"Up to ${hi:,}"


jobs = get_jobs(tester_name)
career_paths = get_career_paths(tester_name)
path_names = ["None"] + [p["path_name"] for p in career_paths]

tab1, tab2 = st.tabs(["Pipeline", "Companies"])

with tab1:
    if jobs:
        total = len(jobs)
        st.markdown("### Pipeline")

        cols = st.columns(len(STATUSES))
        for i, status in enumerate(STATUSES):
            count = len([j for j in jobs if j["status"] == status])
            cols[i].metric(status.replace("_", " ").capitalize(), count)

        st.markdown("---")

        st.markdown("### Funnel")
        responded = len([j for j in jobs if j["status"] in ["screening", "interview", "offer", "rejected"]])
        interviewed = len([j for j in jobs if j["status"] in ["interview", "offer"]])
        offered = len([j for j in jobs if j["status"] == "offer"])

        response_rate = round((responded / total) * 100, 1) if total > 0 else 0
        interview_rate = round((interviewed / total) * 100, 1) if total > 0 else 0
        offer_rate = round((offered / total) * 100, 1) if total > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Applications", total)
        m2.metric("Response Rate", f"{response_rate}%")
        m3.metric("Interview Rate", f"{interview_rate}%")
        m4.metric("Offer Rate", f"{offer_rate}%")

        st.markdown("---")

    with st.expander("➕ Add New Job", expanded=len(jobs) == 0):
        # Reset the JD box after a successful add (must run before the widget is created).
        if st.session_state.pop("_reset_add_jd", False):
            st.session_state["add_jd"] = ""
            st.session_state.pop("_add_jd_pending", None)
        st.session_state.setdefault("add_jd", "")

        st.markdown("**Job Description (optional)**")
        st.caption("Type or paste it below, or extract it from a screenshot. It auto-loads in Match.")
        shot = st.file_uploader(
            "Screenshot of the job posting",
            type=["png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff"],
            key="add_jd_shot"
        )
        if shot is not None and st.button("📷 Extract text from screenshot", key="add_jd_extract"):
            extracted = None
            try:
                with st.spinner("Reading the screenshot..."):
                    extracted = extract_jd_from_image(shot)
            except Exception as e:
                st.error(f"Couldn't read that image: {e}")
            if extracted is not None:
                if st.session_state["add_jd"].strip():
                    st.session_state["_add_jd_pending"] = extracted
                else:
                    st.session_state["add_jd"] = extracted
                st.rerun()

        if st.session_state.get("_add_jd_pending"):
            st.warning("You already have description text entered. Replace it with the extracted text?")
            rc1, rc2 = st.columns(2)
            if rc1.button("Replace", key="add_jd_replace"):
                st.session_state["add_jd"] = st.session_state.pop("_add_jd_pending")
                st.rerun()
            if rc2.button("Keep what I have", key="add_jd_keep"):
                st.session_state.pop("_add_jd_pending", None)
                st.rerun()

        st.text_area(
            "Review the description",
            key="add_jd",
            height=180,
            placeholder="The job description will appear here for you to review and edit before saving."
        )

        with st.form("add_job_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                company = st.text_input("Company *")
                role = st.text_input("Role *")
                status = st.selectbox("Status", STATUSES)
                date_applied = st.date_input("Date Applied")
            with col2:
                url = st.text_input("Job URL")
                location = st.text_input("Location")

            st.markdown("**Salary**")
            sc1, sc2 = st.columns(2)
            with sc1:
                st.caption("Posted range (from the listing)")
                posted_min = st.number_input("Posted Min", min_value=0, value=0, key="add_posted_min")
                posted_max = st.number_input("Posted Max", min_value=0, value=0, key="add_posted_max")
            with sc2:
                st.caption("Your requested range")
                requested_min = st.number_input("Requested Min", min_value=0, value=0, key="add_req_min")
                requested_max = st.number_input("Requested Max", min_value=0, value=0, key="add_req_max")

            career_path_selection = st.selectbox("Career Path", path_names)
            selected_path_id_for_job = next((p["id"] for p in career_paths if p["path_name"] == career_path_selection), None) if career_path_selection != "None" else None
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Job")

            if submitted:
                if not company or not role:
                    st.error("Company and Role are required.")
                else:
                    jd_val = st.session_state.get("add_jd", "")
                    new_job = Job(
                        company=company,
                        role=role,
                        status=status,
                        url=url if url else None,
                        location=location if location else None,
                        posted_salary_min=posted_min if posted_min > 0 else None,
                        posted_salary_max=posted_max if posted_max > 0 else None,
                        requested_salary_min=requested_min if requested_min > 0 else None,
                        requested_salary_max=requested_max if requested_max > 0 else None,
                        notes=notes if notes else None,
                        jd_text=jd_val if jd_val.strip() else None,
                        date_applied=str(date_applied),
                        career_path_id=selected_path_id_for_job
                    )
                    create_job(new_job, tester_name)
                    st.success(f"Added {role} at {company}!")
                    st.session_state["_reset_add_jd"] = True
                    st.rerun()

    st.markdown("---")

    if not jobs:
        st.info("No jobs yet. Add your first one above.")
    else:
        st.markdown("### All Jobs")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_status = st.selectbox("Filter by status", ["All"] + STATUSES)
        with col_f2:
            filter_path = st.selectbox("Filter by career path", ["All"] + [p["path_name"] for p in career_paths])

        filtered_jobs = jobs
        if filter_status != "All":
            filtered_jobs = [j for j in filtered_jobs if j["status"] == filter_status]
        if filter_path != "All":
            filter_path_id = next((p["id"] for p in career_paths if p["path_name"] == filter_path), None)
            filtered_jobs = [j for j in filtered_jobs if j.get("career_path_id") == filter_path_id]

        for job in filtered_jobs:
            with st.expander(f"**{job['company']}** — {job['role']} | {job['status'].replace('_', ' ').capitalize()}"):
                col1, col2 = st.columns([4, 1])

                with col1:
                    with st.form(f"edit_{job['id']}"):
                        e_company = st.text_input("Company", value=job["company"])
                        e_role = st.text_input("Role", value=job["role"])
                        e_status = st.selectbox("Status", STATUSES, index=STATUSES.index(job["status"]) if job["status"] in STATUSES else 0)
                        e_url = st.text_input("URL", value=job["url"] or "")
                        e_location = st.text_input("Location", value=job["location"] or "")

                        st.markdown("**Salary**")
                        esc1, esc2 = st.columns(2)
                        with esc1:
                            st.caption("Posted range")
                            e_posted_min = st.number_input("Posted Min", min_value=0, value=job.get("posted_salary_min") or 0, key=f"epmin_{job['id']}")
                            e_posted_max = st.number_input("Posted Max", min_value=0, value=job.get("posted_salary_max") or 0, key=f"epmax_{job['id']}")
                        with esc2:
                            st.caption("Requested range")
                            e_req_min = st.number_input("Requested Min", min_value=0, value=job.get("requested_salary_min") or 0, key=f"ermin_{job['id']}")
                            e_req_max = st.number_input("Requested Max", min_value=0, value=job.get("requested_salary_max") or 0, key=f"ermax_{job['id']}")

                        e_notes = st.text_area("Notes", value=job["notes"] or "")
                        e_jd_text = st.text_area("Job Description", value=job.get("jd_text") or "", height=150, key=f"jd_{job['id']}", placeholder="Paste the job description here — it'll auto-load in Match.")

                        current_path_id = job.get("career_path_id")
                        current_path_name = next((p["path_name"] for p in career_paths if p["id"] == current_path_id), "None")
                        path_idx = path_names.index(current_path_name) if current_path_name in path_names else 0
                        e_career_path = st.selectbox("Career Path", path_names, index=path_idx)

                        if e_status in OUTCOME_STATUSES:
                            st.markdown("**Outcome Tracking**")
                            e_outcome_date = st.date_input("Outcome Date", value=None)
                            e_predictive = st.radio(
                                "Did the match score feel predictive?",
                                ["Yes", "No", "Unsure", "No match score run"],
                                horizontal=True
                            )
                        else:
                            e_outcome_date = None
                            e_predictive = None

                        if st.form_submit_button("Save Changes"):
                            e_path_id = next((p["id"] for p in career_paths if p["path_name"] == e_career_path), None)
                            update_fields = {
                                "company": e_company,
                                "role": e_role,
                                "status": e_status,
                                "url": e_url or None,
                                "location": e_location or None,
                                "posted_salary_min": e_posted_min if e_posted_min > 0 else None,
                                "posted_salary_max": e_posted_max if e_posted_max > 0 else None,
                                "requested_salary_min": e_req_min if e_req_min > 0 else None,
                                "requested_salary_max": e_req_max if e_req_max > 0 else None,
                                "notes": e_notes or None,
                                "jd_text": e_jd_text if e_jd_text.strip() else None,
                                "career_path_id": e_path_id
                            }
                            if e_outcome_date:
                                update_fields["outcome_date"] = str(e_outcome_date)
                            if e_predictive:
                                update_fields["match_predictive"] = e_predictive
                            update_job(job["id"], update_fields)
                            st.success("Saved!")
                            st.rerun()

                with col2:
                    posted_range = fmt_salary(job.get("posted_salary_min"), job.get("posted_salary_max"))
                    requested_range = fmt_salary(job.get("requested_salary_min"), job.get("requested_salary_max"))
                    if posted_range:
                        st.markdown(f"**Posted:** {posted_range}")
                    if requested_range:
                        st.markdown(f"**Requested:** {requested_range}")
                    if job.get("outcome_date"):
                        st.markdown(f"**Outcome:** {job['outcome_date']}")
                    if job.get("match_predictive"):
                        st.markdown(f"**Predictive:** {job['match_predictive']}")
                    if st.button("🗑️ Delete", key=f"del_{job['id']}"):
                        delete_job(job["id"])
                        st.rerun()

with tab2:
    st.markdown("### Company Profiles")
    company_stats = get_company_stats(tester_name)

    if not company_stats:
        st.info("No company data yet. Add jobs in the Pipeline tab to see company profiles here.")
    else:
        for c in company_stats:
            with st.expander(f"**{c['company']}** — {c['total_applications']} application(s) | Best match: {c['best_score'] or 'N/A'}%"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Applications", c['total_applications'])
                col2.metric("Match Runs", c['total_match_runs'])
                col3.metric("Best Score", f"{c['best_score']}%" if c['best_score'] else "N/A")
                st.markdown(f"**First applied:** {c['first_applied'] or 'N/A'}")
                st.markdown(f"**Last activity:** {c['last_activity'] or 'N/A'}")

show_help("Track")