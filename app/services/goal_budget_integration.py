"""
MODULE 5: Goal-Budget Integration Service
Automatically integrates goals with budget system for seamless fund allocation
"""

from typing import Dict, List, Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.db.models import Goal, Budget, Transaction, User
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GoalBudgetIntegration:
    """Service for integrating goals with budget system"""

    def __init__(self, db: Session):
        self.db = db

    def allocate_budget_for_goals(
        self,
        user_id: UUID,
        month: int,
        year: int
    ) -> Dict:
        """
        Automatically allocate budget for active goals from user's monthly income

        Returns:
            Dict with allocation details and recommendations
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.monthly_income:
            return {"error": "User or monthly income not found"}

        monthly_income = float(user.monthly_income)

        # Get active goals
        active_goals = self.db.query(Goal).filter(
            Goal.user_id == user_id,
            Goal.status == 'active'
        ).all()

        if not active_goals:
            return {
                "allocated": 0,
                "goals_count": 0,
                "message": "No active goals to allocate budget for"
            }

        # Calculate total goal contributions needed
        total_goal_contributions = sum(
            float(goal.monthly_contribution or 0) for goal in active_goals
        )

        # Check if user has enough income for goals
        existing_expenses = self._get_monthly_expenses(user_id, month, year)
        available_for_goals = monthly_income - existing_expenses

        allocation_result = {
            "monthly_income": monthly_income,
            "existing_expenses": existing_expenses,
            "available_for_goals": available_for_goals,
            "requested_for_goals": total_goal_contributions,
            "goals_count": len(active_goals),
            "allocations": [],
            "warnings": []
        }

        # If requested amount exceeds available, calculate proportional allocation
        if total_goal_contributions > available_for_goals:
            allocation_result["warnings"].append(
                f"Requested ${total_goal_contributions:.2f} exceeds available ${available_for_goals:.2f}. "
                f"Allocating proportionally."
            )
            allocation_ratio = available_for_goals / total_goal_contributions if total_goal_contributions > 0 else 0
        else:
            allocation_ratio = 1.0

        # Allocate to each goal
        for goal in active_goals:
            contribution = float(goal.monthly_contribution or 0) * allocation_ratio
            allocation_result["allocations"].append({
                "goal_id": str(goal.id),
                "goal_title": goal.title,
                "requested": float(goal.monthly_contribution or 0),
                "allocated": round(contribution, 2),
                "priority": goal.priority
            })

        return allocation_result

    def create_goal_savings_categories(self, user_id: UUID) -> List[Dict]:
        """
        Create/update budget categories for active goals

        Returns:
            List of created/updated budget categories
        """
        active_goals = self.db.query(Goal).filter(
            Goal.user_id == user_id,
            Goal.status == 'active'
        ).all()

        categories = []
        for goal in active_goals:
            category_name = f"Goal: {goal.title}"
            monthly_amount = float(goal.monthly_contribution or 0)

            categories.append({
                "goal_id": str(goal.id),
                "category_name": category_name,
                "monthly_amount": monthly_amount,
                "priority": goal.priority
            })

        return categories

    def track_goal_progress_from_budget(
        self,
        user_id: UUID,
        month: int,
        year: int
    ) -> Dict:
        """
        Track goal progress based on budget allocations and actual spending

        Returns:
            Progress report for all goals
        """
        active_goals = self.db.query(Goal).filter(
            Goal.user_id == user_id,
            Goal.status == 'active'
        ).all()

        progress_report = {
            "month": month,
            "year": year,
            "goals": []
        }

        for goal in active_goals:
            # Get transactions linked to this goal for the month
            first_day = date(year, month, 1)
            if month == 12:
                last_day = date(year + 1, 1, 1)
            else:
                last_day = date(year, month + 1, 1)

            monthly_savings = self.db.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.goal_id == goal.id,
                Transaction.user_id == user_id,
                Transaction.spent_at >= first_day,
                Transaction.spent_at < last_day
            ).scalar() or Decimal('0')

            expected_contribution = float(goal.monthly_contribution or 0)
            actual_contribution = abs(float(monthly_savings))

            progress_report["goals"].append({
                "goal_id": str(goal.id),
                "goal_title": goal.title,
                "expected_contribution": expected_contribution,
                "actual_contribution": actual_contribution,
                "difference": actual_contribution - expected_contribution,
                "on_track": actual_contribution >= expected_contribution * 0.9,  # 90% threshold
                "progress_percentage": float(goal.progress)
            })

        return progress_report

    def suggest_budget_adjustments_for_goals(self, user_id: UUID) -> List[Dict]:
        """
        Suggest budget adjustments to better support goal progress

        Returns:
            List of suggested adjustments
        """
        suggestions = []

        active_goals = self.db.query(Goal).filter(
            Goal.user_id == user_id,
            Goal.status == 'active'
        ).all()

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.monthly_income:
            return suggestions

        monthly_income = float(user.monthly_income)

        # Analyze each goal's progress
        for goal in active_goals:
            if goal.target_date and goal.monthly_contribution:
                months_remaining = self._calculate_months_remaining(goal.target_date)

                if months_remaining > 0:
                    remaining_amount = float(goal.remaining_amount)
                    required_monthly = remaining_amount / months_remaining
                    current_monthly = float(goal.monthly_contribution)

                    if required_monthly > current_monthly * 1.1:  # 10% threshold
                        shortfall = required_monthly - current_monthly
                        suggestions.append({
                            "goal_id": str(goal.id),
                            "goal_title": goal.title,
                            "type": "increase_contribution",
                            "current_monthly": current_monthly,
                            "required_monthly": required_monthly,
                            "increase_needed": shortfall,
                            "reason": f"To reach target by {goal.target_date}, increase monthly contribution",
                            "feasible": shortfall <= (monthly_income * 0.05)  # Within 5% of income
                        })

        # Check for underfunded goals
        for goal in active_goals:
            if not goal.monthly_contribution or float(goal.monthly_contribution) == 0:
                # Suggest a reasonable contribution
                target = float(goal.target_amount)
                suggested_monthly = min(target / 12, monthly_income * 0.05)  # 5% of income or 1/12 of target

                suggestions.append({
                    "goal_id": str(goal.id),
                    "goal_title": goal.title,
                    "type": "set_contribution",
                    "suggested_monthly": suggested_monthly,
                    "reason": "No monthly contribution set for this goal",
                    "feasible": True
                })

        return suggestions

    def auto_transfer_to_savings_goal(
        self,
        user_id: UUID,
        goal_id: UUID,
        amount: Decimal
    ) -> Dict:
        """
        Automatically create a savings transaction for a goal

        Returns:
            Transaction details
        """
        goal = self.db.query(Goal).filter(
            Goal.id == goal_id,
            Goal.user_id == user_id
        ).first()

        if not goal:
            return {"error": "Goal not found"}

        if goal.status != 'active':
            return {"error": "Goal is not active"}

        try:
            # Create a savings transaction
            transaction = Transaction(
                user_id=user_id,
                goal_id=goal_id,
                amount=abs(float(amount)),  # Positive for savings
                category="Savings",
                description=f"Automatic savings for goal: {goal.title}",
                spent_at=datetime.utcnow(),
                source="auto_goal_transfer"
            )

            self.db.add(transaction)

            # Update goal progress
            goal.add_savings(amount)

            self.db.commit()
            self.db.refresh(goal)
            self.db.refresh(transaction)

            return {
                "success": True,
                "transaction_id": str(transaction.id),
                "goal_title": goal.title,
                "amount": float(amount),
                "new_saved_amount": float(goal.saved_amount),
                "new_progress": float(goal.progress)
            }

        except Exception as e:
            logger.error(f"Error auto-transferring to goal: {e}", exc_info=True)
            self.db.rollback()
            return {"error": str(e)}

    def _get_monthly_expenses(self, user_id: UUID, month: int, year: int) -> float:
        """Calculate total expenses for a given month"""
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1)
        else:
            last_day = date(year, month + 1, 1)

        total_expenses = self.db.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= first_day,
            Transaction.spent_at < last_day,
            Transaction.amount < 0  # Expenses are negative
        ).scalar() or Decimal('0')

        return abs(float(total_expenses))

    def _calculate_months_remaining(self, target_date: date) -> int:
        """Calculate months remaining until target date"""
        today = date.today()
        if target_date <= today:
            return 0

        months = (target_date.year - today.year) * 12 + target_date.month - today.month
        return max(0, months)


def get_goal_budget_integration(db: Session) -> GoalBudgetIntegration:
    """Get Goal-Budget Integration service instance"""
    return GoalBudgetIntegration(db)
