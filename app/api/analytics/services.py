"""Business logic for analytics routes."""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Transaction
from app.services.core.api.analytics_engine import (
    aggregate_monthly_data,
    detect_anomalies,
)


def _month_start_end(now: datetime) -> tuple[datetime, datetime]:
    """Return the start and end datetimes for the given month."""

    start = datetime(now.year, now.month, 1)
    end = datetime(now.year + (now.month == 12), (now.month % 12) + 1, 1)
    return start, end


def get_monthly_category_totals(user_id: str, db: Session) -> dict:
    """Sum expenses by category for the current month."""

    now = datetime.now()
    start, end = _month_start_end(now)
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.timestamp >= start,
            Transaction.timestamp < end,
        )
        .all()
    )
    totals = defaultdict(float)
    for txn in txns:
        totals[txn.category] += float(txn.amount)
    return dict(totals)


def get_trend(
    user_id: str,
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list:
    """Return aggregated daily totals within a window."""

    end_date = end_date or datetime.utcnow().date()
    start_date = start_date or (end_date - timedelta(days=365))

    stmt = (
        select(
            func.date(Transaction.spent_at).label("d"),
            func.sum(Transaction.amount).label("a"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.spent_at >= start_date,
            Transaction.spent_at <= end_date,
        )
        .group_by("d")
        .order_by("d")
    )
    rows = db.execute(stmt).all()
    return [{"date": r.d.isoformat(), "amount": float(r.a)} for r in rows]


def analyze_aggregate(calendar: list) -> dict:
    return {"aggregation": aggregate_monthly_data(calendar)}


def analyze_anomalies(calendar: list) -> dict:
    return {"anomalies": detect_anomalies(calendar)}
