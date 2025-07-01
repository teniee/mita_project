from sqlalchemy import Column, Integer, String
from .base import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, unique=True)
    data = Column(String)  # JSON or other structured format
