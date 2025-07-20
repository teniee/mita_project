from fastapi import APIRouter

from app.schemas.drift import (
    DriftGetRequest,
    DriftGetResponse,
    DriftLogRequest,
    DriftLogResponse,
)
from app.services.drift_service import get_cohort_drift, log_cohort_drift
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/drift", tags=["drift"])


@router.post("/log", response_model=DriftLogResponse)
async def log_drift(request: DriftLogRequest):
    result = log_cohort_drift(request.dict())
    return success_response(result)


@router.post("/get", response_model=DriftGetResponse)
async def fetch_drift(request: DriftGetRequest):
    result = get_cohort_drift(request.dict())
    return success_response(result)
