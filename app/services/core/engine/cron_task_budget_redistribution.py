import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.session import get_db
from app.db.models import User
from app.services.budget_redistributor import redistribute_budget_for_user


def run_budget_redistribution_batch():
    """Run monthly redistribution for all active users."""
    db: Session = next(get_db())

    now = datetime.now(timezone.utc)
    # Redistribute for the current month — rebalance categories that already exceeded budget.
    # Future days are handled by realtime_rebalancer when transactions are recorded.
    year = now.year
    month = now.month

    users = db.query(User).filter(User.is_active.is_(True)).all()
    for user in users:
        try:
            result = redistribute_budget_for_user(db, user.id, year, month)
            msg = (
                f"Redistribution for user {user.id} "
                f"{year}-{month:02d}: {result['status']}"
            )
            logger.info(msg)
        except Exception as e:
            logger.error("Redistribution failed for user %s: %s", user.id, e)
        # On first day of month: roll over last month's savings surplus to goal
        try:
            if now.day == 1:
                from app.services.savings_surplus_service import rollover_month_savings
                prev_year = year if month > 1 else year - 1
                prev_month = month - 1 if month > 1 else 12
                rollover = rollover_month_savings(db, user.id, prev_year, prev_month)
                if rollover.get("applied_to_goal"):
                    logger.info("Savings rollover for user %s: %s", user.id, rollover)
        except Exception as e:
            logger.error("Savings rollover failed for user %s: %s", user.id, e)
