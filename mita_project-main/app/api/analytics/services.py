
"""Business logic for analytics routes."""

from collections import defaultdict
from datetime import datetime
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


def get_monthly_trend(user_id: str, db: Session) -> list:
    """Return a daily total trend for the current month."""

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
    trend = defaultdict(float)
    for txn in txns:
        key = txn.timestamp.date().isoformat()
        trend[key] += float(txn.amount)
    return [
        {"date": k, "amount": round(v, 2)}
        for k, v in sorted(trend.items())
    ]


def analyze_aggregate(calendar: list) -> dict:
    return {"aggregation": aggregate_monthly_data(calendar)}


def analyze_anomalies(calendar: list) -> dict:
    return {"anomalies": detect_anomalies(calendar)}
