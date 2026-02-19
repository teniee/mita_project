from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
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
async def log_drift(request: DriftLogRequest, user=Depends(get_current_user)):  # noqa: B008
    result = log_cohort_drift(str(user.id), request.month, request.value)
    return success_response(result)


@router.post("/get", response_model=DriftGetResponse)
async def fetch_drift(request: DriftGetRequest, user=Depends(get_current_user)):  # noqa: B008
    result = get_cohort_drift(str(user.id), request.month)
    return success_response(result)
