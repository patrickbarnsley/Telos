import psycopg2
import psycopg2.extras
import json
import os
from typing import Optional
from dotenv import load_dotenv
from core.models import Job, Profile

load_dotenv()

def get_db_url():
    try:
        import streamlit as st
        return st.secrets["DATABASE_URL"]
    except Exception:
        return os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(get_db_url(), connect_timeout=10)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL DEFAULT 'default',
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'applied',
            url TEXT,
            location TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            notes TEXT,
            date_applied TEXT,
            date_updated TEXT,
            outcome_date TEXT,
            match_predictive TEXT,
            career_path_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL DEFAULT 'default',
            resume_text TEXT NOT NULL,
            resume_filename TEXT,
            target_role TEXT NOT NULL,
            goals TEXT,
            date_updated TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_versions (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL,
            version_label TEXT NOT NULL,
            resume_text TEXT NOT NULL,
            resume_filename TEXT,
            is_active INTEGER DEFAULT 0,
            created_at TEXT,
            deleted_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS career_paths (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL,
            path_name TEXT NOT NULL,
            path_type TEXT NOT NULL DEFAULT 'sub',
            target_role TEXT NOT NULL,
            goals TEXT,
            parent_path_id INTEGER,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS match_results (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL DEFAULT 'default',
            job_id INTEGER,
            company TEXT,
            role TEXT,
            scored_at TEXT,
            overall_score INTEGER,
            match_summary TEXT,
            matched_reqs TEXT,
            missing_reqs TEXT,
            recommended_certs TEXT,
            recommended_actions TEXT,
            jd_text TEXT,
            resume_version_id INTEGER,
            resume_version_label TEXT,
            resume_snapshot TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guide_progress (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL DEFAULT 'default',
            career_path_id INTEGER,
            milestone_order INTEGER,
            milestone_title TEXT,
            completed INTEGER DEFAULT 0,
            completed_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS critical_path (
            id SERIAL PRIMARY KEY,
            tester_name TEXT NOT NULL,
            career_path_id INTEGER,
            generated_at TEXT,
            path_json TEXT NOT NULL
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

def create_job(job: Job, tester_name: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (tester_name, company, role, status, url, location, salary_min, salary_max, notes, date_applied, date_updated, career_path_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE::text, %s)
        RETURNING id
    """, (tester_name, job.company, job.role, job.status, job.url, job.location, job.salary_min, job.salary_max, job.notes, job.date_applied, job.career_path_id))
    job_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return job_id

def get_jobs(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM jobs WHERE tester_name = %s ORDER BY date_updated DESC NULLS LAST", (tester_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def get_job(job_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(row) if row else None

def update_job(job_id: int, fields: dict):
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{k} = %s" for k in fields])
    set_clause += ", date_updated = CURRENT_DATE::text"
    values = list(fields.values())
    values.append(job_id)
    cursor.execute(f"UPDATE jobs SET {set_clause} WHERE id = %s", values)
    conn.commit()
    cursor.close()
    conn.close()

def delete_job(job_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    conn.commit()
    cursor.close()
    conn.close()

def save_profile(profile: Profile, tester_name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profile WHERE tester_name = %s", (tester_name,))
    cursor.execute("""
        INSERT INTO profile (tester_name, resume_text, resume_filename, target_role, goals, date_updated)
        VALUES (%s, %s, %s, %s, %s, CURRENT_DATE::text)
    """, (tester_name, profile.resume_text, profile.resume_filename, profile.target_role, profile.goals))
    conn.commit()
    cursor.close()
    conn.close()

def get_profile(tester_name: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM profile WHERE tester_name = %s LIMIT 1", (tester_name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(row) if row else None

def save_resume_version(tester_name: str, version_label: str, resume_text: str, resume_filename: str, set_active: bool = False) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    if set_active:
        cursor.execute("UPDATE resume_versions SET is_active = 0 WHERE tester_name = %s", (tester_name,))
    cursor.execute("""
        INSERT INTO resume_versions (tester_name, version_label, resume_text, resume_filename, is_active, created_at)
        VALUES (%s, %s, %s, %s, %s, CURRENT_DATE::text)
        RETURNING id
    """, (tester_name, version_label, resume_text, resume_filename, int(set_active)))
    version_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return version_id

def get_resume_versions(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM resume_versions WHERE tester_name = %s AND deleted_at IS NULL ORDER BY created_at DESC", (tester_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def set_active_resume(tester_name: str, version_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE resume_versions SET is_active = 0 WHERE tester_name = %s", (tester_name,))
    cursor.execute("UPDATE resume_versions SET is_active = 1 WHERE id = %s AND tester_name = %s", (version_id, tester_name))
    conn.commit()
    cursor.close()
    conn.close()

def delete_resume_version(version_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE resume_versions SET deleted_at = CURRENT_DATE::text, is_active = 0 WHERE id = %s", (version_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_active_resume(tester_name: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM resume_versions WHERE tester_name = %s AND is_active = 1 AND deleted_at IS NULL LIMIT 1", (tester_name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(row) if row else None

def save_match_result(score, summary, matched, missing, certs, actions, jd_text, tester_name: str, job_id=None, company=None, role=None, resume_version_id=None, resume_version_label=None, resume_snapshot=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_results (tester_name, job_id, company, role, scored_at, overall_score, match_summary, matched_reqs, missing_reqs, recommended_certs, recommended_actions, jd_text, resume_version_id, resume_version_label, resume_snapshot)
        VALUES (%s, %s, %s, %s, CURRENT_DATE::text, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (tester_name, job_id, company, role, score, summary,
          json.dumps(matched), json.dumps(missing),
          json.dumps(certs), json.dumps(actions), jd_text,
          resume_version_id, resume_version_label, resume_snapshot))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_match_results(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM match_results WHERE tester_name = %s ORDER BY scored_at DESC", (tester_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def get_match_results(job_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM match_results WHERE job_id = %s ORDER BY scored_at DESC", (job_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def delete_match_result(match_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM match_results WHERE id = %s", (match_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_company_stats(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT
            j.company,
            COUNT(DISTINCT j.id) as total_applications,
            COUNT(m.id) as total_match_runs,
            MAX(m.overall_score) as best_score,
            MIN(j.date_applied) as first_applied,
            MAX(j.date_updated) as last_activity
        FROM jobs j
        LEFT JOIN match_results m ON j.id = m.job_id
        WHERE j.tester_name = %s
        GROUP BY j.company
        ORDER BY last_activity DESC NULLS LAST
    """, (tester_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def save_milestone_progress(tester_name: str, milestone_order: int, milestone_title: str, completed: bool, career_path_id: int = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guide_progress WHERE tester_name = %s AND milestone_order = %s AND career_path_id IS NOT DISTINCT FROM %s", (tester_name, milestone_order, career_path_id))
    cursor.execute("""
        INSERT INTO guide_progress (tester_name, career_path_id, milestone_order, milestone_title, completed, completed_at)
        VALUES (%s, %s, %s, %s, %s, CASE WHEN %s = 1 THEN CURRENT_DATE::text ELSE NULL END)
    """, (tester_name, career_path_id, milestone_order, milestone_title, int(completed), int(completed)))
    conn.commit()
    cursor.close()
    conn.close()

def get_milestone_progress(tester_name: str, career_path_id: int = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT milestone_order, completed FROM guide_progress WHERE tester_name = %s AND career_path_id IS NOT DISTINCT FROM %s", (tester_name, career_path_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {row["milestone_order"]: bool(row["completed"]) for row in rows}

def save_critical_path(tester_name: str, path: dict, career_path_id: int = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM critical_path WHERE tester_name = %s AND career_path_id IS NOT DISTINCT FROM %s", (tester_name, career_path_id))
    cursor.execute("""
        INSERT INTO critical_path (tester_name, career_path_id, generated_at, path_json)
        VALUES (%s, %s, CURRENT_DATE::text, %s)
    """, (tester_name, career_path_id, json.dumps(path)))
    conn.commit()
    cursor.close()
    conn.close()

def get_critical_path(tester_name: str, career_path_id: int = None) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT path_json, generated_at FROM critical_path WHERE tester_name = %s AND career_path_id IS NOT DISTINCT FROM %s LIMIT 1", (tester_name, career_path_id))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {"path": json.loads(row["path_json"]), "generated_at": row["generated_at"]}
    return None

def create_career_path(tester_name: str, path_name: str, target_role: str, path_type: str = 'sub', goals: str = None, parent_path_id: int = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO career_paths (tester_name, path_name, path_type, target_role, goals, parent_path_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_DATE::text)
        RETURNING id
    """, (tester_name, path_name, path_type, target_role, goals, parent_path_id))
    path_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return path_id

def get_career_paths(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM career_paths WHERE tester_name = %s ORDER BY path_type DESC, created_at ASC", (tester_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def delete_career_path(path_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM career_paths WHERE id = %s", (path_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_guide_data(tester_name: str, career_path_id: int = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM profile WHERE tester_name = %s LIMIT 1", (tester_name,))
    profile = cursor.fetchone()

    cursor.execute("SELECT * FROM match_results WHERE tester_name = %s ORDER BY scored_at DESC", (tester_name,))
    match_history = cursor.fetchall()

    cursor.execute("SELECT * FROM career_paths WHERE tester_name = %s ORDER BY path_type DESC, created_at ASC", (tester_name,))
    career_paths = cursor.fetchall()

    cursor.execute("SELECT * FROM resume_versions WHERE tester_name = %s AND deleted_at IS NULL ORDER BY created_at DESC", (tester_name,))
    resume_versions = cursor.fetchall()

    cursor.execute("SELECT path_json, generated_at FROM critical_path WHERE tester_name = %s AND career_path_id IS NOT DISTINCT FROM %s LIMIT 1", (tester_name, career_path_id))
    critical_path = cursor.fetchone()

    cursor.execute("SELECT milestone_order, completed FROM guide_progress WHERE tester_name = %s AND career_path_id IS NOT DISTINCT FROM %s", (tester_name, career_path_id))
    progress = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "profile": dict(profile) if profile else None,
        "match_history": [dict(r) for r in match_history],
        "career_paths": [dict(r) for r in career_paths],
        "resume_versions": [dict(r) for r in resume_versions],
        "critical_path": {"path": json.loads(critical_path["path_json"]), "generated_at": critical_path["generated_at"]} if critical_path else None,
        "progress": {row["milestone_order"]: bool(row["completed"]) for row in progress}
    }

def get_match_page_data(tester_name: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM profile WHERE tester_name = %s LIMIT 1", (tester_name,))
    profile = cursor.fetchone()

    cursor.execute("SELECT * FROM jobs WHERE tester_name = %s ORDER BY date_updated DESC NULLS LAST", (tester_name,))
    jobs = cursor.fetchall()

    cursor.execute("SELECT * FROM resume_versions WHERE tester_name = %s AND deleted_at IS NULL ORDER BY created_at DESC", (tester_name,))
    resume_versions = cursor.fetchall()

    cursor.execute("SELECT * FROM match_results WHERE tester_name = %s ORDER BY scored_at DESC", (tester_name,))
    match_results = cursor.fetchall()

    cursor.close()
    conn.close()

    return {
        "profile": dict(profile) if profile else None,
        "jobs": [dict(r) for r in jobs],
        "resume_versions": [dict(r) for r in resume_versions],
        "match_results": [dict(r) for r in match_results]
    }

def get_outcome_correlation(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT 
            j.company,
            j.role,
            j.status,
            j.outcome_date,
            j.match_predictive,
            MAX(m.overall_score) as best_match_score,
            COUNT(m.id) as total_match_runs,
            j.date_applied
        FROM jobs j
        LEFT JOIN match_results m ON j.id = m.job_id
        WHERE j.tester_name = %s
        AND j.status IN ('offer', 'rejected', 'interview')
        GROUP BY j.id, j.company, j.role, j.status, j.outcome_date, j.match_predictive, j.date_applied
        ORDER BY j.outcome_date DESC NULLS LAST
    """, (tester_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def get_all_outcome_correlations() -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT 
            j.tester_name,
            j.company,
            j.role,
            j.status,
            j.outcome_date,
            j.match_predictive,
            MAX(m.overall_score) as best_match_score,
            COUNT(m.id) as total_match_runs,
            j.date_applied
        FROM jobs j
        LEFT JOIN match_results m ON j.id = m.job_id
        WHERE j.status IN ('offer', 'rejected', 'interview')
        GROUP BY j.id, j.tester_name, j.company, j.role, j.status, j.outcome_date, j.match_predictive, j.date_applied
        ORDER BY j.outcome_date DESC NULLS LAST
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]

def get_usage_over_time() -> list:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT 
            scored_at as date,
            tester_name,
            'match' as activity_type,
            COUNT(*) as count
        FROM match_results
        WHERE scored_at IS NOT NULL
        GROUP BY scored_at, tester_name
        UNION ALL
        SELECT 
            date_updated as date,
            tester_name,
            'job' as activity_type,
            COUNT(*) as count
        FROM jobs
        WHERE date_updated IS NOT NULL
        GROUP BY date_updated, tester_name
        UNION ALL
        SELECT 
            generated_at as date,
            tester_name,
            'critical_path' as activity_type,
            COUNT(*) as count
        FROM critical_path
        WHERE generated_at IS NOT NULL
        GROUP BY generated_at, tester_name
        ORDER BY date DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]