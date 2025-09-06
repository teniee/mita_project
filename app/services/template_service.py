from typing import Optional
from sqlalchemy.orm import Session

from app.db.models import AIAdviceTemplate


class AIAdviceTemplateService:
    """CRUD operations for AI advice templates."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str) -> Optional[str]:
        record = (
            self.db.query(AIAdviceTemplate).filter(AIAdviceTemplate.key == key).first()
        )
        return record.text if record else None

    def set(self, key: str, text: str) -> AIAdviceTemplate:
        record = (
            self.db.query(AIAdviceTemplate).filter(AIAdviceTemplate.key == key).first()
        )
        if record:
            record.text = text
        else:
            record = AIAdviceTemplate(key=key, text=text)
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, key: str) -> None:
        record = (
            self.db.query(AIAdviceTemplate).filter(AIAdviceTemplate.key == key).first()
        )
        if record:
            self.db.delete(record)
            self.db.commit()

    def list_all(self) -> list[AIAdviceTemplate]:
        return self.db.query(AIAdviceTemplate).all()
