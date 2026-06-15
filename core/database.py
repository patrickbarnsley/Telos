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
            date_updated TEXT
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
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guide_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tester_name TEXT NOT NULL DEFAULT 'default',
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
            generated_at TEXT,
            path_json TEXT NOT NULL
        )
    """)
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN tester_name TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE profile ADD COLUMN tester_name TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE match_results ADD COLUMN tester_name TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass
    conn.commit()
    conn.close()

def create_job(job: Job, tester_name: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (tester_name, company, role, status, url, location, salary_min, salary_max, notes, date_applied, date_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'))
    """, (tester_name, job.company, job.role, job.status, job.url, job.location, job.salary_min, job.salary_max, job.notes, job.date_applied))
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

def save_match_result(score, summary, matched, missing, certs, actions, jd_text, tester_name: str, job_id=None, company=None, role=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_results (tester_name, job_id, company, role, scored_at, overall_score, match_summary, matched_reqs, missing_reqs, recommended_certs, recommended_actions, jd_text)
        VALUES (?, ?, ?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?)
    """, (tester_name, job_id, company, role, score, summary,
          json.dumps(matched), json.dumps(missing),
          json.dumps(certs), json.dumps(actions), jd_text))
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

def save_milestone_progress(tester_name: str, milestone_order: int, milestone_title: str, completed: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM guide_progress WHERE tester_name = ? AND milestone_order = ?", (tester_name, milestone_order))
    cursor.execute("""
        INSERT INTO guide_progress (tester_name, milestone_order, milestone_title, completed, completed_at)
        VALUES (?, ?, ?, ?, CASE WHEN ? = 1 THEN date('now') ELSE NULL END)
    """, (tester_name, milestone_order, milestone_title, int(completed), int(completed)))
    conn.commit()
    conn.close()

def get_milestone_progress(tester_name: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT milestone_order, completed FROM guide_progress WHERE tester_name = ?", (tester_name,))
    rows = cursor.fetchall()
    conn.close()
    return {row["milestone_order"]: bool(row["completed"]) for row in rows}

def save_critical_path(tester_name: str, path: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM critical_path WHERE tester_name = ?", (tester_name,))
    cursor.execute("""
        INSERT INTO critical_path (tester_name, generated_at, path_json)
        VALUES (?, date('now'), ?)
    """, (tester_name, json.dumps(path)))
    conn.commit()
    conn.close()

def get_critical_path(tester_name: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT path_json, generated_at FROM critical_path WHERE tester_name = ? LIMIT 1", (tester_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"path": json.loads(row["path_json"]), "generated_at": row["generated_at"]}
    return None