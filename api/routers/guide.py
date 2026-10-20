"""The Guide pillar: roadmap and advisor."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import current_account, fail, require_quota

router = APIRouter(prefix="/api", tags=["guide"])


class AdvisorIn(BaseModel):
    message: str
    history: list[dict] = []
    career_path_id: int | None = None


@router.get("/roadmap")
def read(career_path_id: int | None = None, account: str = Depends(current_account)):
    """Unwrapped on purpose.

    get_critical_path stores the roadmap under a "path" key alongside a
    timestamp. That wrapper is how the row is shaped, not what a caller wants,
    and leaking it meant the frontend read milestones off the envelope and
    rendered an empty roadmap.
    """
    from core.database import get_critical_path
    row = get_critical_path(account, career_path_id) or {}
    path = row.get("path") if isinstance(row.get("path"), dict) else row
    return {**(path or {}), "generated_at": row.get("generated_at")}


@router.post("/roadmap", status_code=status.HTTP_201_CREATED)
def build(career_path_id: int | None = None,
          account: str = Depends(require_quota("roadmap"))):
    from core.ai_engine import generate_critical_path
    from core.database import (get_all_match_results, get_profile, save_critical_path)
    from core.plans import record_usage

    profile = get_profile(account)
    if not profile or not (profile.get("resume_text") or "").strip():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Add a resume and a target role before building a roadmap.")
    try:
        path = generate_critical_path(profile, get_all_match_results(account))
    except Exception as exc:
        raise fail(exc, "building your roadmap")

    record_usage(account, "roadmap")
    save_critical_path(account, path, career_path_id)
    return path


@router.post("/advisor")
def advise(body: AdvisorIn, account: str = Depends(require_quota("advisor"))):
    from core.ai_engine import chat_with_advisor
    from core.database import get_critical_path, get_profile
    from core.plans import record_usage

    if not body.message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ask a question first.")
    profile = get_profile(account) or {}
    path = get_critical_path(account, body.career_path_id) or {}
    try:
        reply = chat_with_advisor(profile, path, body.history, body.message)
    except Exception as exc:
        raise fail(exc, "asking your advisor")

    record_usage(account, "advisor")
    return {"reply": reply}


class PathIn(BaseModel):
    path_name: str
    target_role: str
    goals: str | None = None


class MilestoneIn(BaseModel):
    milestone_order: int
    milestone_title: str
    completed: bool
    career_path_id: int | None = None


@router.get("/paths")
def list_paths(account: str = Depends(current_account)):
    from core.database import get_career_paths
    return {"paths": get_career_paths(account)}


@router.post("/paths", status_code=status.HTTP_201_CREATED)
def create_path(body: PathIn, account: str = Depends(current_account)):
    from core.database import create_career_path
    if not body.path_name.strip() or not body.target_role.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "A path needs a name and a target role.")
    try:
        path_id = create_career_path(account, body.path_name, body.target_role,
                                     goals=body.goals)
    except Exception as exc:
        raise fail(exc, "creating that path")
    return {"id": path_id}


@router.delete("/paths/{path_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_path(path_id: int, account: str = Depends(current_account)):
    from core.database import delete_career_path, get_career_paths
    if not any(p.get("id") == path_id for p in get_career_paths(account)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such path.")
    delete_career_path(path_id, account)


@router.get("/roadmap/progress")
def progress(career_path_id: int | None = None, account: str = Depends(current_account)):
    from core.database import get_milestone_progress
    return {"progress": get_milestone_progress(account, career_path_id)}


@router.put("/roadmap/progress")
def set_progress(body: MilestoneIn, account: str = Depends(current_account)):
    """Ticking a milestone off. Deliberately not quota-gated: recording that you
    did something costs nothing to serve and charging for it would be absurd."""
    from core.database import save_milestone_progress
    try:
        save_milestone_progress(account, body.milestone_order, body.milestone_title,
                                body.completed, body.career_path_id)
    except Exception as exc:
        raise fail(exc, "saving your progress")
    return {"ok": True}
