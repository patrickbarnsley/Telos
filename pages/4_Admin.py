import streamlit as st
import json
import os
from core.app_styles import apply_theme
from core.database import init_db, get_connection
from dotenv import load_dotenv

load_dotenv()

init_db()
apply_theme()

st.title("🔐 Telos Admin")

def get_admin_password():
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        return os.getenv("ADMIN_PASSWORD", "")

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    st.markdown("### Admin Access")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if password == get_admin_password():
            st.session_state.admin_auth = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

st.success("Logged in as admin.")

tab1, tab2, tab3 = st.tabs(["Testers", "Match Results", "Feedback Summary"])

with tab1:
    st.markdown("### Registered Testers")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT tester_name FROM profile ORDER BY tester_name")
    testers = cursor.fetchall()
    conn.close()

    if not testers:
        st.info("No testers registered yet.")
    else:
        for t in testers:
            st.markdown(f"- {t['tester_name']}")

with tab2:
    st.markdown("### All Match Results")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tester_name, company, role, overall_score, match_summary,
               missing_reqs, recommended_certs, scored_at
        FROM match_results
        ORDER BY scored_at DESC
    """)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if not results:
        st.info("No match results yet.")
    else:
        for r in results:
            with st.expander(f"**{r['tester_name']}** — {r['company']} | {r['role']} | {r['overall_score']}% | {r['scored_at']}"):
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

with tab3:
    st.markdown("### Cert Hallucination Review")
    st.markdown("Review all cert recommendations across all testers to identify patterns or hallucinations.")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tester_name, company, role, recommended_certs, overall_score
        FROM match_results
        ORDER BY scored_at DESC
    """)
    all_results = [dict(row) for row in cursor.fetchall()]
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