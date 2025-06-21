from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models import Mood
from app.utils.response_wrapper import success_response

from .schemas import MoodIn, MoodOut

router = APIRouter(prefix="/mood", tags=["mood"])


@router.post("/", response_model=MoodOut)
async def log_mood(
    data: MoodIn,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    record = db.query(Mood).filter_by(user_id=user.id, date=data.date).first()
    if record:
        record.mood = data.mood
    else:
        record = Mood(user_id=user.id, date=data.date, mood=data.mood)
        db.add(record)
    db.commit()
    db.refresh(record)
    return success_response(
        {"id": str(record.id), "date": record.date, "mood": record.mood}
    )


@router.get("/", response_model=List[MoodOut])
async def list_moods(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(get_current_user),  # noqa: B008
):
    query = db.query(Mood).filter(Mood.user_id == user.id)
    if start_date:
        query = query.filter(Mood.date >= start_date)
    if end_date:
        query = query.filter(Mood.date <= end_date)
    records = query.order_by(Mood.date).all()
    return success_response(
        [{"id": str(r.id), "date": r.date, "mood": r.mood} for r in records]
    )
