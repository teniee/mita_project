from datetime import datetime, timezone
from typing import List

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.db.models.transaction import Transaction
from app.services.core.analytics.monthly_aggregator import aggregate_monthly_data
from app.services.core.api.analytics_engine import detect_anomalies


async def get_monthly_category_totals(user_id: str, db):
    """Category totals for the current month (AsyncSession).

    The routes inject an AsyncSession; the previous sync body called
    db.execute(...).all() on a coroutine and raised on every request.
    """
    current_year = datetime.now(timezone.utc).year
    current_month = datetime.now(timezone.utc).month

    # spent_at is timestamptz: date()/extract() on it use the DB session's
    # TimeZone, so day/month buckets shifted on any non-UTC server (and made
    # this endpoint's "today" disagree with the UTC-based callers around
    # midnight). Normalize to UTC explicitly.
    spent_at_utc = func.timezone("UTC", Transaction.spent_at)

    stmt = (
        select(Transaction.category, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            extract("year", spent_at_utc) == current_year,
            extract("month", spent_at_utc) == current_month,
        )
        .group_by(Transaction.category)
    )

    result = (await db.execute(stmt)).all()

    return [{"category": row[0], "total": float(row[1])} for row in result]


async def get_monthly_trend(user_id: str, db):
    """Return daily totals for the current month (AsyncSession)."""

    current_year = datetime.now(timezone.utc).year
    current_month = datetime.now(timezone.utc).month

    spent_at_utc = func.timezone("UTC", Transaction.spent_at)

    stmt = (
        select(
            func.date(spent_at_utc).label("day"),
            func.sum(Transaction.amount).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            extract("year", spent_at_utc) == current_year,
            extract("month", spent_at_utc) == current_month,
        )
        .group_by("day")
        .order_by("day")
    )

    result = (await db.execute(stmt)).all()

    return [{"date": row[0].isoformat(), "amount": float(row[1])} for row in result]


def analyze_aggregate(calendar: List[dict]):
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    return aggregate_monthly_data(calendar, current_month)


def analyze_anomalies(calendar: List[dict]):
    # The detector iterates calendar.values() — the API payload is a list
    # of day dicts, which raised AttributeError -> 500 on every call.
    calendar_map = {
        str(day.get("date") or day.get("day") or i): (day or {})
        for i, day in enumerate(calendar)
    }
    return detect_anomalies(calendar_map)
