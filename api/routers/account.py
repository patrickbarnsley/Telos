"""Who am I, export everything, delete everything."""
from fastapi import APIRouter, Depends, Response, status

from api.deps import SESSION_COOKIE, current_account, fail

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/me")
def me(account: str = Depends(current_account)):
    from core.plans import ACTION_LABELS, check_quota, get_plan, is_owner, plan_label
    from core.database import get_profile

    quotas = {}
    for action in ACTION_LABELS:
        allowed, used, limit = check_quota(account, action)
        quotas[action] = {"used": used, "limit": limit, "allowed": allowed}
    profile = get_profile(account) or {}
    return {
        "email": account,
        "plan": get_plan(account),
        "plan_label": plan_label(account),
        "owner": is_owner(account),
        "target_role": profile.get("target_role") or "",
        "quotas": quotas,
    }


@router.get("/export")
def export(account: str = Depends(current_account)):
    from core.database import export_user_data
    try:
        return export_user_data(account)
    except Exception as exc:
        raise fail(exc, "exporting your data")


@router.delete("/account", status_code=status.HTTP_200_OK)
def delete(response: Response, account: str = Depends(current_account)):
    """Erase the account. The spend ledger is anonymised, not deleted:
    it is a financial record, and purge_user_data already draws that line."""
    from core.auth import delete_account
    from core.database import purge_user_data
    try:
        removed = purge_user_data(account)
        delete_account(account)
    except Exception as exc:
        raise fail(exc, "deleting your account")
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"deleted": True, "records": removed}
