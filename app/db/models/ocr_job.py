import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base


class OCRJob(Base):
    """
    Model for tracking OCR receipt processing jobs
    """
    __tablename__ = "ocr_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(100), unique=True, nullable=False, index=True)  # "ocr_userid_timestamp"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Status tracking
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, processing, completed, failed
    progress = Column(Numeric(5, 2), default=0.0)  # 0-100

    # File information
    image_path = Column(String(500), nullable=True)  # Temporary or permanent storage path
    image_url = Column(String(500), nullable=True)  # Public URL if uploaded to cloud storage

    # OCR Results
    store_name = Column(String(200), nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    date = Column(String(50), nullable=True)
    category_hint = Column(String(50), nullable=True)
    confidence = Column(Numeric(5, 2), default=0.0)  # 0-100
    raw_result = Column(JSON, nullable=True)  # Full OCR response

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Numeric(3, 0), default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
