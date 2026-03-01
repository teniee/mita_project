"""
Budget Alert Service
Monitors spending and sends alerts when budgets are at risk or exceeded
"""
from typing import Dict, List
from uuid import UUID
from decimal import Decimal
import logging

from sqlalchemy.orm import Session

from app.services.core.engine.budget_tracker import BudgetTracker
from app.services.notification_integration import get_notification_integration

logger = logging.getLogger(__name__)


class BudgetAlertService:
    """
    Service for monitoring budget spending and sending alerts
    """

    # Thresholds for sending alerts
    WARNING_THRESHOLD = 0.80  # 80% of budget
    DANGER_THRESHOLD = 1.00   # 100% of budget (exceeded)

    def __init__(self, db: Session):
        self.db = db
        self.notifier = get_notification_integration(db)

    def check_budget_alerts(
        self,
        user_id: UUID,
        year: int,
        month: int,
        category_budgets: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Check all category budgets and send alerts if needed

        Args:
            user_id: User UUID
            year: Year to check
            month: Month to check
            category_budgets: Dict mapping category to budget limit

        Returns:
            List of alerts sent
        """
        alerts_sent = []

        try:
            tracker = BudgetTracker(self.db, user_id, year, month)
            spent_amounts = tracker.get_spent()

            for category, budget_limit in category_budgets.items():
                if budget_limit <= 0:
                    continue  # Skip categories with no budget

                spent = spent_amounts.get(category, Decimal('0.00'))
                percentage = float(spent / budget_limit)

                # Check if we should send an alert
                alert = self._check_category_alert(
                    user_id=user_id,
                    category=category,
                    spent=float(spent),
                    limit=float(budget_limit),
                    percentage=percentage
                )

                if alert:
                    alerts_sent.append(alert)

        except Exception as e:
            logger.error(f"Error checking budget alerts for user {user_id}: {e}")

        return alerts_sent

    def _check_category_alert(
        self,
        user_id: UUID,
        category: str,
        spent: float,
        limit: float,
        percentage: float
    ) -> Dict:
        """
        Check if an alert should be sent for a specific category

        Returns alert dict if sent, None otherwise
        """
        try:
            # Budget exceeded (critical alert)
            if percentage >= self.DANGER_THRESHOLD:
                overage = spent - limit
                self.notifier.notify_budget_exceeded(
                    user_id=user_id,
                    category=category,
                    spent=spent,
                    limit=limit,
                    overage=overage
                )
                logger.info(f"Budget exceeded alert sent for user {user_id}, category {category}")
                return {
                    "type": "exceeded",
                    "category": category,
                    "spent": spent,
                    "limit": limit,
                    "percentage": percentage
                }

            # Budget warning (80% threshold)
            elif percentage >= self.WARNING_THRESHOLD:
                self.notifier.notify_budget_warning(
                    user_id=user_id,
                    category=category,
                    spent=spent,
                    limit=limit,
                    percentage=percentage * 100
                )
                logger.info(f"Budget warning sent for user {user_id}, category {category}")
                return {
                    "type": "warning",
                    "category": category,
                    "spent": spent,
                    "limit": limit,
                    "percentage": percentage
                }

        except Exception as e:
            logger.error(f"Error sending budget alert: {e}")

        return None

    def check_single_category(
        self,
        user_id: UUID,
        category: str,
        spent_amount: Decimal,
        budget_limit: Decimal
    ) -> bool:
        """
        Check a single category immediately after a transaction
        Returns True if alert was sent
        """
        if budget_limit <= 0:
            return False

        percentage = float(spent_amount / budget_limit)

        alert = self._check_category_alert(
            user_id=user_id,
            category=category,
            spent=float(spent_amount),
            limit=float(budget_limit),
            percentage=percentage
        )

        return alert is not None

    def send_monthly_summary(
        self,
        user_id: UUID,
        year: int,
        month: int,
        category_budgets: Dict[str, Decimal]
    ) -> bool:
        """
        Send end-of-month budget summary
        Returns True if summary was sent successfully
        """
        try:
            tracker = BudgetTracker(self.db, user_id, year, month)
            spent_amounts = tracker.get_spent()

            total_budget = sum(category_budgets.values())
            total_spent = sum(spent_amounts.values())

            # Count categories over budget
            categories_over = 0
            for category, budget_limit in category_budgets.items():
                if budget_limit > 0:
                    spent = spent_amounts.get(category, Decimal('0.00'))
                    if spent > budget_limit:
                        categories_over += 1

            self.notifier.notify_monthly_budget_summary(
                user_id=user_id,
                total_spent=float(total_spent),
                total_budget=float(total_budget),
                categories_over=categories_over
            )

            logger.info(f"Monthly budget summary sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error sending monthly budget summary: {e}")
            return False

    def get_budget_status(
        self,
        user_id: UUID,
        year: int,
        month: int,
        category_budgets: Dict[str, Decimal]
    ) -> Dict[str, Dict]:
        """
        Get current budget status for all categories
        Useful for dashboard display

        Returns:
            Dict mapping category to status dict with spent, limit, percentage, status
        """
        status = {}

        try:
            tracker = BudgetTracker(self.db, user_id, year, month)
            spent_amounts = tracker.get_spent()

            for category, budget_limit in category_budgets.items():
                spent = spent_amounts.get(category, Decimal('0.00'))
                percentage = float(spent / budget_limit) if budget_limit > 0 else 0

                # Determine status
                if percentage >= 1.0:
                    budget_status = "exceeded"
                elif percentage >= 0.8:
                    budget_status = "warning"
                elif percentage >= 0.5:
                    budget_status = "moderate"
                else:
                    budget_status = "good"

                status[category] = {
                    "spent": float(spent),
                    "limit": float(budget_limit),
                    "remaining": float(budget_limit - spent),
                    "percentage": percentage,
                    "status": budget_status
                }

        except Exception as e:
            logger.error(f"Error getting budget status: {e}")

        return status


# Helper function for easy access
def get_budget_alert_service(db: Session) -> BudgetAlertService:
    """Get BudgetAlertService instance"""
    return BudgetAlertService(db)
