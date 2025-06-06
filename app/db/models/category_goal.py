import uuid

from sqlalchemy import Column, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class CategoryGoal(Base):
    __tablename__ = "category_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    category = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    target_amount = Column(Numeric, nullable=False)
