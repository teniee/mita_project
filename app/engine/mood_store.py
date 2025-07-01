"""Simple persistent store for user moods."""

from sqlalchemy.orm import Session

from app.core.session import get_db
from app.db.models import Mood


def save_mood(user_id: str, date: str, mood: str) -> None:
    db: Session = next(get_db())
    obj = db.query(Mood).filter_by(user_id=user_id, date=date).first()
    if obj:
        obj.mood = mood
    else:
        obj = Mood(user_id=user_id, date=date, mood=mood)
        db.add(obj)
    db.commit()


def get_mood(user_id: str, date: str) -> str | None:
    db: Session = next(get_db())
    obj = db.query(Mood).filter_by(user_id=user_id, date=date).first()
    return obj.mood if obj else None
