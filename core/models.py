from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    company: str
    role: str
    status: str
    url: Optional[str] = None
    location: Optional[str] = None
    # Legacy single-range fields, kept for backward compatibility.
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    # Split salary ranges.
    posted_salary_min: Optional[int] = None
    posted_salary_max: Optional[int] = None
    requested_salary_min: Optional[int] = None
    requested_salary_max: Optional[int] = None
    notes: Optional[str] = None
    jd_text: Optional[str] = None
    date_applied: Optional[str] = None
    career_path_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Profile:
    resume_text: str
    target_role: str
    goals: Optional[str] = None
    resume_filename: Optional[str] = None
    id: Optional[int] = None