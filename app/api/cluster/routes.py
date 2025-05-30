
from fastapi import APIRouter
from app.schemas.cluster import FitRequest, LabelRequest, ClusterResult, LabelResult, CentroidResult
from app.services.cluster_service import fit_cluster_model, get_user_cluster_label, get_cluster_centroids
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/cluster", tags=["cluster"])

@router.post("/fit", response_model=ClusterResult)
async def fit_model(request: FitRequest):
    result = fit_cluster_model(request.user_data)
    return success_response(result)

@router.post("/label", response_model=LabelResult)
async def get_user_label(request: LabelRequest):
    result = get_user_cluster_label(request.user_id)
    return success_response(result)

@router.get("/centroids", response_model=CentroidResult)
async def get_centroids():
    return success_response(get_cluster_centroids())