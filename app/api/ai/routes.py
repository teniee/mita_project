from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.db.models import AIAnalysisSnapshot, User
from app.api.dependencies import get_current_user
from app.services.core.engine.ai_snapshot_service import save_ai_snapshot
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/latest-snapshots")
async def get_latest_ai_snapshots(db: Session = Depends(get_db)):  # noqa: B008
    users = db.query(User).all()
    result = []

    for user in users:
        snapshot = (
            db.query(AIAnalysisSnapshot)
            .filter_by(user_id=user.id)
            .order_by(AIAnalysisSnapshot.created_at.desc())
            .first()
        )
        if snapshot:
            result.append(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "rating": snapshot.rating,
                    "risk": snapshot.risk,
                    "summary": snapshot.summary,
                    "created_at": snapshot.created_at.isoformat(),
                }
            )

    return {"count": len(result), "data": result}


@router.post("/snapshot")
async def create_ai_snapshot(
    *, year: int, month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    result = save_ai_snapshot(user.id, db, year, month)
    return success_response(result)
