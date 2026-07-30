import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


class DailyPlan(Base):
    __tablename__ = "daily_plan"
    # INV-16: at most one plan row per (user, day, category). Without this,
    # onboarding re-submits appended duplicate rows and the .first()-based
    # spend accrual silently split spending across them.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", "category", name="uq_daily_plan_user_date_category"
        ),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # Category and budget tracking columns
    category = Column(String(100), nullable=True, index=True)  # Spending category
    planned_amount = Column(
        Numeric(12, 2), nullable=True, default=Decimal("0.00")
    )  # Budgeted amount
    spent_amount = Column(
        Numeric(12, 2), nullable=True, default=Decimal("0.00")
    )  # Actual spent
    daily_budget = Column(Numeric(12, 2), nullable=True)  # Total daily budget limit
    status = Column(
        String(20), nullable=True, default="green"
    )  # green/yellow/red status

    # Links this row to a specific Goal (set for goal_savings category rows only).
    # ON DELETE SET NULL is a DB-level safety net; the application removes future
    # rows at the service layer before a goal is soft-deleted.
    goal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # JSONB for additional metadata and backward compatibility.
    #
    # none_as_null: assigning Python None must produce SQL NULL, not the JSON
    # `null` literal. Without it, clearing the column (consume_realtime_adjustment
    # sets `plan_json = metadata or None` once the last key is consumed) left
    # 'null'::jsonb behind, so a row that started as SQL NULL did not return to
    # SQL NULL after a create/edit/delete round trip. Purely a storage
    # representation change - no schema migration is involved, and readers
    # already treat both as absent.
    plan_json = Column(JSONB(none_as_null=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
