from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.cluster import FitRequest, LabelResult
from app.services.cluster_service import get_user_cluster_label
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/cluster", tags=["cluster"])

_DEFERRED_DETAIL = (
    "Cohort clustering is a deferred feature and is not implemented yet: the "
    "mounted request schema (a list of feature rows) has never matched the "
    "in-memory KMeans engine input (a dict of per-user profile/calendar/mood "
    "blobs), and per-process in-memory model state cannot serve a "
    "multi-worker deployment."
)


@router.post("/fit", deprecated=True)
async def fit_model(request: FitRequest, user=Depends(get_current_user)):  # noqa: B008
    """DEFERRED — no backing implementation (answered 500 on every call).

    Per the TASK-15 policy, a deferred feature answers 501 explicitly
    instead of a permanent 500.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DEFERRED_DETAIL
    )


@router.post("/label", response_model=LabelResult)
async def get_user_label(user=Depends(get_current_user)):
    """Best-effort cluster label; 'Unknown Cluster' until a model exists."""
    result = get_user_cluster_label(user.id)
    return success_response(result)


@router.get("/centroids", deprecated=True)
async def get_centroids():
    """DEFERRED — the in-memory model is never fitted (see /fit), so centroid
    access raised AttributeError -> 500 on every call."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=_DEFERRED_DETAIL
    )
