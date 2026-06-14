from dataclasses import dataclass
from typing import Optional

@dataclass
class Job:
    company: str
    role: str
    status: str
    url: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    notes: Optional[str] = None
    date_applied: Optional[str] = None
    id: Optional[int] = None