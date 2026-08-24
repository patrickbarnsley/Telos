import streamlit as st
import json
import os
import hmac
import psycopg2.extras
import pandas as pd
from core.app_styles import apply_theme
from core.auth import require_login
from core.plans import is_owner
from core.database import get_connection, get_all_outcome_correlations, get_usage_over_time
from dotenv import load_dotenv

load_dotenv()

apply_theme()

# --- Access control -------------------------------------------------------
# Three gates, in order. This page exposes every user's email, target role,
# match history and usage, so it is not defended by a shared password alone.
#
#   1. Signed in to Telos at all. Previously absent, which left the page
#      reachable by anyone who knew the URL.
#   2. Signed in as an owner. Membership comes from OWNER_EMAILS, so a correct
#      password from a non-owner account is still refused. The demo account can
#      never satisfy this.
#   3. The admin password, as a second factor, compared in constant time and
#      rate limited.

require_login()

_tester = st.session_state.get("tester_name", "")

if not is_owner(_tester):
    # Deliberately the same message a signed-out visitor would see. Confirming
    # that an admin page exists here tells an attacker where to spend effort.
    st.title("Page not found")
    st.markdown("This page does not exist, or you do not have access to it.")
    st.page_link("app.py", label="Back to Telos")
    st.stop()

st.title("Telos Admin")


def get_admin_password():
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return os.getenv("ADMIN_PASSWORD", "")


if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False
if "admin_attempts" not in st.session_state:
    st.session_state.admin_attempts = 0

if not st.session_state.admin_auth:
    st.markdown("### Admin access")
    st.caption(f"Signed in as {_tester}")

    if st.session_state.admin_attempts >= 5:
        st.error("Too many failed attempts. Reload the page to try again.")
        st.stop()

    password = st.text_input("Password", type="password")
    if st.button("Log in"):
        expected = get_admin_password()
        # hmac.compare_digest avoids leaking the password length or prefix
        # through response timing.
        if expected and hmac.compare_digest(password, expected):
            st.session_state.admin_auth = True
            st.session_state.admin_attempts = 0
            st.rerun()
        else:
            st.session_state.admin_attempts += 1
            remaining = 5 - st.session_state.admin_attempts
            st.error(f"Incorrect password. {remaining} attempt(s) remaining.")
    st.stop()

st.success(f"Admin session active - {_tester}")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Testers", "Usage", "Match Results", "Cert Hallucinations", "Guide Critical Paths", "Outcome Tracking"])

with tab1:
    st.markdown("### Registered Testers")
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT DISTINCT tester_name FROM profile ORDER BY tester_name")
    testers = cursor.fetchall()
    cursor.close()
    conn.close()

    if not testers:
        st.info("No testers registered yet.")
    else:
        for t in testers:
            st.markdown(f"- {t['tester_name']}")

