from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import AIAnalysisSnapshot
from app.services.core.engine.ai_snapshot_service import save_ai_snapshot
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/latest-snapshots")
async def get_latest_ai_snapshots(
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: B008
):
    rows = (
        db.query(AIAnalysisSnapshot)
        .filter_by(user_id=user.id)
        .order_by(AIAnalysisSnapshot.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    data = [
        {
            "user_id": user.id,
            "rating": r.rating,
            "risk": r.risk,
            "summary": r.summary,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return {"count": len(data), "data": data}


@router.post("/snapshot")
async def create_ai_snapshot(
    *,
    year: int,
    month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    result = save_ai_snapshot(user.id, db, year, month)
    return success_response(result)
