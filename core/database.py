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
    conn.commit()
    conn.close()

def create_job(job: Job) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (company, role, status, url, location, salary_min, salary_max, notes, date_applied, date_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'))
    """, (job.company, job.role, job.status, job.url, job.location, job.salary_min, job.salary_max, job.notes, job.date_applied))
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    return job_id

def get_jobs() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY date_updated DESC")
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

def save_profile(profile: Profile):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profile")
    cursor.execute("""
        INSERT INTO profile (resume_text, resume_filename, target_role, goals, date_updated)
        VALUES (?, ?, ?, ?, date('now'))
    """, (profile.resume_text, profile.resume_filename, profile.target_role, profile.goals))
    conn.commit()
    conn.close()

def get_profile() -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profile LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_match_result(score, summary, matched, missing, certs, actions, jd_text, job_id=None, company=None, role=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_results (job_id, company, role, scored_at, overall_score, match_summary, matched_reqs, missing_reqs, recommended_certs, recommended_actions, jd_text)
        VALUES (?, ?, ?, date('now'), ?, ?, ?, ?, ?, ?, ?)
    """, (job_id, company, role, score, summary,
          json.dumps(matched), json.dumps(missing),
          json.dumps(certs), json.dumps(actions), jd_text))
    conn.commit()
    conn.close()

def get_all_match_results() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM match_results ORDER BY scored_at DESC")
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