"""Profile and resume versions."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import current_account, fail

router = APIRouter(prefix="/api", tags=["profile"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # matches .streamlit/config.toml maxUploadSize


class ProfileIn(BaseModel):
    resume_text: str
    target_role: str
    goals: str | None = None
    resume_filename: str | None = None


@router.get("/profile")
def read(account: str = Depends(current_account)):
    from core.database import get_profile
    return get_profile(account) or {}


@router.put("/profile")
def write(body: ProfileIn, account: str = Depends(current_account)):
    from core.database import save_profile
    from core.models import Profile
    try:
        save_profile(Profile(**body.model_dump()), account)
    except Exception as exc:
        raise fail(exc, "saving your profile")
    return {"ok": True}


@router.get("/resumes")
def versions(account: str = Depends(current_account)):
    from core.database import get_resume_versions
    return {"versions": get_resume_versions(account)}


@router.post("/resumes", status_code=status.HTTP_201_CREATED)
async def upload(file: UploadFile = File(...), label: str = "",
                 account: str = Depends(current_account)):
    from core.ai_engine import extract_resume_text
    from core.database import save_resume_version

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            "That file is larger than 5 MB.")

    class _Uploaded:
        """extract_resume_text expects a file-like with .name and .read()."""
        def __init__(self, name, data):
            self.name, self._data = name, data
        def read(self):
            return self._data
        def getvalue(self):
            return self._data

    try:
        text = extract_resume_text(_Uploaded(file.filename or "resume.pdf", raw))
    except Exception as exc:
        # A file the parser cannot open is the uploader's problem, not ours, and
        # the generic handler was answering "something went wrong on our side,
        # email support" for a corrupt PDF. Say what is wrong and what to do.
        if "pdf" in type(exc).__name__.lower() or "PDFSyntax" in str(type(exc)):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "That file could not be opened as a PDF. If you exported it from "
                "a word processor, try saving as PDF again, or upload the DOCX "
                "instead.")
        raise fail(exc, "reading that resume")
    if not (text or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "No text could be read from that file. A scanned image "
                            "needs to be a text PDF or a DOCX.")
    version_id = save_resume_version(account, label or (file.filename or "Resume"),
                                     text, file.filename or "resume.pdf", set_active=True)
    return {"id": version_id, "characters": len(text)}


@router.put("/resumes/{version_id}/active")
def make_active(version_id: int, account: str = Depends(current_account)):
    from core.database import get_resume_versions, set_active_resume
    if not any(v.get("id") == version_id for v in get_resume_versions(account)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such resume version.")
    set_active_resume(account, version_id)
    return {"ok": True}


@router.delete("/resumes/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(version_id: int, account: str = Depends(current_account)):
    from core.database import delete_resume_version, get_resume_versions
    if not any(v.get("id") == version_id for v in get_resume_versions(account)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such resume version.")
    delete_resume_version(version_id, account)
