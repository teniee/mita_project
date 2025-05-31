from fastapi import APIRouter
from pydantic import BaseModel
from app.services.core.cohort.cohort_service import CohortService
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/cohort", tags=["cohort"])
service = CohortService()

class ProfileRequest(BaseModel):
    user_id: str
    profile: dict

class DriftRequest(BaseModel):
    user_id: str

@router.post("/assign")
async def assign_cohort(payload: ProfileRequest):
    cohort = service.assign_cohort(payload.profile)
    return success_response({"cohort": cohort})

@router.post("/drift")
async def get_drift(payload: DriftRequest):
    drift = service.get_cohort_drift(payload.user_id)
    return success_response({"drift": drift})