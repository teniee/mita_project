"""
Spending Prevention Service
Provides real-time budget validation BEFORE transaction creation
Implements MITA's core differentiator: preventive (not reactive) overspending protection
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models.daily_plan import DailyPlan


class SpendingPreventionService:
    """
    Real-time spending prevention service
    Checks if user can afford a transaction BEFORE creating it
    """

    # Warning level thresholds
    SAFE_THRESHOLD = 0.70  # Under 70% of budget = safe (green)
    CAUTION_THRESHOLD = 0.90  # 70-90% of budget = caution (yellow)
    DANGER_THRESHOLD = 1.00  # 90-100% of budget = danger (orange)
    # Over 100% = blocked (red)

    def __init__(self, db: Session, user_id: UUID):
        self.db = db
        self.user_id = user_id

    def check_affordability(
        self,
        category: str,
        amount: Decimal,
        transaction_date: Optional[datetime] = None
    ) -> Dict:
        """
        Check if user can afford transaction BEFORE creating it

        Returns:
        {
            "can_afford": bool,
            "warning_level": "safe" | "caution" | "danger" | "blocked",
            "current_spent": Decimal,
            "daily_budget": Decimal,
            "remaining_budget": Decimal,
            "percentage_used": float,
            "overage": Decimal,  # How much over budget (if any)
            "impact_message": str,
            "alternative_categories": [
                {"category": str, "available": Decimal, "percentage_free": float}
            ],
            "suggestions": [str],  # Actionable suggestions
            "allow_override": bool  # Can user proceed anyway?
        }
        """
        if transaction_date is None:
            transaction_date = datetime.now()

        trans_date = transaction_date.date() if isinstance(transaction_date, datetime) else transaction_date

        # Get today's daily plan for this category
        daily_plan = self.db.query(DailyPlan).filter(
            and_(
                DailyPlan.user_id == self.user_id,
                DailyPlan.date == trans_date,
                DailyPlan.category == category
            )
        ).first()

        # If no daily plan exists, can't validate (allow with warning)
        if not daily_plan:
            return self._build_no_budget_response(category, amount)

        daily_budget = Decimal(str(daily_plan.daily_budget or 0))
        current_spent = Decimal(str(daily_plan.spent_amount or 0))

        # Calculate impact
        new_total = current_spent + amount
        remaining = daily_budget - new_total
        percentage_used = float((new_total / daily_budget * 100)) if daily_budget > 0 else 999.0
        overage = max(Decimal(0), new_total - daily_budget)

        # Determine warning level
        warning_level = self._calculate_warning_level(new_total, daily_budget)
        can_afford = warning_level in ['safe', 'caution']

        # Get alternative categories with available budget
        alternatives = self._find_alternative_categories(trans_date, amount)

        # Generate actionable suggestions
        suggestions = self._generate_suggestions(
            category=category,
            amount=amount,
            overage=overage,
            alternatives=alternatives,
            daily_budget=daily_budget,
            remaining=remaining
        )

        # Generate impact message
        impact_message = self._generate_impact_message(
            warning_level=warning_level,
            category=category,
            remaining=remaining,
            overage=overage,
            percentage_used=percentage_used
        )

        return {
            "can_afford": can_afford,
            "warning_level": warning_level,
            "current_spent": float(current_spent),
            "daily_budget": float(daily_budget),
            "remaining_budget": float(remaining),
            "percentage_used": round(percentage_used, 1),
            "overage": float(overage),
            "impact_message": impact_message,
            "alternative_categories": alternatives,
            "suggestions": suggestions,
            "allow_override": True,  # Always allow override (user has final say)
            "category": category,
            "amount": float(amount)
        }

    def _calculate_warning_level(self, new_total: Decimal, daily_budget: Decimal) -> str:
        """Calculate warning level based on budget usage"""
        if daily_budget <= 0:
            return "safe"  # No budget set

        usage_ratio = float(new_total / daily_budget)

        if usage_ratio < self.SAFE_THRESHOLD:
            return "safe"
        elif usage_ratio < self.CAUTION_THRESHOLD:
            return "caution"
        elif usage_ratio < self.DANGER_THRESHOLD:
            return "danger"
        else:
            return "blocked"

    def _find_alternative_categories(
        self,
        transaction_date: date,
        amount: Decimal
    ) -> List[Dict]:
        """
        Find categories with enough available budget for this transaction
        Returns top 3 alternatives sorted by available amount
        """
        daily_plans = self.db.query(DailyPlan).filter(
            and_(
                DailyPlan.user_id == self.user_id,
                DailyPlan.date == transaction_date
            )
        ).all()

        alternatives = []
        for plan in daily_plans:
            daily_budget = Decimal(str(plan.daily_budget or 0))
            spent = Decimal(str(plan.spent_amount or 0))
            available = daily_budget - spent

            if available >= amount:  # Has enough budget
                percentage_free = float((available / daily_budget * 100)) if daily_budget > 0 else 0
                alternatives.append({
                    "category": plan.category,
                    "available": float(available),
                    "percentage_free": round(percentage_free, 1),
                    "daily_budget": float(daily_budget)
                })

        # Sort by available amount (descending)
        alternatives.sort(key=lambda x: x['available'], reverse=True)
        return alternatives[:3]  # Top 3

    def _generate_suggestions(
        self,
        category: str,
        amount: Decimal,
        overage: Decimal,
        alternatives: List[Dict],
        daily_budget: Decimal,
        remaining: Decimal
    ) -> List[str]:
        """Generate actionable suggestions for user"""
        suggestions = []

        if overage > 0:
            # Over budget - suggest alternatives
            if alternatives:
                top_alt = alternatives[0]
                suggestions.append(
                    f"Use '{top_alt['category']}' category instead (${top_alt['available']:.2f} available)"
                )

            # Suggest reducing amount
            if remaining > 0:
                suggestions.append(
                    f"Reduce amount to ${float(daily_budget - (amount - remaining)):.2f} to stay within budget"
                )

            # Suggest splitting transaction
            if len(alternatives) >= 2:
                suggestions.append(
                    f"Split between '{category}' and '{alternatives[0]['category']}'"
                )

            # Suggest waiting
            suggestions.append(
                "Wait until tomorrow when daily budget resets"
            )

        else:
            # Within budget - suggest being mindful
            if remaining < amount:
                suggestions.append(
                    f"This will leave only ${float(remaining - amount):.2f} for {category} today"
                )

        return suggestions[:3]  # Max 3 suggestions

    def _generate_impact_message(
        self,
        warning_level: str,
        category: str,
        remaining: Decimal,
        overage: Decimal,
        percentage_used: float
    ) -> str:
        """Generate human-readable impact message"""
        if warning_level == "safe":
            return f"✅ Safe to spend. You'll have ${float(remaining):.2f} left in {category} today."

        elif warning_level == "caution":
            return f"⚠️ This will use {percentage_used:.0f}% of your {category} budget. ${float(remaining):.2f} remaining."

        elif warning_level == "danger":
            return f"🟠 Warning! This will leave only ${float(remaining):.2f} in {category} today ({percentage_used:.0f}% used)."

        else:  # blocked
            return f"🔴 This will exceed your {category} budget by ${float(overage):.2f}!"

    def _build_no_budget_response(self, category: str, amount: Decimal) -> Dict:
        """Response when no budget exists for category"""
        return {
            "can_afford": True,  # Allow but warn
            "warning_level": "caution",
            "current_spent": 0.0,
            "daily_budget": 0.0,
            "remaining_budget": 0.0,
            "percentage_used": 0.0,
            "overage": 0.0,
            "impact_message": f"⚠️ No budget set for '{category}'. Consider setting a daily budget.",
            "alternative_categories": [],
            "suggestions": [
                f"Set a daily budget for '{category}' in settings",
                "Use automatic budget suggestions from AI"
            ],
            "allow_override": True,
            "category": category,
            "amount": float(amount)
        }

    def get_all_category_status(self, transaction_date: Optional[date] = None) -> Dict[str, Dict]:
        """
        Get current budget status for ALL categories
        Useful for dashboard/overview screens

        Returns:
        {
            "food": {
                "daily_budget": 50.00,
                "spent": 35.00,
                "remaining": 15.00,
                "percentage_used": 70.0,
                "status": "caution"
            },
            ...
        }
        """
        if transaction_date is None:
            transaction_date = date.today()

        daily_plans = self.db.query(DailyPlan).filter(
            and_(
                DailyPlan.user_id == self.user_id,
                DailyPlan.date == transaction_date
            )
        ).all()

        result = {}
        for plan in daily_plans:
            daily_budget = Decimal(str(plan.daily_budget or 0))
            spent = Decimal(str(plan.spent_amount or 0))
            remaining = daily_budget - spent
            percentage = float((spent / daily_budget * 100)) if daily_budget > 0 else 0

            # Determine status color
            if percentage < 70:
                status = "safe"
            elif percentage < 90:
                status = "caution"
            elif percentage < 100:
                status = "danger"
            else:
                status = "over_budget"

            result[plan.category] = {
                "daily_budget": float(daily_budget),
                "spent": float(spent),
                "remaining": float(remaining),
                "percentage_used": round(percentage, 1),
                "status": status
            }

        return result
