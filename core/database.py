import sqlite3
from typing import Optional
from core.models import Job

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
    fields["date_updated"] = "date('now')"
    set_clause = ", ".join([f"{k} = ?" for k in fields if k != "date_updated"])
    set_clause += ", date_updated = date('now')"
    values = [v for k, v in fields.items() if k != "date_updated"]
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