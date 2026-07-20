import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.date_utils import day_to_range
from app.db.models import DailyPlan, Transaction, User
from app.services.core.engine.calendar_updater import update_day_status
from app.services.core.engine.realtime_rebalancer import check_and_rebalance

logger = logging.getLogger(__name__)


def _safe_zone(tz: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def user_timezone_of(db: Session, user_id: UUID) -> str:
    tz = db.query(User.timezone).filter(User.id == user_id).scalar()
    return tz or "UTC"


def local_day_of(spent_at: datetime, tz: Optional[str]) -> date:
    """Calendar day of a stored (UTC) transaction instant in the user's
    timezone — the day the user experienced the spend on."""
    if spent_at.tzinfo is None:
        spent_at = spent_at.replace(tzinfo=timezone.utc)
    return spent_at.astimezone(_safe_zone(tz)).date()


def local_day_utc_window(day: date, tz: Optional[str]) -> Tuple[datetime, datetime]:
    """UTC instant range [start, end) covering the user's local calendar day.

    Returned as naive datetimes meaning UTC — matching how spent_at is
    stored/compared across the codebase (and SQLite test databases, which
    cannot compare aware against stored-naive values).
    """
    zone = _safe_zone(tz)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def recalculate_plan_spent(
    db: Session,
    user_id: UUID,
    day: date,
    category: str,
    tz: Optional[str] = None,
) -> None:
    """Recompute DailyPlan.spent_amount for (user, day, category) from the
    non-deleted transaction ledger.

    Idempotent by construction — used after transaction edits and deletes so
    the accrual cannot drift (the additive apply_transaction_to_plan path
    would double-count an edit and never reverse a delete).

    `day` is the user's LOCAL calendar day; the ledger window is the UTC
    range of that local day (a Sofia day spans 21:00Z–21:00Z, not 00:00Z).
    """
    if tz is None:
        tz = user_timezone_of(db, user_id)
    day_start, day_end = day_to_range(day)
    txn_start, txn_end = local_day_utc_window(day, tz)
    total = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.category == category,
            Transaction.spent_at >= txn_start,
            Transaction.spent_at < txn_end,
        )
        .scalar()
    )
    total = Decimal(total or 0)

    plan = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= day_start,
            DailyPlan.date <= day_end,
            DailyPlan.category == category,
        )
        .first()
    )
    if plan:
        plan.spent_amount = total
    elif total:
        db.add(
            DailyPlan(
                user_id=user_id,
                date=day,
                category=category,
                planned_amount=Decimal("0.00"),
                daily_budget=Decimal("0.00"),
                spent_amount=total,
            )
        )

    db.commit()
    update_day_status(db, user_id, day)

    # Keep the auto-rebalance promise consistent with the create path; a
    # decreased spend simply makes this a no-op.
    try:
        rebalance_result = check_and_rebalance(
            db=db,
            user_id=user_id,
            category=category,
            transaction_date=day,
        )
        if rebalance_result is not None:
            update_day_status(db, user_id, day)
    except Exception as e:
        logger.warning(f"Auto-rebalance failed in recalculate (non-critical): {e}")


def apply_transaction_to_plan(db: Session, txn: Transaction) -> None:
    """Apply an already saved transaction to the DailyPlan table.

    The plan day is the user's LOCAL calendar day of the spend — a txn at
    02:00 Sofia (23:00Z previous day) belongs to the Sofia date the user
    picked, not the UTC date.
    """
    txn_day = local_day_of(txn.spent_at, user_timezone_of(db, txn.user_id))

    day_start, day_end = day_to_range(txn_day)
    plan = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == txn.user_id,
            DailyPlan.date >= day_start,
            DailyPlan.date <= day_end,
            DailyPlan.category == txn.category,
        )
        .first()
    )
    if plan:
        plan.spent_amount += txn.amount
    else:
        new_plan = DailyPlan(
            user_id=txn.user_id,
            date=txn_day,
            category=txn.category,
            planned_amount=Decimal("0.00"),
            # Unplanned category for this day: explicit zero limit, not NULL,
            # so calendar limits and spending checks stay well-defined.
            daily_budget=Decimal("0.00"),
            spent_amount=txn.amount,
        )
        db.add(new_plan)
        plan = new_plan

    db.commit()
    update_day_status(db, txn.user_id, txn_day)

    # MODULE 10: Check budget and send alerts if needed
    if plan and plan.planned_amount > 0:
        try:
            from app.services.budget_alert_service import get_budget_alert_service

            alert_service = get_budget_alert_service(db)
            alert_service.check_single_category(
                user_id=txn.user_id,
                category=txn.category,
                spent_amount=plan.spent_amount,
                budget_limit=plan.planned_amount,
            )
        except Exception as e:
            logger.warning(f"Failed to check budget alerts: {e}")

    # VELOCITY ALERT: check if this category is burning budget too fast
    try:
        from app.services.velocity_alert_service import check_velocity_after_transaction

        check_velocity_after_transaction(
            db=db,
            user_id=txn.user_id,
            category=txn.category,
            transaction_date=txn_day,
        )
    except Exception as e:
        logger.warning(f"Velocity check failed (non-critical): {e}")

    # AUTO-REBALANCE: if category is overspent, pull budget from future
    # low-priority days and credit back to this day — core MITA promise.
    try:
        rebalance_result = check_and_rebalance(
            db=db,
            user_id=txn.user_id,
            category=txn.category,
            transaction_date=txn_day,
        )
        if rebalance_result is not None:
            # Re-evaluate day status — planned_amount on this day may have
            # increased after rebalancing, flipping red → green/yellow.
            update_day_status(db, txn.user_id, txn_day)
            logger.info(
                "Auto-rebalance: covered=%.2f uncovered=%.2f transfers=%d",
                float(rebalance_result.covered),
                float(rebalance_result.uncovered),
                len(rebalance_result.transfers),
            )
    except Exception as e:
        logger.warning(f"Auto-rebalance failed (non-critical): {e}")


def record_expense(
    db: Session,
    user_id: UUID,
    day: date,
    category: str,
    amount: float,
    description: str = "",
):
    # Transaction has no `date` column — the temporal column is spent_at.
    # Decimal(str(...)) avoids importing binary-float error into money.
    txn = Transaction(
        user_id=user_id,
        spent_at=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
        category=category,
        amount=Decimal(str(amount)),
        description=description,
    )
    db.add(txn)

    _day_start, _day_end = day_to_range(day)
    plan = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= _day_start,
            DailyPlan.date <= _day_end,
            DailyPlan.category == category,
        )
        .first()
    )
    if plan:
        plan.spent_amount += Decimal(str(amount))
    else:
        new_plan = DailyPlan(
            user_id=user_id,
            date=day,
            category=category,
            planned_amount=Decimal("0.00"),
            daily_budget=Decimal("0.00"),
            spent_amount=Decimal(str(amount)),
        )
        db.add(new_plan)

    db.commit()

    update_day_status(db, user_id, day)

    # AUTO-REBALANCE: ensure future days are recalculated — core MITA promise.
    try:
        rebalance_result = check_and_rebalance(
            db=db,
            user_id=user_id,
            category=category,
            transaction_date=day,
        )
        if rebalance_result is not None:
            update_day_status(db, user_id, day)
            logger.info(
                "Auto-rebalance (record_expense): covered=%.2f uncovered=%.2f transfers=%d",
                float(rebalance_result.covered),
                float(rebalance_result.uncovered),
                len(rebalance_result.transfers),
            )
    except Exception as e:
        logger.warning(f"Auto-rebalance failed in record_expense (non-critical): {e}")

    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount),
    }
