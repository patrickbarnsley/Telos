import streamlit as st
from core.app_styles import apply_theme, show_help
from core.database import init_db, create_job, get_jobs, update_job, delete_job, get_career_paths, get_company_stats, get_match_results
from core.models import Job

init_db()
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
        with st.form("add_job_form"):
            col1, col2 = st.columns(2)
            with col1:
                company = st.text_input("Company *")
                role = st.text_input("Role *")
                status = st.selectbox("Status", STATUSES)
                date_applied = st.date_input("Date Applied")
            with col2:
                url = st.text_input("Job URL")
                location = st.text_input("Location")
                salary_min = st.number_input("Salary Min", min_value=0, value=0)
                salary_max = st.number_input("Salary Max", min_value=0, value=0)
            career_path_selection = st.selectbox("Career Path", path_names)
            selected_path_id_for_job = next((p["id"] for p in career_paths if p["path_name"] == career_path_selection), None) if career_path_selection != "None" else None
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Job")

            if submitted:
                if not company or not role:
                    st.error("Company and Role are required.")
                else:
                    new_job = Job(
                        company=company,
                        role=role,
                        status=status,
                        url=url if url else None,
                        location=location if location else None,
                        salary_min=salary_min if salary_min > 0 else None,
                        salary_max=salary_max if salary_max > 0 else None,
                        notes=notes if notes else None,
                        date_applied=str(date_applied),
                        career_path_id=selected_path_id_for_job
                    )
                    create_job(new_job, tester_name)
                    st.success(f"Added {role} at {company}!")
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
                        e_notes = st.text_area("Notes", value=job["notes"] or "")

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
                                "notes": e_notes or None,
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