import streamlit as st
from core.app_styles import apply_theme
from core.database import init_db, create_job, get_jobs, update_job, delete_job
from core.models import Job

init_db()
apply_theme()

st.title("📋 Track")
st.subheader("Your job pipeline")

STATUSES = ["applied", "screening", "interview", "offer", "rejected", "withdrawn"]

jobs = get_jobs()

# Pipeline stats
if jobs:
    total = len(jobs)
    st.markdown("### Pipeline")

    cols = st.columns(len(STATUSES))
    for i, status in enumerate(STATUSES):
        count = len([j for j in jobs if j["status"] == status])
        pct = round((count / total) * 100, 1) if total > 0 else 0
        cols[i].metric(status.capitalize(), count)

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

# Add new job form
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
                    date_applied=str(date_applied)
                )
                create_job(new_job)
                st.success(f"Added {role} at {company}!")
                st.rerun()

st.markdown("---")

# Job list
if not jobs:
    st.info("No jobs yet. Add your first one above.")
else:
    st.markdown("### All Jobs")
    filter_status = st.selectbox("Filter by status", ["All"] + STATUSES)
    filtered_jobs = jobs if filter_status == "All" else [j for j in jobs if j["status"] == filter_status]

    for job in filtered_jobs:
        with st.expander(f"**{job['company']}** — {job['role']} | {job['status'].capitalize()}"):
            col1, col2 = st.columns([4, 1])

            with col1:
                with st.form(f"edit_{job['id']}"):
                    e_company = st.text_input("Company", value=job["company"])
                    e_role = st.text_input("Role", value=job["role"])
                    e_status = st.selectbox("Status", STATUSES, index=STATUSES.index(job["status"]))
                    e_url = st.text_input("URL", value=job["url"] or "")
                    e_location = st.text_input("Location", value=job["location"] or "")
                    e_notes = st.text_area("Notes", value=job["notes"] or "")

                    if st.form_submit_button("Save Changes"):
                        update_job(job["id"], {
                            "company": e_company,
                            "role": e_role,
                            "status": e_status,
                            "url": e_url or None,
                            "location": e_location or None,
                            "notes": e_notes or None
                        })
                        st.success("Saved!")
                        st.rerun()

            with col2:
                if st.button("🗑️ Delete", key=f"del_{job['id']}"):
                    delete_job(job["id"])
                    st.rerun()