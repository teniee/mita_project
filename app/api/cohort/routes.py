from fastapi import APIRouter, Depends

from app.api.cohort.schemas import CohortOut, DriftOut, DriftRequest, ProfileRequest
from app.api.dependencies import get_current_user
from app.services.cohort_service import assign_user_cohort, get_user_drift
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/cohort", tags=["cohort"])


@router.post("/assign", response_model=CohortOut)
async def assign_cohort(
    payload: ProfileRequest, user=Depends(get_current_user)  # noqa: B008
):
    cohort = assign_user_cohort(payload.profile)
    return success_response({"cohort": cohort})


@router.post("/drift", response_model=DriftOut)
async def drift(payload: DriftRequest, user=Depends(get_current_user)):  # noqa: B008
    drift = get_user_drift(user.id)
    return success_response({"drift": drift})
