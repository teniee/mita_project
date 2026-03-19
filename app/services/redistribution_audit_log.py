"""
Redistribution Audit Log — DB-backed (Problem 2 fix, 2026-03-19)

Previously stored in _audit_log: Dict[str, List[Dict]] = {} which was
wiped on every Railway restart / container redeploy.

Now persists to the redistribution_events PostgreSQL table via the
RedistributionEvent model. Survives restarts, queryable, indexed.

Public API (unchanged signatures, db param added):
    record_redistribution_event(db, user_id, from_category, to_category,
                                 amount, reason, from_day=None)
    get_redistribution_history(db, user_id, limit=50)
    clear_user_audit_log(db, user_id)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models.redistribution_event import RedistributionEvent

logger = get_logger(__name__)


def _parse_day(from_day: Optional[Union[str, date, datetime]]) -> Optional[date]:
    """Normalise from_day to a Python date (or None)."""
    if from_day is None:
        return None
    if isinstance(from_day, datetime):
        return from_day.date()
    if isinstance(from_day, date):
        return from_day
    # String: "2026-03-15" or "2026-03-15T12:00:00"
    try:
        return datetime.fromisoformat(str(from_day)).date()
    except ValueError:
        logger.warning("redistribution_audit_log: could not parse from_day=%r", from_day)
        return None


def record_redistribution_event(
    db: Session,
    user_id: uuid.UUID,
    from_category: str,
    to_category: str,
    amount: Decimal,
    reason: str,
    from_day: Optional[Union[str, date, datetime]] = None,
) -> Dict:
    """
    Persist a redistribution event to the database.

    Called by rebalance_after_overspend() and redistribute_budget_for_user()
    after each transfer. Wrapped in try/except at call site so that a DB
    error here never blocks the core rebalancing logic.

    Returns the event as a dict (mirrors previous in-memory behaviour).
    """
    parsed_day = _parse_day(from_day)

    event_id = uuid.uuid4()
    event = RedistributionEvent(
        id=event_id,
        user_id=user_id,
        from_category=from_category,
        to_category=to_category,
        amount=amount,
        reason=reason,
        from_day=parsed_day,
    )

    # Use a savepoint so that a DB error here (e.g. missing table in tests,
    # transient connection issue) does NOT corrupt the main transaction that
    # the caller (rebalancer) needs to commit its DailyPlan changes.
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except Exception as exc:
        # Savepoint rolled back — main transaction is still alive.
        # The caller's own try/except will decide whether to warn and continue.
        logger.warning(
            "redistribution_audit_log: DB write failed (savepoint rolled back): %s", exc
        )
        raise

    logger.info(
        "Redistribution recorded: %s → %s $%.2f (%s)",
        from_category, to_category, float(amount), reason,
    )

    return {
        "id": str(event_id),
        "timestamp": event.created_at.isoformat() if event.created_at else datetime.utcnow().isoformat(),
        "user_id": str(user_id),
        "from_category": from_category,
        "to_category": to_category,
        "amount": float(amount),
        "reason": reason,
        "from_day": parsed_day.isoformat() if parsed_day else None,
    }


def get_redistribution_history(
    db: Session,
    user_id: uuid.UUID,
    limit: int = 50,
) -> List[Dict]:
    """
    Return redistribution history for a user, newest first.
    """
    events = (
        db.query(RedistributionEvent)
        .filter(RedistributionEvent.user_id == user_id)
        .order_by(RedistributionEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(e.id),
            "timestamp": e.created_at.isoformat(),
            "from_category": e.from_category,
            "to_category": e.to_category,
            "amount": float(e.amount),
            "reason": e.reason,
            "from_day": e.from_day.isoformat() if e.from_day else None,
        }
        for e in events
    ]


def clear_user_audit_log(
    db: Session,
    user_id: uuid.UUID,
) -> int:
    """
    Delete all redistribution events for a user (e.g. on month rollover).
    Returns the number of rows deleted.
    """
    deleted = (
        db.query(RedistributionEvent)
        .filter(RedistributionEvent.user_id == user_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Cleared %d redistribution events for user=%s", deleted, user_id)
    return deleted
