
from fastapi import APIRouter
from app.api.cohort.schemas import ProfileRequest, DriftRequest, CohortOut, DriftOut
from app.services.cohort_service import assign_user_cohort, get_user_drift
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/cohort", tags=["cohort"])

@router.post("/assign", response_model=CohortOut)
async def assign_cohort(payload: ProfileRequest):
    cohort = assign_user_cohort(payload.profile)
    return success_response({"cohort": cohort})

@router.post("/drift", response_model=DriftOut)
async def drift(payload: DriftRequest):
    drift = get_user_drift(payload.user_id)
    return success_response({"drift": drift})