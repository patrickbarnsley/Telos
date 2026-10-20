"""The Track pillar. Every handler is scoped by the cookie account."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import current_account, fail

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobIn(BaseModel):
    company: str
    role: str
    status: str = "applied"
    url: str | None = None
    location: str | None = None
    posted_salary_min: int | None = None
    posted_salary_max: int | None = None
    requested_salary_min: int | None = None
    requested_salary_max: int | None = None
    notes: str | None = None
    jd_text: str | None = None
    date_applied: str | None = None
    career_path_id: int | None = None


class JobPatch(BaseModel):
    company: str | None = None
    role: str | None = None
    status: str | None = None
    url: str | None = None
    location: str | None = None
    posted_salary_min: int | None = None
    posted_salary_max: int | None = None
    requested_salary_min: int | None = None
    requested_salary_max: int | None = None
    notes: str | None = None
    jd_text: str | None = None
    date_applied: str | None = None
    career_path_id: int | None = None


@router.get("/stats")
def stats(account: str = Depends(current_account)):
    """Per-company totals, declared before /{job_id} so "stats" is not read as an id."""
    from core.database import get_company_stats
    try:
        return {"companies": get_company_stats(account)}
    except Exception as exc:
        raise fail(exc, "working out your pipeline stats")


@router.get("")
def list_jobs(account: str = Depends(current_account)):
    from core.database import get_jobs
    return {"jobs": get_jobs(account)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: JobIn, account: str = Depends(current_account)):
    from core.database import create_job
    from core.models import Job
    try:
        job_id = create_job(Job(**body.model_dump()), account)
    except Exception as exc:
        raise fail(exc, "saving that role")
    return {"id": job_id}


@router.get("/{job_id}")
def read(job_id: int, account: str = Depends(current_account)):
    from core.database import get_job
    job = get_job(job_id, account)
    if not job:
        # Not 403. A missing row and someone else's row are the same answer,
        # or the response becomes an oracle for which ids exist.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role.")
    return job


@router.patch("/{job_id}")
def update(job_id: int, body: JobPatch, account: str = Depends(current_account)):
    from core.database import get_job, update_job
    if not get_job(job_id, account):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role.")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to change.")
    try:
        update_job(job_id, fields, account)
    except Exception as exc:
        raise fail(exc, "updating that role")
    return {"ok": True}


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(job_id: int, account: str = Depends(current_account)):
    from core.database import delete_job, get_job
    if not get_job(job_id, account):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role.")
    delete_job(job_id, account)
