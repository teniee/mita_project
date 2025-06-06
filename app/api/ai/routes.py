from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.db.models import AIAnalysisSnapshot, User

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