with tab2:
    st.markdown("### Usage Per Tester")

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT
            p.tester_name,
            p.target_role,
            p.date_updated as profile_updated,
            COUNT(DISTINCT j.id) as total_jobs,
            COUNT(DISTINCT m.id) as total_matches,
            COUNT(DISTINCT cp.id) as critical_paths_generated,
            COUNT(DISTINCT rv.id) as resume_versions,
            MAX(m.scored_at) as last_match_date,
            MAX(j.date_updated) as last_job_update
        FROM profile p
        LEFT JOIN jobs j ON j.tester_name = p.tester_name
        LEFT JOIN match_results m ON m.tester_name = p.tester_name
        LEFT JOIN critical_path cp ON cp.tester_name = p.tester_name
        LEFT JOIN resume_versions rv ON rv.tester_name = p.tester_name AND rv.deleted_at IS NULL
        GROUP BY p.tester_name, p.target_role, p.date_updated
        ORDER BY last_match_date DESC NULLS LAST
    """)
    usage = cursor.fetchall()
    cursor.close()
    conn.close()

    if not usage:
        st.info("No usage data yet.")
    else:
        for u in usage:
            with st.expander(f"**{u['tester_name']}** - {u['target_role'] or 'No target role set'}"):
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Jobs Logged", u['total_jobs'])
                col2.metric("Match Scores Run", u['total_matches'])
                col3.metric("Critical Paths", u['critical_paths_generated'])
                col4.metric("Resume Versions", u['resume_versions'])
                st.markdown(f"**Last match scored:** {u['last_match_date'] or 'Never'}")
                st.markdown(f"**Last job updated:** {u['last_job_update'] or 'Never'}")
                st.markdown(f"**Profile set up:** {u['profile_updated'] or 'Unknown'}")

    st.markdown("---")
    st.markdown("### Usage Over Time")

    usage_data = get_usage_over_time()

    if not usage_data:
        st.info("No activity data yet.")
    else:
        df = pd.DataFrame(usage_data)
        df["date"] = pd.to_datetime(df["date"])

        all_testers = ["All"] + sorted(df["tester_name"].unique().tolist())
        selected_tester = st.selectbox("Filter by tester", all_testers)

        if selected_tester != "All":
            df = df[df["tester_name"] == selected_tester]

        activity_filter = st.multiselect(
            "Activity types",
            ["match", "job", "critical_path"],
            default=["match", "job", "critical_path"],
            format_func=lambda x: {"match": "Match Scores", "job": "Jobs Logged", "critical_path": "Critical Paths"}[x]
        )

        df = df[df["activity_type"].isin(activity_filter)]

        if df.empty:
            st.info("No data for selected filters.")
        else:
            pivot = df.pivot_table(index="date", columns="activity_type", values="count", aggfunc="sum").fillna(0)
            pivot.columns = [{"match": "Match Scores", "job": "Jobs Logged", "critical_path": "Critical Paths"}.get(c, c) for c in pivot.columns]
            st.line_chart(pivot)

            st.markdown("#### Daily Breakdown")
            display_df = df.copy()
            display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
            display_df["activity_type"] = display_df["activity_type"].map({"match": "Match Scores", "job": "Jobs Logged", "critical_path": "Critical Paths"})
            display_df = display_df.rename(columns={"tester_name": "Tester", "date": "Date", "activity_type": "Activity", "count": "Count"})
            st.dataframe(display_df[["Date", "Tester", "Activity", "Count"]].sort_values("Date", ascending=False), use_container_width=True)

with tab3:
    st.markdown("### All Match Results")
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT tester_name, company, role, overall_score, match_summary,
               missing_reqs, recommended_certs, scored_at
        FROM match_results
        ORDER BY scored_at DESC
    """)
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not results:
        st.info("No match results yet.")
    else:
        for r in results:
            with st.expander(f"**{r['tester_name']}** - {r['company']} | {r['role']} | {r['overall_score']}% | {r['scored_at']}"):
                st.markdown(f"**Summary:** {r['match_summary']}")

                missing = json.loads(r['missing_reqs']) if r['missing_reqs'] else []
                certs = json.loads(r['recommended_certs']) if r['recommended_certs'] else []

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Gaps Identified:**")
                    for item in missing:
                        st.markdown(f"- {item}")
                with col2:
                    st.markdown("**Certs Recommended:**")
                    for cert in certs:
                        st.markdown(f"- {cert}")

with tab4:
    st.markdown("### Cert Hallucination Review")
    st.markdown("Review all cert recommendations across all testers to identify patterns or hallucinations.")

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT tester_name, company, role, recommended_certs, overall_score
        FROM match_results
        ORDER BY scored_at DESC
    """)
    all_results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    all_certs = []
    for r in all_results:
        certs = json.loads(r['recommended_certs']) if r['recommended_certs'] else []
        for cert in certs:
            all_certs.append({
                "tester": r['tester_name'],
                "company": r['company'],
                "role": r['role'],
                "cert": cert
            })

    if not all_certs:
        st.info("No cert recommendations yet.")
    else:
        st.markdown(f"**Total cert recommendations across all testers: {len(all_certs)}**")
        for c in all_certs:
            st.markdown(f"- **{c['tester']}** applying to {c['company']} ({c['role']}): _{c['cert']}_")

with tab5:
    st.markdown("### Guide Critical Paths")
    st.markdown("Review all generated critical paths and cert recommendations from Guide.")

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT tester_name, generated_at, path_json
        FROM critical_path
        ORDER BY generated_at DESC
    """)
    paths = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if not paths:
        st.info("No critical paths generated yet.")
    else:
        for p in paths:
            path = json.loads(p['path_json'])
            certs = path.get('critical_certs', [])
            milestones = path.get('milestones', [])

            with st.expander(f"**{p['tester_name']}** - Generated: {p['generated_at']}"):
                st.markdown(f"**Current State:** {path.get('current_state', '')}")
                st.markdown(f"**Target State:** {path.get('target_state', '')}")
                st.markdown(f"**Estimated Timeline:** {path.get('estimated_timeline', '')}")
                st.markdown(f"**Biggest Risk:** {path.get('biggest_risk', '')}")

                st.markdown("**Critical Certs Recommended:**")
                if certs:
                    for cert in certs:
                        st.markdown(f"- {cert}")
                else:
                    st.markdown("_None recommended_")

                st.markdown("**Milestones:**")
                for m in milestones:
                    st.markdown(f"- Milestone {m.get('order')}: {m.get('title')} ({m.get('timeline')})")

