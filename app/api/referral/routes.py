from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/referral", tags=["referral"])

_DEFERRED_DETAIL = (
    "The referral reward program is a deferred feature and is not implemented "
    "yet: the users table has no referred_by / referral_reward_used columns, "
    "so eligibility and claiming raised AttributeError -> 500 on every call. "
    "Add the referral schema (owner migration) before re-enabling."
)


@router.post("/eligibility", deprecated=True)
async def eligibility(user=Depends(get_current_user)):  # noqa: B008
    """DEFERRED — per the TASK-15 policy a deferred feature answers 501
    explicitly instead of a permanent 500."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DEFERRED_DETAIL
    )


@router.post("/claim", deprecated=True)
async def claim(user=Depends(get_current_user)):  # noqa: B008
    """DEFERRED — see /eligibility."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DEFERRED_DETAIL
    )


@router.get("/code")
async def invite_code(user=Depends(get_current_user)):  # noqa: B008
    code = str(user.id).replace("-", "")[:6]
    return success_response({"code": code})
