from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.db.models.transaction import Transaction
from app.services.core.analytics.monthly_aggregator import aggregate_monthly_data
from app.services.core.api.analytics_engine import detect_anomalies


def get_monthly_category_totals(user_id: str, db: Session):
    current_year = datetime.utcnow().year
    current_month = datetime.utcnow().month

    stmt = (
        select(Transaction.category, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.user_id == user_id,
            extract("year", Transaction.spent_at) == current_year,
            extract("month", Transaction.spent_at) == current_month,
        )
        .group_by(Transaction.category)
    )

    result = db.execute(stmt).all()

    return [{"category": row[0], "total": float(row[1])} for row in result]


def get_trend(
    user_id: str,
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
):
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


def analyze_aggregate(calendar: List[dict]):
    current_month = datetime.utcnow().strftime("%Y-%m")
    return aggregate_monthly_data(calendar, current_month)


def analyze_anomalies(calendar: List[dict]):
    return detect_anomalies(calendar)
