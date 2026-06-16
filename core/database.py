import sqlite3
import json
from typing import Optional
from core.models import Job, Profile

DB_PATH = "telos.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            resume_snapshot TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guide_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tester_name TEXT NOT NULL,
            career_path_id INTEGER,
            generated_at TEXT,
            path_json TEXT NOT NULL
        )
    """)
    # Migrations
    migrations = [
        "ALTER TABLE jobs ADD COLUMN tester_name TEXT NOT NULL DEFAULT 'default'",
        "ALTER TABLE jobs ADD COLUMN outcome_date TEXT",
        "ALTER TABLE jobs ADD COLUMN match_predictive TEXT",
        "ALTER TABLE jobs ADD COLUMN career_path_id INTEGER",
        "ALTER TABLE profile ADD COLUMN tester_name TEXT NOT NULL DEFAULT 'default'",
        "ALTER TABLE match_results ADD COLUMN tester_name TEXT NOT NULL DEFAULT 'default'",
        "ALTER TABLE match_results ADD COLUMN resume_version_id INTEGER",
        "ALTER TABLE match_results ADD COLUMN resume_version_label TEXT",
        "ALTER TABLE match_results ADD COLUMN resume_snapshot TEXT",
    ]
    for migration in migrations:
        try:
            cursor.execute(migration)
        except Exception:
            pass
    conn.commit()
    conn.close()

def create_job(job: Job, tester_name: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (tester_name, company, role, status, url, location, salary_min, salary_max, notes, date_applied, date_updated, career_path_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'), ?)
    """, (tester_name, job.company, job.role, job.status, job.url, job.location, job.salary_min, job.salary_max, job.notes, job.date_applied, job.career_path_id))
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id

def get_jobs(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE tester_name = ? ORDER BY date_updated DESC", (tester_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_job(job_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_job(job_id: int, fields: dict):
    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join([f"{k} = ?" for k in fields])
    set_clause += ", date_updated = date('now')"
    values = list(fields.values())
    values.append(job_id)
    cursor.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

def delete_job(job_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

def save_profile(profile: Profile, tester_name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profile WHERE tester_name = ?", (tester_name,))
    cursor.execute("""
        INSERT INTO profile (tester_name, resume_text, resume_filename, target_role, goals, date_updated)
        VALUES (?, ?, ?, ?, ?, date('now'))
    """, (tester_name, profile.resume_text, profile.resume_filename, profile.target_role, profile.goals))
    conn.commit()
    conn.close()

def get_profile(tester_name: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profile WHERE tester_name = ? LIMIT 1", (tester_name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_resume_version(tester_name: str, version_label: str, resume_text: str, resume_filename: str, set_active: bool = False) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    if set_active:
        cursor.execute("UPDATE resume_versions SET is_active = 0 WHERE tester_name = ?", (tester_name,))
    cursor.execute("""
        INSERT INTO resume_versions (tester_name, version_label, resume_text, resume_filename, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, date('now'))
    """, (tester_name, version_label, resume_text, resume_filename, int(set_active)))
    conn.commit()
    version_id = cursor.lastrowid
    conn.close()
    return version_id

def get_resume_versions(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE tester_name = ? AND deleted_at IS NULL ORDER BY created_at DESC", (tester_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def set_active_resume(tester_name: str, version_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE resume_versions SET is_active = 0 WHERE tester_name = ?", (tester_name,))
    cursor.execute("UPDATE resume_versions SET is_active = 1 WHERE id = ? AND tester_name = ?", (version_id, tester_name))
    conn.commit()
    conn.close()

def delete_resume_version(version_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE resume_versions SET deleted_at = date('now'), is_active = 0 WHERE id = ?", (version_id,))
    conn.commit()
    conn.close()

def get_active_resume(tester_name: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resume_versions WHERE tester_name = ? AND is_active = 1 AND deleted_at IS NULL LIMIT 1", (tester_name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_match_result(score, summary, matched, missing, certs, actions, jd_text, tester_name: str, job_id=None, company=None, role=None, resume_version_id=None, resume_version_label=None, resume_snapshot=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_results (tester_name, job_id, company, role, scored_at, overall_score, match_summary, matched_reqs, missing_reqs, recommended_certs, recommended_actions, jd_text, resume_version_id, resume_version_label, resume_snapshot)
        VALUES (?, ?, ?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tester_name, job_id, company, role, score, summary,
          json.dumps(matched), json.dumps(missing),
          json.dumps(certs), json.dumps(actions), jd_text,
          resume_version_id, resume_version_label, resume_snapshot))
    conn.commit()
    conn.close()

def get_all_match_results(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match_results WHERE tester_name = ? ORDER BY scored_at DESC", (tester_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_match_results(job_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match_results WHERE job_id = ? ORDER BY scored_at DESC", (job_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_company_stats(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
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
        WHERE j.tester_name = ?
        GROUP BY j.company
        ORDER BY last_activity DESC
    """, (tester_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_milestone_progress(tester_name: str, milestone_order: int, milestone_title: str, completed: bool, career_path_id: int = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guide_progress WHERE tester_name = ? AND milestone_order = ? AND career_path_id IS ?", (tester_name, milestone_order, career_path_id))
    cursor.execute("""
        INSERT INTO guide_progress (tester_name, career_path_id, milestone_order, milestone_title, completed, completed_at)
        VALUES (?, ?, ?, ?, ?, CASE WHEN ? = 1 THEN date('now') ELSE NULL END)
    """, (tester_name, career_path_id, milestone_order, milestone_title, int(completed), int(completed)))
    conn.commit()
    conn.close()

def get_milestone_progress(tester_name: str, career_path_id: int = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT milestone_order, completed FROM guide_progress WHERE tester_name = ? AND career_path_id IS ?", (tester_name, career_path_id))
    rows = cursor.fetchall()
    conn.close()
    return {row["milestone_order"]: bool(row["completed"]) for row in rows}

def save_critical_path(tester_name: str, path: dict, career_path_id: int = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM critical_path WHERE tester_name = ? AND career_path_id IS ?", (tester_name, career_path_id))
    cursor.execute("""
        INSERT INTO critical_path (tester_name, career_path_id, generated_at, path_json)
        VALUES (?, ?, date('now'), ?)
    """, (tester_name, career_path_id, json.dumps(path)))
    conn.commit()
    conn.close()

def get_critical_path(tester_name: str, career_path_id: int = None) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT path_json, generated_at FROM critical_path WHERE tester_name = ? AND career_path_id IS ? LIMIT 1", (tester_name, career_path_id))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"path": json.loads(row["path_json"]), "generated_at": row["generated_at"]}
    return None

def create_career_path(tester_name: str, path_name: str, target_role: str, path_type: str = 'sub', goals: str = None, parent_path_id: int = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO career_paths (tester_name, path_name, path_type, target_role, goals, parent_path_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, date('now'))
    """, (tester_name, path_name, path_type, target_role, goals, parent_path_id))
    conn.commit()
    path_id = cursor.lastrowid
    conn.close()
    return path_id

def get_career_paths(tester_name: str) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM career_paths WHERE tester_name = ? ORDER BY path_type DESC, created_at ASC", (tester_name,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_career_path(path_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM career_paths WHERE id = ?", (path_id,))
    conn.commit()
    conn.close()

def delete_match_result(match_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM match_results WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()