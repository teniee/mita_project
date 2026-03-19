from datetime import date
from decimal import Decimal
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Transaction
from app.services.core.engine.calendar_updater import update_day_status
from app.services.core.engine.realtime_rebalancer import check_and_rebalance

logger = logging.getLogger(__name__)


def apply_transaction_to_plan(db: Session, txn: Transaction) -> None:
    """Apply an already saved transaction to the DailyPlan table."""
    txn_day = txn.spent_at.date()

    plan = (
        db.query(DailyPlan)
        .filter_by(user_id=txn.user_id, date=txn_day, category=txn.category)
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
                budget_limit=plan.planned_amount
            )
        except Exception as e:
            logger.warning(f"Failed to check budget alerts: {e}")

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
    txn = Transaction(
        user_id=user_id,
        date=day,
        category=category,
        amount=Decimal(amount),
        description=description,
    )
    db.add(txn)

    plan = (
        db.query(DailyPlan)
        .filter_by(user_id=user_id, date=day, category=category)
        .first()
    )
    if plan:
        plan.spent_amount += Decimal(amount)
    else:
        new_plan = DailyPlan(
            user_id=user_id,
            date=day,
            category=category,
            planned_amount=Decimal("0.00"),
            spent_amount=Decimal(amount),
        )
        db.add(new_plan)

    db.commit()

    update_day_status(db, user_id, day)

    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount),
    }
