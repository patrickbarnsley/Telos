"""Read-only demo account.

A hiring manager clicking a link should see the product working in about ten
seconds, without a signup form and without costing anything to serve. This
module provides that: a single shared demo user (`__demo__`) pre-loaded with a
realistic pipeline, real match output, and a real roadmap.

Everything in here is fictional. The persona is invented; no real person's
resume or job history appears in the demo.

Guarantees:
  - Demo traffic never triggers an AI call (see core.plans: the demo plan has a
    zero quota on every metered action).
  - Demo traffic never mutates data (see `blocked`).
"""
import json

from core.plans import DEMO_TESTER

DEMO_EMAIL = "demo@usetelosapp.com"

DEMO_RESUME = """JORDAN AVERY
Business Analyst | Boston, MA | jordan.avery@example.com

SUMMARY
Business analyst with 6 years supporting enterprise software delivery for
healthcare payers. Owns requirements, UAT coordination, and stakeholder
communication across concurrent workstreams.

EXPERIENCE

Senior Business Analyst — Meridian Health Systems (2022-present)
- Lead analyst on a claims-platform migration affecting 40+ internal users
  across three departments.
- Author functional requirements and acceptance criteria; run UAT cycles and
  triage defects with the vendor engineering team.
- Facilitate weekly stakeholder syncs and publish status reporting to
  directors.
- Built Excel and Power BI reporting that cut manual month-end reconciliation
  from two days to four hours.

Business Analyst — Copley Insurance Group (2019-2022)
- Gathered requirements for policy administration enhancements.
- Coordinated release validation across QA and operations.
- Maintained the requirements traceability matrix for two annual releases.

EDUCATION
B.S. Business Administration, University of Massachusetts

CERTIFICATIONS
Certified ScrumMaster (CSM), Scrum Alliance — 2023

SKILLS
Requirements gathering, UAT coordination, stakeholder management, SQL
(intermediate), Power BI, Excel, Confluence, Agile ceremonies
"""

DEMO_JOBS = [
    ("Northwind Health", "Technical Project Manager", "interview", "Boston, MA (Hybrid)", 105000, 125000,
     "Second round scheduled. Panel with delivery lead + eng manager."),
    ("Vantage Clinical", "Implementation Manager", "screening", "Remote", 98000, 118000,
     "Recruiter screen went well. Asked about EHR integrations."),
    ("Beacon Data Systems", "Technical Program Manager", "applied", "Remote", 115000, 140000,
     "Applied via Greenhouse. No response yet."),
    ("Halcyon Software", "Project Manager, Professional Services", "applied", "Boston, MA", 95000, 115000, ""),
    ("Kestrel Analytics", "Senior Business Analyst", "offer", "Remote", 102000, 112000,
     "Offer at 108k. Strong fit but lateral move — weighing against TPM roles."),
    ("Orion Payer Solutions", "Technical Project Manager", "rejected", "Waltham, MA", 110000, 130000,
     "Rejected after screen — wanted 3+ years direct PM ownership."),
    ("Lattice Health", "Implementation Consultant", "rejected", "Remote", 90000, 105000,
     "No response after 4 weeks, marked closed."),
    ("Sable Systems", "Program Manager", "applied", "Remote", 120000, 145000, ""),
    ("Foundry Medical", "Delivery Manager", "screening", "Boston, MA (Hybrid)", 108000, 128000,
     "Phone screen Thursday."),
    ("Arden Technologies", "Technical Project Manager", "applied", "Remote", 100000, 122000, ""),
    ("Pinnacle Care", "Business Systems Analyst", "rejected", "Remote", 88000, 100000, ""),
    ("Cobalt Logistics", "Project Coordinator", "applied", "Boston, MA", 72000, 85000,
     "Backup option — below target band."),
]

