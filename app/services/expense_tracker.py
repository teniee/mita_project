import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.date_utils import day_to_range
from app.db.models import DailyPlan, Transaction
from app.services.core.engine.calendar_updater import update_day_status
from app.services.core.engine.realtime_rebalancer import check_and_rebalance

logger = logging.getLogger(__name__)


def record_expense(
    db: Session,
    user_id,
    day: date,
    category: str,
    amount: float,
    description: str = "",
):
    # 1. Save into the transactions table
    txn = Transaction(
        user_id=user_id,
        date=day,
        category=category,
        amount=Decimal(amount),
        description=description,
    )
    db.add(txn)

    # 2. Update the daily calendar plan
    day_start, day_end = day_to_range(day)
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
        plan.spent_amount += Decimal(amount)
    else:
        # Create plan row if category is missing
        new_plan = DailyPlan(
            user_id=user_id,
            date=day,
            category=category,
            planned_amount=Decimal("0.00"),
            spent_amount=Decimal(amount),
        )
        db.add(new_plan)

    db.commit()

    # 3. Update day status (green/yellow/red)
    update_day_status(db, user_id, day)

    # 4. AUTO-REBALANCE: ensure future days are recalculated — core MITA promise.
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
                "Auto-rebalance (receipt record_expense): covered=%.2f uncovered=%.2f transfers=%d",
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
