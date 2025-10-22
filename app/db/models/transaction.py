import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Boolean, Float, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from .base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Basic transaction data
    category = Column(String(50), nullable=False, index=True)  # Index for category filtering
    amount = Column(Numeric(precision=12, scale=2), nullable=False)  # Precise decimal for money
    currency = Column(String(3), default="USD")
    description = Column(String(500), nullable=True)  # Optional description

    # Merchant and location data
    merchant = Column(String(200), nullable=True)  # Merchant name
    location = Column(String(200), nullable=True)  # Transaction location

    # Tags for categorization and filtering
    tags = Column(ARRAY(String), nullable=True)  # Array of tags

    # Recurring transaction tracking
    is_recurring = Column(Boolean, default=False, nullable=False)

    # OCR confidence score (for receipt-based transactions)
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0

    # Receipt/attachment URL
    receipt_url = Column(String(500), nullable=True)  # URL to receipt image

    # Notes field for additional information
    notes = Column(Text, nullable=True)  # Extended notes

    # Timestamps
    spent_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to user
    user = relationship("User", back_populates="transactions")