DEMO_JD = """Technical Project Manager — Northwind Health

We are seeking a Technical Project Manager to lead cross-functional delivery of
our provider-facing platform.

Responsibilities:
- Own end-to-end delivery for 2-3 concurrent technical projects
- Manage project scope, schedule, budget, and risk
- Coordinate across engineering, product, and clinical operations
- Run agile ceremonies and maintain sprint health
- Administer Jira workflows and reporting for the delivery org

Requirements:
- 5+ years managing cross-functional technical delivery
- Direct ownership of project budget and schedule
- Agile / Scrum certification
- Jira administration experience
- Healthcare or regulated-industry domain experience
- Strong written and verbal stakeholder communication
- PMP certification preferred
"""

DEMO_MATCHES = [
    {
        "company": "Northwind Health", "role": "Technical Project Manager", "score": 74,
        "summary": ("Strong analyst foundation with genuine cross-functional delivery exposure, but the resume "
                    "does not show direct ownership of project budget or schedule, which this role treats as a "
                    "hard requirement. Jira administration and healthcare domain depth are the other real gaps."),
        "matched": [
            "5+ years supporting cross-functional technical delivery",
            "Agile / Scrum certification (CSM, Scrum Alliance)",
            "Stakeholder communication and status reporting to director level",
            "UAT coordination across QA and operations",
            "Healthcare payer domain exposure",
        ],
        "missing": [
            "Direct ownership of project budget — resume shows support, not ownership",
            "Jira administration — Confluence is listed, Jira administration is not",
            "PMP certification (listed as preferred)",
            "Explicit schedule ownership for concurrent projects",
        ],
        "certs": [
            "Project Management Professional (PMP), Project Management Institute — directly named as preferred and the clearest single lever on this score",
            "PMI Agile Certified Practitioner (PMI-ACP), Project Management Institute — deepens the agile credential beyond CSM",
        ],
        "actions": [
            "Rewrite the claims-migration bullet to lead with ownership language and name the schedule you held",
            "Add a Jira line to skills if you administer workflows — currently only Confluence appears",
            "Quantify the 40+ user migration with a duration and a delivery date",
            "Mirror the phrase 'cross-functional delivery' from the posting into the summary line",
        ],
        "jd": DEMO_JD,
    },
    {
        "company": "Vantage Clinical", "role": "Implementation Manager", "score": 81,
        "summary": ("Good match. Implementation work maps closely onto the UAT and vendor-coordination "
                    "experience already on the resume. The gap is client-facing ownership rather than "
                    "internal stakeholder support."),
        "matched": [
            "UAT coordination and defect triage with vendor engineering",
            "Requirements authoring and acceptance criteria",
            "Healthcare payer domain experience",
            "Stakeholder facilitation and status reporting",
            "Agile ceremony participation",
        ],
        "missing": [
            "Direct client-facing implementation ownership",
            "EHR integration experience named explicitly",
            "Formal go-live / cutover leadership",
        ],
        "certs": [
            "Certified Associate in Project Management (CAPM), Project Management Institute — a faster credential than PMP if the hours requirement is not yet met",
        ],
        "actions": [
            "Reframe the vendor-coordination bullet as external-facing delivery",
            "Name the specific systems involved in the claims migration",
            "Add a cutover or go-live example if one exists",
        ],
        "jd": "Implementation Manager — Vantage Clinical\n\nLead client implementations of our clinical data platform...",
    },
    {
        "company": "Beacon Data Systems", "role": "Technical Program Manager", "score": 58,
        "summary": ("Below the realistic screening threshold. This role expects program-level scope across "
                    "multiple teams and technical depth in cloud infrastructure, neither of which the resume "
                    "demonstrates. Apply, but treat it as a stretch rather than a core target."),
        "matched": [
            "Cross-functional coordination across departments",
            "Agile ceremony facilitation",
            "Status reporting to senior stakeholders",
        ],
        "missing": [
            "Program-level ownership spanning multiple concurrent teams",
            "Cloud infrastructure familiarity (AWS / GCP named in posting)",
            "Technical background or CS degree",
            "Experience managing engineering managers or team leads",
            "Budget authority",
        ],
        "certs": [
            "AWS Certified Cloud Practitioner, Amazon Web Services — entry-level credential that addresses the named infrastructure gap directly",
        ],
        "actions": [
            "Deprioritize this posting relative to the TPM roles scoring above 70",
            "If pursuing this track, close the cloud-literacy gap before applying to similar roles",
            "Look for program-level scope in your current job to build the missing evidence",
        ],
        "jd": "Technical Program Manager — Beacon Data Systems\n\nDrive complex, multi-team technical programs...",
    },
]

