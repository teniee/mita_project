"""The user's stated spending patterns (``spending_patterns``, migration 0042).

Read by the reviewed budget (ChatGPT) and the month rollover, so a new month
keeps how the user buys — groceries every Wednesday, coffee as a flexible
budget, no medical insurance — instead of copying how many dates last month
happened to have. Written only from a user's statement (``source`` is
``user_confirmed``); MITA never infers one.

Dependency-free (SQLAlchemy only): the MCP image and the API both import it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Mapping, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SpendingPattern as PatternRow
from app.services.core.engine.spending_schedule import (
    KIND_NOT_APPLICABLE,
    SpendingPattern,
)


def pattern_of(row: PatternRow) -> SpendingPattern:
    return SpendingPattern(
        kind=row.kind,
        frequency=row.frequency,
        weekdays=tuple(int(d) for d in (row.weekdays or [])),
        days_of_month=tuple(int(d) for d in (row.days_of_month or [])),
        times_per_month=row.times_per_month,
        anchor_date=row.anchor_date,
        typical_amount=(
            Decimal(str(row.typical_amount)) if row.typical_amount is not None else None
        ),
    )


def stored_patterns(db: Session, user_id: UUID) -> Dict[str, SpendingPattern]:
    """``{line key: pattern}`` for every line the user described."""
    rows = db.execute(select(PatternRow).where(PatternRow.user_id == user_id)).scalars()
    return {row.line_key: pattern_of(row) for row in rows}


def confirmed_at(db: Session, user_id: UUID) -> Dict[str, datetime]:
    rows = db.execute(
        select(PatternRow.line_key, PatternRow.confirmed_at).where(
            PatternRow.user_id == user_id
        )
    ).all()
    return {key: at for key, at in rows}


def not_applicable(patterns: Mapping[str, SpendingPattern]) -> frozenset:
    """MITA's lines the user said do not apply to them."""
    return frozenset(k for k, p in patterns.items() if p.kind == KIND_NOT_APPLICABLE)


def save_pattern(
    db: Session,
    user_id: UUID,
    line_key: str,
    pattern: SpendingPattern,
    now: datetime,
) -> bool:
    """Insert or overwrite one line's pattern; True when anything changed.
    Does not commit."""
    pattern = pattern.validated()
    row = db.get(PatternRow, (user_id, line_key))
    values = dict(
        kind=pattern.kind,
        frequency=pattern.frequency,
        weekdays=list(pattern.weekdays),
        days_of_month=list(pattern.days_of_month),
        times_per_month=pattern.times_per_month,
        anchor_date=pattern.anchor_date,
        typical_amount=pattern.typical_amount,
        source="user_confirmed",
    )
    if row is None:
        db.add(
            PatternRow(
                user_id=user_id,
                line_key=line_key,
                confirmed_at=now,
                created_at=now,
                updated_at=now,
                **values,
            )
        )
        return True
    if pattern_of(row) == pattern:
        return False
    for name, value in values.items():
        setattr(row, name, value)
    row.confirmed_at = now
    row.updated_at = now
    return True


def anchor_or_none(value: Optional[str]) -> Optional[date]:
    return date.fromisoformat(value) if value else None
