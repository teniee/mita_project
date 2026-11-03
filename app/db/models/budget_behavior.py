"""How the user's money is meant to be spent — migrations 0041 and 0042.

* ``obligation_payments`` (0041): which recorded expense paid which saved
  regular payment (``scheduled_expenses``) on which due date. The ONLY thing
  that settles a fixed obligation: a purchase in the same category is not a
  payment (a car part is not the car loan). One expense pays at most one due
  date; one due date may be paid by several expenses (in parts).
* ``spending_patterns`` (0042): how the user buys what a budget line is for —
  planned purchases on known dates (groceries every Wednesday), a flexible
  envelope with no purchase dates (coffee and walks), or "does not apply to
  me" for one of MITA's suggested lines (no medical insurance). Stated by the
  user; never inferred (``source`` is ``user_confirmed`` only).

Shared tables: the ledger rebuild, the month rollover and the mobile
forecast read them; only the ChatGPT app writes them for now. Both cascade
with the user. Rules: docs/chatgpt-app/behavioral-budget.md.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


PATTERN_KINDS = ("planned", "flexible", "not_applicable")
PATTERN_FREQUENCIES = (
    "daily",
    "weekdays",
    "weekly",
    "biweekly",
    "times_per_month",
    "monthly",
    "dates",
)
PATTERN_SOURCES = ("user_confirmed",)


class ObligationPayment(Base):
    """An expense the user said paid one due date of a saved regular payment."""

    __tablename__ = "obligation_payments"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_obligation_payments_transaction"),
        Index("ix_obligation_payments_user_due", "user_id", "due_date"),
        Index(
            "ix_obligation_payments_obligation_due",
            "scheduled_expense_id",
            "due_date",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_expense_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_expenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_date = Column(Date, nullable=False)
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class SpendingPattern(Base):
    """How the user buys what one budget line is for (stated, never guessed)."""

    __tablename__ = "spending_patterns"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('planned', 'flexible', 'not_applicable')",
            name="ck_spending_patterns_kind",
        ),
        CheckConstraint(
            "frequency IS NULL OR frequency IN ('daily', 'weekdays', 'weekly', "
            "'biweekly', 'times_per_month', 'monthly', 'dates')",
            name="ck_spending_patterns_frequency",
        ),
        CheckConstraint(
            "(kind = 'planned') = (frequency IS NOT NULL)",
            name="ck_spending_patterns_planned_has_frequency",
        ),
        CheckConstraint(
            "times_per_month IS NULL OR times_per_month BETWEEN 1 AND 31",
            name="ck_spending_patterns_times",
        ),
        CheckConstraint(
            "typical_amount IS NULL OR typical_amount > 0",
            name="ck_spending_patterns_typical_amount",
        ),
        CheckConstraint(
            "source IN ('user_confirmed')", name="ck_spending_patterns_source"
        ),
    )

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # The plan line it applies to: one of MITA's lines ("groceries") or one
    # of the user's own ("my:Groceries").
    line_key = Column(String(50), primary_key=True)
    kind = Column(String(16), nullable=False)
    frequency = Column(String(20), nullable=True)
    weekdays = Column(JSONB, nullable=False, default=list)  # 0 = Monday … 6 = Sunday
    days_of_month = Column(JSONB, nullable=False, default=list)
    times_per_month = Column(SmallInteger, nullable=True)
    anchor_date = Column(Date, nullable=True)  # every two weeks: one of the dates
    typical_amount = Column(Numeric(12, 2), nullable=True)
    source = Column(String(20), nullable=False, default="user_confirmed")
    confirmed_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