DEMO_PATH = {
    "current_state": ("A senior business analyst with real delivery exposure in healthcare software, but whose "
                      "resume reads as support rather than ownership. The experience is closer to project "
                      "management than the document currently admits."),
    "target_state": ("A Technical Project Manager owning end-to-end delivery of two to three concurrent "
                     "technical projects, with explicit schedule and budget authority, in a healthcare or "
                     "regulated-industry setting."),
    "gap_summary": ("Three gaps repeat across every match: no demonstrated budget or schedule ownership, no Jira "
                    "administration, and no PMP. The first is a framing problem as much as an experience problem "
                    "— the work partially exists and is being described in the wrong register."),
    "milestones": [
        {
            "order": 1,
            "title": "Rewrite the resume around ownership",
            "description": ("Every match flagged the same thing: support language where ownership language belongs. "
                            "This is the cheapest and highest-leverage fix available and it costs nothing but an "
                            "afternoon."),
            "timeline": "7 days",
            "actions": [
                "Rewrite the claims-migration bullet leading with what you owned, not what you supported",
                "Attach a duration and a delivery date to each delivery bullet",
                "Mirror the exact phrase 'cross-functional delivery' from target postings",
                "Add Jira explicitly if you touch it at all",
            ],
            "success_criteria": "Re-score against the Northwind posting and clear 80.",
        },
        {
            "order": 2,
            "title": "Claim schedule ownership in your current role",
            "description": ("The fastest route to the missing evidence is your current job. Ask for the delivery "
                            "schedule on the next workstream rather than waiting for a title change."),
            "timeline": "30 days",
            "actions": [
                "Ask your manager to own the schedule for the next workstream",
                "Volunteer to run the vendor status call",
                "Start keeping a one-page delivery log you can quote in interviews",
            ],
            "success_criteria": "You can name one project where you held the schedule end to end.",
        },
        {
            "order": 3,
            "title": "Close the PMP gap",
            "description": ("PMP appears as preferred on most target postings and required on the higher band. "
                            "Verify hours eligibility first — CAPM is the fallback if you are short."),
            "timeline": "90 days",
            "actions": [
                "Audit your project hours against PMI's eligibility requirement",
                "Register for the exam or, if short on hours, sit CAPM instead",
                "Complete the 35 contact hours of project management education",
            ],
            "success_criteria": "Exam scheduled with a date on the calendar.",
        },
        {
            "order": 4,
            "title": "Concentrate applications on the 70+ band",
            "description": ("Your match history already shows where you convert. Roles scoring under 60 have not "
                            "returned a screen. Stop spending applications there."),
            "timeline": "Ongoing",
            "actions": [
                "Score every posting before applying, not after",
                "Apply only to postings scoring 70 or above unless there is a referral",
                "Track which score bands actually produce screens and revisit monthly",
            ],
            "success_criteria": "Response rate above 20% on the 70+ band.",
        },
        {
            "order": 5,
            "title": "Build the Jira administration credential",
            "description": ("Named as a requirement on the majority of your target postings and currently absent "
                            "from the resume entirely."),
            "timeline": "60 days",
            "actions": [
                "Request Jira project-admin rights on one board at work",
                "Build one automation rule and one dashboard you can describe",
                "Add a concrete Jira line to the skills section",
            ],
            "success_criteria": "You can describe a Jira workflow you configured yourself.",
        },
    ],
    "critical_certs": [
        "Project Management Professional (PMP), Project Management Institute — named on most target postings",
        "PMI Agile Certified Practitioner (PMI-ACP), Project Management Institute — if the target market leans agile delivery",
    ],
    "estimated_timeline": "4-6 months to a competitive TPM application, assuming the resume rewrite happens this week.",
    "biggest_risk": ("Continuing to apply at the current volume without fixing the ownership framing first. "
                     "Every application sent against the old resume burns a company you cannot easily re-approach."),
}


