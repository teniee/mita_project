from app.utils.response_wrapper import success_response

from fastapi import APIRouter
from app.schemas.cluster import FitRequest, LabelRequest
from app.services.core.cohort.cohort_cluster_engine import CohortClusterEngine

router = APIRouter()
cluster_engine = CohortClusterEngine()

@router.post("/fit")
def fit_model(request: FitRequest):
    return cluster_engine.fit(request.user_data)

@router.post("/label")
def get_user_label(request: LabelRequest):
    return cluster_engine.get_label(request.user_id)

@router.get("/centroids")
def get_cluster_centroids():
    return cluster_engine.get_centroids()