from sqlalchemy.orm import Session

from app.db.models import AIAnalysisSnapshot
from app.services.core.engine.ai_personal_finance_profiler import (
    build_user_profile,
    generate_financial_rating,
)


def save_ai_snapshot(user_id: int, db: Session, year: int, month: int) -> dict:
    profile = build_user_profile(user_id=user_id, db=db, year=year, month=month)
    rating_data = generate_financial_rating(profile, db)

    snapshot = AIAnalysisSnapshot(
        user_id=user_id,
        rating=rating_data["rating"],
        risk=rating_data["risk"],
        summary=rating_data["summary"],
        full_profile=profile,
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return {
        "status": "saved",
        "snapshot_id": snapshot.id,
        "rating": snapshot.rating,
        "risk": snapshot.risk,
    }