def is_demo() -> bool:
    import streamlit as st
    return st.session_state.get("tester_name") == DEMO_TESTER


def blocked(what: str = "Changes") -> bool:
    """Guard mutations. Returns True (and renders a notice) when in demo mode."""
    import streamlit as st
    if is_demo():
        st.info(f"**{what} are disabled in the demo.** Create a free account to use this on your own search.")
        return True
    return False


def enter_demo():
    import streamlit as st
    st.session_state.user_email = DEMO_EMAIL
    st.session_state.tester_name = DEMO_TESTER
    ensure_seeded()


def _already_seeded(conn) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE tester_name = %s", (DEMO_TESTER,))
    n = cursor.fetchone()[0]
    cursor.close()
    return int(n or 0) > 0


def ensure_seeded():
    """Populate the demo account once. Safe to call on every demo entry."""
    from core.database import (get_connection, create_job, save_profile, save_resume_version,
                               save_match_result, save_critical_path, create_career_path,
                               save_milestone_progress, demo_seeding)
    from core.models import Job, Profile

    conn = get_connection()
    try:
        if _already_seeded(conn):
            return
    finally:
        conn.close()

    with demo_seeding():
        save_profile(
            Profile(
                resume_text=DEMO_RESUME,
                target_role="Technical Project Manager",
                goals=("Move from business analysis into technical project management within a year, "
                       "ideally staying in healthcare. Target band 110-130k, remote or Boston hybrid."),
                resume_filename="jordan_avery_resume.pdf",
            ),
            DEMO_TESTER,
        )
        resume_version_id = save_resume_version(
            DEMO_TESTER, "TPM-focused v3", DEMO_RESUME, "jordan_avery_resume.pdf", set_active=True
        )
        save_resume_version(
            DEMO_TESTER, "General BA v1", DEMO_RESUME, "jordan_avery_ba.pdf", set_active=False
        )

        path_id = create_career_path(
            DEMO_TESTER, "Master Roadmap", "Technical Project Manager", "master",
            "Move from BA into TPM within 12 months.",
        )

        job_ids = {}
        for company, role, status, location, smin, smax, notes in DEMO_JOBS:
            jid = create_job(
                Job(company=company, role=role, status=status, location=location,
                    posted_salary_min=smin, posted_salary_max=smax, notes=notes,
                    jd_text=DEMO_JD if company == "Northwind Health" else None,
                    url="https://example.com/posting", career_path_id=path_id),
                DEMO_TESTER,
            )
            job_ids[company] = jid

        for m in DEMO_MATCHES:
            save_match_result(
                m["score"], m["summary"], m["matched"], m["missing"], m["certs"], m["actions"],
                m["jd"], DEMO_TESTER, job_id=job_ids.get(m["company"]),
                company=m["company"], role=m["role"],
                resume_version_id=resume_version_id, resume_version_label="TPM-focused v3",
                resume_snapshot=DEMO_RESUME,
            )

        save_critical_path(DEMO_TESTER, DEMO_PATH, path_id)
        save_milestone_progress(DEMO_TESTER, 1, "Rewrite the resume around ownership", True, path_id)


def demo_banner():
    """Persistent reminder on every page that this is the shared demo account."""
    import streamlit as st
    if not is_demo():
        return
    st.markdown(
        '<div style="background:rgba(201,168,76,.1);border:1px solid rgba(201,168,76,.35);'
        'border-radius:8px;padding:11px 15px;margin-bottom:18px;font-size:14px;color:#E8E4DA;">'
        '🔍 <strong>Demo account</strong> — fictional candidate, real product output. '
        'Browsing is enabled; edits and new AI runs need a free account.</div>',
        unsafe_allow_html=True
    )
