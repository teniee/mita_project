"""
Notification Templates System
Provides ready-to-use notification templates for different events
"""
from typing import Dict, Any, Optional


class NotificationTemplates:
    """
    Centralized notification templates for all app events
    Provides consistent messaging across the application
    """

    # ============================================================================
    # GOAL NOTIFICATIONS
    # ============================================================================

    @staticmethod
    def goal_created(goal_title: str, target_amount: float) -> Dict[str, Any]:
        """Notification when a new goal is created"""
        return {
            "title": "🎯 New Goal Created!",
            "message": f"You've created a new goal: {goal_title}. Target: ${target_amount:,.2f}",
            "type": "info",
            "priority": "medium",
            "category": "goal_updates",
        }

    @staticmethod
    def goal_progress_milestone(
        goal_title: str,
        progress: float,
        saved_amount: float,
        target_amount: float
    ) -> Dict[str, Any]:
        """Notification when goal reaches milestone (25%, 50%, 75%, 90%)"""
        emoji_map = {
            25: "🌱",
            50: "🚀",
            75: "🔥",
            90: "⭐",
        }
        emoji = emoji_map.get(int(progress), "🎯")

        return {
            "title": f"{emoji} Goal Progress: {progress:.0f}%",
            "message": f"Great work! You've saved ${saved_amount:,.2f} of ${target_amount:,.2f} for '{goal_title}'",
            "type": "achievement",
            "priority": "high" if progress >= 75 else "medium",
            "category": "goal_updates",
        }

    @staticmethod
    def goal_completed(
        goal_title: str,
        final_amount: float,
        days_taken: Optional[int] = None
    ) -> Dict[str, Any]:
        """Notification when goal is completed"""
        time_msg = f" in {days_taken} days" if days_taken else ""
        return {
            "title": "🎉 Goal Achieved!",
            "message": f"Congratulations! You've completed '{goal_title}' and saved ${final_amount:,.2f}{time_msg}!",
            "type": "achievement",
            "priority": "high",
            "category": "goal_updates",
            "data": {"celebration": True, "confetti": True},
        }

    @staticmethod
    def goal_overdue(goal_title: str, days_overdue: int) -> Dict[str, Any]:
        """Notification when goal is overdue"""
        return {
            "title": "⏰ Goal Deadline Passed",
            "message": f"Your goal '{goal_title}' was due {days_overdue} days ago. Consider adjusting the deadline or adding more savings.",
            "type": "reminder",
            "priority": "medium",
            "category": "goal_updates",
        }

    @staticmethod
    def goal_due_soon(goal_title: str, days_remaining: int, remaining_amount: float) -> Dict[str, Any]:
        """Notification when goal deadline is approaching"""
        return {
            "title": "⏳ Goal Deadline Approaching",
            "message": f"Your goal '{goal_title}' is due in {days_remaining} days. You still need ${remaining_amount:,.2f} to reach your target.",
            "type": "reminder",
            "priority": "high",
            "category": "goal_updates",
        }

    # ============================================================================
    # BUDGET NOTIFICATIONS
    # ============================================================================

    @staticmethod
    def budget_warning(category: str, spent: float, limit: float, percentage: float) -> Dict[str, Any]:
        """Warning when spending reaches 80% of budget"""
        return {
            "title": "⚠️ Budget Alert",
            "message": f"You've spent {percentage:.0f}% (${spent:,.2f} of ${limit:,.2f}) of your {category} budget this month.",
            "type": "warning",
            "priority": "high",
            "category": "budget_alerts",
        }

    @staticmethod
    def budget_exceeded(category: str, spent: float, limit: float, overage: float) -> Dict[str, Any]:
        """Alert when budget is exceeded"""
        return {
            "title": "🚨 Budget Exceeded!",
            "message": f"You've exceeded your {category} budget by ${overage:,.2f}. Total spent: ${spent:,.2f} (Limit: ${limit:,.2f})",
            "type": "alert",
            "priority": "critical",
            "category": "budget_alerts",
        }

    @staticmethod
    def budget_on_track(category: str, remaining: float) -> Dict[str, Any]:
        """Positive notification when budget is on track"""
        return {
            "title": "✅ Budget On Track",
            "message": f"Great job! You have ${remaining:,.2f} remaining in your {category} budget this month.",
            "type": "tip",
            "priority": "low",
            "category": "budget_alerts",
        }

    @staticmethod
    def monthly_budget_summary(
        total_spent: float,
        total_budget: float,
        categories_over: int
    ) -> Dict[str, Any]:
        """End of month budget summary"""
        percentage = (total_spent / total_budget * 100) if total_budget > 0 else 0

        return {
            "title": "📊 Monthly Budget Summary",
            "message": f"This month you spent ${total_spent:,.2f} of ${total_budget:,.2f} ({percentage:.0f}%). "
                      f"{categories_over} categories exceeded their limits." if categories_over > 0
                      else "All categories stayed within budget!",
            "type": "info",
            "priority": "medium",
            "category": "budget_alerts",
        }

    # ============================================================================
    # TRANSACTION NOTIFICATIONS
    # ============================================================================

    @staticmethod
    def large_transaction(amount: float, category: str, merchant: Optional[str] = None) -> Dict[str, Any]:
        """Notification for unusually large transactions"""
        merchant_text = f" at {merchant}" if merchant else ""
        return {
            "title": "💳 Large Transaction Detected",
            "message": f"You spent ${amount:,.2f} in {category}{merchant_text}. This is higher than your usual spending.",
            "type": "info",
            "priority": "medium",
            "category": "transaction_alerts",
        }

    @staticmethod
    def transaction_added_to_goal(amount: float, goal_title: str, new_progress: float) -> Dict[str, Any]:
        """Notification when transaction is linked to goal"""
        return {
            "title": "🎯 Savings Added to Goal",
            "message": f"${amount:,.2f} added to '{goal_title}'. Progress: {new_progress:.1f}%",
            "type": "info",
            "priority": "medium",
            "category": "transaction_alerts",
        }

    @staticmethod
    def recurring_transaction_detected(category: str, amount: float) -> Dict[str, Any]:
        """Notification when recurring pattern is detected"""
        return {
            "title": "🔄 Recurring Transaction Detected",
            "message": f"We noticed a recurring {category} transaction of ${amount:,.2f}. Would you like to set up automatic budgeting?",
            "type": "tip",
            "priority": "low",
            "category": "transaction_alerts",
        }

    # ============================================================================
    # AI & INSIGHTS NOTIFICATIONS
    # ============================================================================

    @staticmethod
    def ai_recommendation(recommendation: str, potential_savings: Optional[float] = None) -> Dict[str, Any]:
        """AI-generated recommendation"""
        savings_text = f" You could save ${potential_savings:,.2f} per month." if potential_savings else ""
        return {
            "title": "💡 Smart Recommendation",
            "message": f"{recommendation}{savings_text}",
            "type": "recommendation",
            "priority": "medium",
            "category": "ai_recommendations",
        }

    @staticmethod
    def spending_pattern_alert(insight: str) -> Dict[str, Any]:
        """Alert about unusual spending patterns"""
        return {
            "title": "📈 Spending Pattern Alert",
            "message": insight,
            "type": "info",
            "priority": "medium",
            "category": "ai_recommendations",
        }

    @staticmethod
    def savings_opportunity(category: str, amount: float) -> Dict[str, Any]:
        """Notification about potential savings"""
        return {
            "title": "💰 Savings Opportunity",
            "message": f"You could save ${amount:,.2f} by reducing your {category} spending by 20% this month.",
            "type": "tip",
            "priority": "medium",
            "category": "ai_recommendations",
        }

    # ============================================================================
    # DAILY REMINDERS & TIPS
    # ============================================================================

    @staticmethod
    def daily_budget_reminder(remaining_budget: float, days_left: int) -> Dict[str, Any]:
        """Daily reminder about remaining budget"""
        daily_allowance = remaining_budget / days_left if days_left > 0 else 0
        return {
            "title": "🌅 Daily Budget Update",
            "message": f"Good morning! You have ${remaining_budget:,.2f} remaining for {days_left} days. "
                      f"Daily allowance: ${daily_allowance:,.2f}",
            "type": "reminder",
            "priority": "low",
            "category": "daily_reminders",
        }

    @staticmethod
    def weekly_progress_report(
        goals_on_track: int,
        total_saved_this_week: float
    ) -> Dict[str, Any]:
        """Weekly progress summary"""
        return {
            "title": "📊 Weekly Progress Report",
            "message": f"This week: {goals_on_track} goals on track, ${total_saved_this_week:,.2f} saved. Keep it up!",
            "type": "info",
            "priority": "medium",
            "category": "daily_reminders",
        }

    @staticmethod
    def motivational_tip(tip: str) -> Dict[str, Any]:
        """Random motivational financial tip"""
        return {
            "title": "💪 Financial Tip",
            "message": tip,
            "type": "tip",
            "priority": "low",
            "category": "daily_reminders",
        }

    # ============================================================================
    # VELOCITY ALERT NOTIFICATIONS
    # ============================================================================

    @staticmethod
    def velocity_watch(
        category: str,
        velocity_ratio: float,
        days_until_exhausted: Optional[float],
    ) -> Dict[str, Any]:
        """Informational: spending slightly ahead of plan (1.2x – 1.49x)."""
        days_text = (
            f"budget runs out in ~{days_until_exhausted:.0f} days at this pace"
            if days_until_exhausted is not None and days_until_exhausted > 0
            else "budget is running low"
        )
        cat_display = category.replace("_", " ").title()
        return {
            "title": f"⚡ {cat_display} spending is ahead",
            "message": (
                f"You're spending {velocity_ratio:.1f}× faster than planned on "
                f"{cat_display}. {days_text.capitalize()}."
            ),
            "type": "warning",
            "priority": "medium",
            "category": "budget_alerts",
            "data": {
                "alert_subtype": "velocity_watch",
                "budget_category": category,
                "velocity_ratio": round(velocity_ratio, 2),
            },
        }

    @staticmethod
    def velocity_warning(
        category: str,
        velocity_ratio: float,
        days_until_exhausted: Optional[float],
        goal_title: Optional[str] = None,
        delay_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """High-priority: budget will exhaust significantly early (1.5x – 1.99x)."""
        cat_display = category.replace("_", " ").title()
        days_text = (
            f"Only ~{days_until_exhausted:.0f} days of {cat_display} budget left "
            "at current pace."
            if days_until_exhausted is not None and days_until_exhausted > 0
            else f"{cat_display} budget is nearly exhausted."
        )
        goal_text = ""
        if goal_title and delay_days and delay_days > 0:
            goal_text = (
                f" Your goal '{goal_title}' may be delayed ~{delay_days} days."
            )
        return {
            "title": f"⚠️ {cat_display} budget at risk",
            "message": (
                f"You're using your {cat_display} budget {velocity_ratio:.1f}× "
                f"faster than planned. {days_text}{goal_text}"
            ),
            "type": "warning",
            "priority": "high",
            "category": "budget_alerts",
            "data": {
                "alert_subtype": "velocity_warning",
                "budget_category": category,
                "velocity_ratio": round(velocity_ratio, 2),
                "days_until_exhausted": days_until_exhausted,
            },
        }

    @staticmethod
    def velocity_critical(
        category: str,
        velocity_ratio: float,
        days_until_exhausted: Optional[float],
        goal_title: Optional[str] = None,
        delay_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Critical: budget runs out very soon (2.0x+)."""
        cat_display = category.replace("_", " ").title()
        days_text = (
            f"in ~{days_until_exhausted:.0f} days"
            if days_until_exhausted is not None and days_until_exhausted > 0
            else "very soon"
        )
        goal_text = ""
        if goal_title and delay_days and delay_days > 0:
            goal_text = (
                f" This puts your goal '{goal_title}' at risk — "
                f"~{delay_days} day delay."
            )
        return {
            "title": f"🔴 {cat_display} budget running out fast",
            "message": (
                f"At current pace your {cat_display} budget runs out {days_text} — "
                f"{velocity_ratio:.1f}× faster than planned. "
                f"Reduce spending or rebalance now.{goal_text}"
            ),
            "type": "alert",
            "priority": "critical",
            "category": "budget_alerts",
            "data": {
                "alert_subtype": "velocity_critical",
                "budget_category": category,
                "velocity_ratio": round(velocity_ratio, 2),
                "days_until_exhausted": days_until_exhausted,
            },
        }

    @staticmethod
    def spending_win(
        win_type: str,
        streak_days: int,
        surplus_amount: float,
    ) -> Dict[str, Any]:
        """Positive: celebrate a budget win-streak."""
        streak_map = {
            "streak_7": ("🎯", "7-day budget streak!"),
            "streak_14": ("🔥", "14-day budget streak!"),
            "streak_30": ("⭐", "30-day budget streak!"),
        }
        emoji, title_suffix = streak_map.get(win_type, ("✅", f"{streak_days}-day streak!"))
        return {
            "title": f"{emoji} {title_suffix}",
            "message": (
                f"You've been under budget for {streak_days} days straight "
                f"and saved ${surplus_amount:,.2f} total. Keep it up!"
            ),
            "type": "achievement",
            "priority": "low",
            "category": "budget_alerts",
            "data": {
                "alert_subtype": win_type,
                "streak_days": streak_days,
                "surplus_amount": round(surplus_amount, 2),
                "celebration": True,
            },
        }

    # ============================================================================
    # SYSTEM & SECURITY NOTIFICATIONS
    # ============================================================================

    @staticmethod
    def account_activity(activity: str) -> Dict[str, Any]:
        """Notification about important account activity"""
        return {
            "title": "🔔 Account Activity",
            "message": activity,
            "type": "info",
            "priority": "high",
            "category": "system",
        }

    @staticmethod
    def security_alert(alert: str) -> Dict[str, Any]:
        """Security-related notifications"""
        return {
            "title": "🔒 Security Alert",
            "message": alert,
            "type": "alert",
            "priority": "critical",
            "category": "system",
        }

    @staticmethod
    def data_sync_complete() -> Dict[str, Any]:
        """Notification when data sync completes"""
        return {
            "title": "✅ Data Synced",
            "message": "Your financial data has been successfully synced across all devices.",
            "type": "info",
            "priority": "low",
            "category": "system",
        }


# Motivational tips pool
FINANCIAL_TIPS = [
    "Track every expense, no matter how small. Small leaks sink big ships!",
    "The 50/30/20 rule: 50% needs, 30% wants, 20% savings and debt repayment.",
    "Pay yourself first - automate your savings before spending on anything else.",
    "Review your subscriptions monthly. Cancel what you don't use.",
    "Use the 24-hour rule for non-essential purchases over $50.",
    "Build an emergency fund covering 3-6 months of expenses.",
    "Invest in experiences, not things. Memories last longer than material goods.",
    "Comparison shop for big purchases. A few minutes can save hundreds.",
    "Cook at home more often. Restaurant meals cost 3-5x more than home-cooked.",
    "Set specific, measurable financial goals. Vague goals lead to vague results.",
]