with tab6:
    st.markdown("### Outcome Tracking & Score Correlation")
    st.markdown("Jobs that reached interview, offer, or rejection, correlated with their match scores.")

    outcomes = get_all_outcome_correlations()

    if not outcomes:
        st.info("No outcome data yet. Jobs need to be moved to Interview, Offer, or Rejected status to appear here.")
    else:
        offers = [o for o in outcomes if o["status"] == "offer"]
        interviews = [o for o in outcomes if o["status"] == "interview"]
        rejections = [o for o in outcomes if o["status"] == "rejected"]

        col1, col2, col3 = st.columns(3)
        col1.metric("Offers", len(offers))
        col2.metric("Interviews", len(interviews))
        col3.metric("Rejections", len(rejections))

        st.markdown("---")

        if offers:
            st.markdown("### 🎉 Offers")
            for o in offers:
                score = o["best_match_score"]
                predictive = o["match_predictive"] or "Not rated"
                with st.expander(f"**{o['tester_name']}** - {o['company']} | {o['role']} | Score: {score or 'N/A'}%"):
                    col1, col2 = st.columns(2)
                    col1.markdown(f"**Outcome Date:** {o['outcome_date'] or 'Not set'}")
                    col1.markdown(f"**Match Runs:** {o['total_match_runs']}")
                    col2.markdown(f"**Best Score:** {score or 'N/A'}%")
                    col2.markdown(f"**Score felt predictive:** {predictive}")

        if interviews:
            st.markdown("### 📞 Interviews")
            for o in interviews:
                score = o["best_match_score"]
                predictive = o["match_predictive"] or "Not rated"
                with st.expander(f"**{o['tester_name']}** - {o['company']} | {o['role']} | Score: {score or 'N/A'}%"):
                    col1, col2 = st.columns(2)
                    col1.markdown(f"**Applied:** {o['date_applied'] or 'N/A'}")
                    col1.markdown(f"**Match Runs:** {o['total_match_runs']}")
                    col2.markdown(f"**Best Score:** {score or 'N/A'}%")
                    col2.markdown(f"**Score felt predictive:** {predictive}")

        if rejections:
            st.markdown("### ❌ Rejections")
            for o in rejections:
                score = o["best_match_score"]
                predictive = o["match_predictive"] or "Not rated"
                with st.expander(f"**{o['tester_name']}** - {o['company']} | {o['role']} | Score: {score or 'N/A'}%"):
                    col1, col2 = st.columns(2)
                    col1.markdown(f"**Outcome Date:** {o['outcome_date'] or 'Not set'}")
                    col1.markdown(f"**Match Runs:** {o['total_match_runs']}")
                    col2.markdown(f"**Best Score:** {score or 'N/A'}%")
                    col2.markdown(f"**Score felt predictive:** {predictive}")

        st.markdown("---")
        st.markdown("### 📊 Score Distribution by Outcome")

        if any(o["best_match_score"] for o in outcomes):
            offer_scores = [o["best_match_score"] for o in offers if o["best_match_score"]]
            interview_scores = [o["best_match_score"] for o in interviews if o["best_match_score"]]
            rejection_scores = [o["best_match_score"] for o in rejections if o["best_match_score"]]

            if offer_scores:
                st.markdown(f"**Avg score for offers:** {round(sum(offer_scores)/len(offer_scores), 1)}%")
            if interview_scores:
                st.markdown(f"**Avg score for interviews:** {round(sum(interview_scores)/len(interview_scores), 1)}%")
            if rejection_scores:
                st.markdown(f"**Avg score for rejections:** {round(sum(rejection_scores)/len(rejection_scores), 1)}%")