"""The Match pillar, plus interview prep. Every AI call is quota-gated first."""
from fastapi import (APIRouter, Depends, File, HTTPException, UploadFile,
                     status)
from pydantic import BaseModel

from api.deps import current_account, fail, require_quota

router = APIRouter(prefix="/api/match", tags=["match"])


class MatchIn(BaseModel):
    jd_text: str
    job_id: int | None = None
    company: str | None = None
    role: str | None = None


class ScamCheckIn(BaseModel):
    company: str
    jd_text: str


MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # same cap as the resume upload


@router.post("/from-image")
async def from_image(file: UploadFile = File(...),
                     account: str = Depends(require_quota("jd_extract"))):
    """Transcribe a job posting out of a screenshot.

    The text comes back for the user to read before anything is scored against
    it. Nothing is saved here: an image is the least reliable input Telos takes,
    and a transcription the user has not looked at has no business becoming a
    stored job description.
    """
    from core.ai_engine import extract_jd_from_image
    from core.plans import record_usage

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "That image is larger than 5 MB.")
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That file is empty.")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "That is not an image. Upload a screenshot of the posting, or paste "
            "the text instead.")

    class _Uploaded:
        """extract_jd_from_image expects a file-like with .read()."""
        def __init__(self, data): self._data = data
        def read(self): return self._data

    try:
        text = extract_jd_from_image(_Uploaded(raw))
    except Exception as exc:
        raise fail(exc, "reading that screenshot")

    if not (text or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No readable job text in that image. A sharper screenshot of the "
            "posting usually fixes it, or paste the text instead.")

    record_usage(account, "jd_extract")
    return {"jd_text": text}


@router.get("")
def history(account: str = Depends(current_account)):
    from core.database import get_all_match_results
    return {"results": get_all_match_results(account)}


@router.post("", status_code=status.HTTP_201_CREATED)
def score(body: MatchIn, account: str = Depends(require_quota("match"))):
    from core.ai_engine import score_match
    from core.database import get_active_resume, get_profile, save_match_result
    from core.plans import record_usage

    resume = get_active_resume(account)
    profile = get_profile(account) or {}
    resume_text = (resume or {}).get("resume_text") or profile.get("resume_text") or ""
    if not resume_text.strip():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Add a resume on your profile before scoring a role.")
    if not body.jd_text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paste the job description first.")

    try:
        result = score_match(resume_text, body.jd_text, profile.get("target_role") or "")
    except Exception as exc:
        raise fail(exc, "scoring that role")

    record_usage(account, "match")
    match_id = save_match_result(
        result.get("overall_score"), result.get("summary"),
        result.get("matched_requirements"), result.get("missing_requirements"),
        result.get("suggested_certifications"), result.get("suggested_actions"),
        body.jd_text, account, job_id=body.job_id,
        company=body.company, role=body.role,
        resume_version_id=(resume or {}).get("id"),
        resume_version_label=(resume or {}).get("version_label"),
        resume_snapshot=resume_text)
    return {"id": match_id, **result}


@router.get("/{match_id}")
def read(match_id: int, account: str = Depends(current_account)):
    from core.database import get_match_result
    row = get_match_result(match_id, account)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such match.")
    return row


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(match_id: int, account: str = Depends(current_account)):
    from core.database import delete_match_result, get_match_result
    if not get_match_result(match_id, account):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such match.")
    delete_match_result(match_id, account)


@router.get("/{match_id}/interview-prep")
def read_prep(match_id: int, account: str = Depends(current_account)):
    from core.database import get_interview_prep, get_match_result
    if not get_match_result(match_id, account):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such match.")
    row = get_interview_prep(match_id, account)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No prep generated for that match yet.")
    # Unwrapped, for the same reason as the roadmap: the stored row nests the
    # prep under "prep" alongside metadata. That envelope is how it is saved,
    # not what a caller wants, and returning it meant the questions list was
    # invisible one level down.
    prep = row.get("prep") if isinstance(row.get("prep"), dict) else row
    return {**(prep or {}),
            "generated_at": row.get("generated_at"),
            "company": row.get("company"),
            "role": row.get("role")}


@router.post("/{match_id}/interview-prep", status_code=status.HTTP_201_CREATED)
def make_prep(match_id: int, account: str = Depends(require_quota("interview_prep"))):
    from core.ai_engine import generate_interview_prep
    from core.database import (get_active_resume, get_match_result, get_profile,
                               save_interview_prep)
    from core.plans import record_usage

    match = get_match_result(match_id, account)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such match.")

    resume = get_active_resume(account) or {}
    profile = get_profile(account) or {}
    resume_text = match.get("resume_snapshot") or resume.get("resume_text") \
        or profile.get("resume_text") or ""
    try:
        prep = generate_interview_prep(match, resume_text, profile.get("target_role") or "")
    except Exception as exc:
        raise fail(exc, "preparing your interview questions")

    record_usage(account, "interview_prep")
    save_interview_prep(account, match_id, prep)
    return prep


@router.post("/scam-check", status_code=status.HTTP_200_OK)
def scam_check(body: ScamCheckIn, account: str = Depends(require_quota("scam_check"))):
    """Is this employer real, and is this posting trying to manipulate the check?

    The verdict comes back from the model and is then overruled if the posting
    contains text aimed at automated screening. That second step runs after the
    call on purpose: if the posting talked its way to a clean verdict, the
    model's own output is the thing that cannot be trusted to mention it.
    """
    from core.ai_engine import check_company_legitimacy
    from core.plans import record_usage

    if not body.company.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name the company first.")
    if not body.jd_text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paste the posting first.")

    try:
        verdict = check_company_legitimacy(body.company, body.jd_text)
    except Exception as exc:
        raise fail(exc, "checking that employer")

    record_usage(account, "scam_check")
    return verdict
