from app.utils.response_wrapper import success_response

from fastapi import APIRouter
from app.schemas.drift import DriftLogRequest, DriftGetRequest
from app.services.core.cohort.cohort_drift_tracker import CohortDriftTracker

router = APIRouter()
drifter = CohortDriftTracker()

@router.post("/log")
def log_drift(request: DriftLogRequest):
    return drifter.log_month(**request.dict())

@router.post("/get")
def get_drift(request: DriftGetRequest):
    return drifter.get_drift(**request.dict())