"""
MODULE 5: Smart Goal Advisor Service
AI-powered goal recommendations and insights based on user behavior and spending patterns
"""

from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta, date
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from app.db.models import Goal, Transaction, User, Budget
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SmartGoalAdvisor:
    """AI-powered service for intelligent goal recommendations and insights"""

    def __init__(self, db: Session):
        self.db = db

    def generate_personalized_recommendations(
        self,
        user_id: UUID
    ) -> List[Dict]:
        """
        Generate personalized goal recommendations based on user's:
        - Income level
        - Spending patterns
        - Existing goals
        - Historical behavior
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        recommendations = []

        # Get user's existing goals
        existing_goals = self.db.query(Goal).filter(
            Goal.user_id == user_id,
            Goal.status.in_(['active', 'paused'])
        ).all()

        existing_categories = {g.category for g in existing_goals if g.category}

        # Analyze spending patterns
        spending_analysis = self._analyze_spending_patterns(user_id)
        monthly_income = float(user.monthly_income or 3000)

        # 1. Emergency Fund (if not exists)
        if 'Emergency' not in existing_categories:
            recommendations.append(self._recommend_emergency_fund(monthly_income))

        # 2. Savings Goal (if not exists or if user can afford more)
        if 'Savings' not in existing_categories or monthly_income > 5000:
            recommendations.append(self._recommend_general_savings(monthly_income, spending_analysis))

        # 3. Debt Payoff (if high interest spending detected)
        if spending_analysis.get('high_interest_indicators', False):
            recommendations.append(self._recommend_debt_payoff(monthly_income))

        # 4. Category-specific goals based on spending
        category_recs = self._recommend_category_goals(spending_analysis, existing_categories, monthly_income)
        recommendations.extend(category_recs)

        # 5. Investment goal (for higher income users)
        if monthly_income > 4000 and 'Investment' not in existing_categories:
            recommendations.append(self._recommend_investment(monthly_income))

        # Sort by priority score
        recommendations.sort(key=lambda x: x.get('priority_score', 0), reverse=True)

        return recommendations[:5]  # Return top 5

    def analyze_goal_health(self, goal_id: UUID, user_id: UUID) -> Dict:
        """
        Analyze the health of a goal and provide insights
        """
        goal = self.db.query(Goal).filter(
            Goal.id == goal_id,
            Goal.user_id == user_id
        ).first()

        if not goal:
            return {"error": "Goal not found"}

        insights = {
            "goal_id": str(goal.id),
            "goal_title": goal.title,
            "health_score": 0,  # 0-100
            "status": goal.status,
            "insights": [],
            "recommendations": [],
            "predicted_completion_date": None,
            "on_track": False
        }

        # Calculate health score
        progress = float(goal.progress)
        days_since_created = (datetime.utcnow() - goal.created_at).days

        if goal.target_date:
            total_days = (goal.target_date - goal.created_at.date()).days
            days_remaining = (goal.target_date - date.today()).days

            if total_days > 0:
                expected_progress = ((total_days - days_remaining) / total_days) * 100
                progress_ratio = progress / expected_progress if expected_progress > 0 else 0

                insights["on_track"] = progress_ratio >= 0.9
                insights["health_score"] = min(100, int(progress_ratio * 100))

                # Predict completion date
                if progress > 0 and days_since_created > 0:
                    daily_progress = progress / days_since_created
                    remaining_progress = 100 - progress
                    days_to_completion = int(remaining_progress / daily_progress) if daily_progress > 0 else 0
                    predicted_date = date.today() + timedelta(days=days_to_completion)
                    insights["predicted_completion_date"] = predicted_date.isoformat()

                    # Check if predicted date is after target
                    if predicted_date > goal.target_date:
                        days_late = (predicted_date - goal.target_date).days
                        insights["insights"].append(
                            f"⚠️ At current pace, you'll complete this {days_late} days late"
                        )
                        insights["recommendations"].append(
                            f"Consider increasing monthly savings by ${float(goal.monthly_contribution or 0) * 0.3:.2f}"
                        )
                    else:
                        insights["insights"].append(
                            "✅ You're on track to meet your deadline!"
                        )
            else:
                insights["health_score"] = int(progress)
        else:
            # No deadline, base health on progress only
            insights["health_score"] = int(progress)
            insights["recommendations"].append(
                "📅 Set a target date to stay motivated and track progress better"
            )

        # Check monthly contribution adequacy
        if goal.monthly_contribution and goal.target_date:
            months_remaining = ((goal.target_date.year - date.today().year) * 12 +
                              goal.target_date.month - date.today().month)
            if months_remaining > 0:
                required_monthly = float(goal.remaining_amount) / months_remaining
                current_monthly = float(goal.monthly_contribution)

                if current_monthly < required_monthly:
                    shortfall = required_monthly - current_monthly
                    insights["recommendations"].append(
                        f"💡 Increase monthly contribution by ${shortfall:.2f} to reach your goal on time"
                    )

        # Recent activity check
        transactions = self.db.query(Transaction).filter(
            Transaction.goal_id == goal_id,
            Transaction.user_id == user_id
        ).order_by(desc(Transaction.spent_at)).limit(5).all()

        if transactions:
            last_transaction_date = transactions[0].spent_at
            days_since_last = (datetime.utcnow() - last_transaction_date).days

            if days_since_last > 30:
                insights["insights"].append(
                    f"⏰ No savings added in {days_since_last} days"
                )
                insights["recommendations"].append(
                    "📌 Set up automatic transfers to keep your goal moving forward"
                )
        else:
            insights["recommendations"].append(
                "💸 Start adding savings to build momentum!"
            )

        return insights

    def suggest_goal_adjustments(self, user_id: UUID) -> List[Dict]:
        """
        Suggest adjustments to existing goals based on user's current situation
        """
        suggestions = []

        # Get active goals
        goals = self.db.query(Goal).filter(
            Goal.user_id == user_id,
            Goal.status == 'active'
        ).all()

        user = self.db.query(User).filter(User.id == user_id).first()
        monthly_income = float(user.monthly_income or 3000) if user else 3000

        # Analyze recent spending to determine available funds
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_spending = self.db.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= thirty_days_ago,
            Transaction.amount < 0  # Expenses are negative
        ).scalar() or Decimal('0')

        monthly_expenses = abs(float(recent_spending))
        available_for_goals = monthly_income - monthly_expenses

        for goal in goals:
            health = self.analyze_goal_health(goal.id, user_id)

            if health["health_score"] < 70:
                suggestions.append({
                    "goal_id": str(goal.id),
                    "goal_title": goal.title,
                    "type": "adjustment",
                    "current_monthly": float(goal.monthly_contribution or 0),
                    "suggested_monthly": min(
                        float(goal.monthly_contribution or 0) * 1.3,
                        available_for_goals * 0.3
                    ),
                    "reason": "Goal is falling behind schedule",
                    "health_score": health["health_score"]
                })

        return suggestions

    def detect_goal_opportunities(self, user_id: UUID) -> List[Dict]:
        """
        Detect opportunities for new goals based on spending patterns
        """
        opportunities = []
        spending_analysis = self._analyze_spending_patterns(user_id)

        # Opportunity 1: Large recurring expenses → dedicated savings goal
        for category, data in spending_analysis.get('recurring_expenses', {}).items():
            if data['average'] > 200:
                opportunities.append({
                    "type": "recurring_expense_goal",
                    "category": category,
                    "suggested_goal": f"{category} Annual Budget",
                    "target_amount": data['average'] * 12,
                    "monthly_contribution": data['average'],
                    "reason": f"You spend an average of ${data['average']:.2f}/month on {category}. "
                             f"Consider setting aside funds in advance."
                })

        # Opportunity 2: Consistent underspending in a category → savings goal
        for category, data in spending_analysis.get('underspending_categories', {}).items():
            surplus = data.get('surplus', 0)
            if surplus > 100:
                opportunities.append({
                    "type": "surplus_savings_goal",
                    "category": category,
                    "suggested_goal": f"Surplus from {category}",
                    "target_amount": surplus * 12,
                    "monthly_contribution": surplus,
                    "reason": f"You typically have ${surplus:.2f} left over in {category}. "
                             f"Turn this into savings!"
                })

        return opportunities

    def _analyze_spending_patterns(self, user_id: UUID) -> Dict:
        """Analyze user's spending patterns over last 3 months"""
        three_months_ago = datetime.utcnow() - timedelta(days=90)

        transactions = self.db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= three_months_ago
        ).all()

        analysis = {
            'total_spending': 0,
            'recurring_expenses': {},
            'underspending_categories': {},
            'high_interest_indicators': False,
            'average_monthly_spending': 0
        }

        if not transactions:
            return analysis

        # Calculate totals and averages by category
        category_spending = {}
        for txn in transactions:
            if txn.amount < 0:  # Expenses
                cat = txn.category or 'Other'
                if cat not in category_spending:
                    category_spending[cat] = []
                category_spending[cat].append(abs(float(txn.amount)))

        # Analyze each category
        for category, amounts in category_spending.items():
            avg = sum(amounts) / len(amounts)
            if len(amounts) >= 3:  # At least 3 transactions
                analysis['recurring_expenses'][category] = {
                    'average': avg,
                    'count': len(amounts),
                    'total': sum(amounts)
                }

        # Calculate total and average
        all_expenses = [abs(float(t.amount)) for t in transactions if t.amount < 0]
        if all_expenses:
            analysis['total_spending'] = sum(all_expenses)
            analysis['average_monthly_spending'] = analysis['total_spending'] / 3

        # Detect high-interest indicators (lots of small transactions, subscription services)
        small_recurring = [t for t in transactions if abs(float(t.amount)) < 50 and t.category in ['Subscriptions', 'Services']]
        analysis['high_interest_indicators'] = len(small_recurring) > 10

        return analysis

    def _recommend_emergency_fund(self, monthly_income: float) -> Dict:
        target = monthly_income * 6  # 6 months of expenses
        return {
            "type": "emergency_fund",
            "title": "Emergency Fund",
            "category": "Emergency",
            "target_amount": target,
            "monthly_contribution": monthly_income * 0.10,
            "priority": "high",
            "priority_score": 100,
            "description": f"Build a 6-month emergency fund (${target:,.0f}) for financial security",
            "reasoning": "Essential financial safety net. Experts recommend 6 months of expenses.",
            "suggested_deadline": (date.today() + timedelta(days=730)).isoformat()  # 2 years
        }

    def _recommend_general_savings(self, monthly_income: float, spending_analysis: Dict) -> Dict:
        target = monthly_income * 3  # 3 months of income
        contribution = monthly_income * 0.15
        return {
            "type": "general_savings",
            "title": "Monthly Savings Goal",
            "category": "Savings",
            "target_amount": target,
            "monthly_contribution": contribution,
            "priority": "high",
            "priority_score": 90,
            "description": "Build up your savings with consistent monthly contributions",
            "reasoning": "Following the 50/30/20 rule, aim to save 20% of your income",
            "suggested_deadline": (date.today() + timedelta(days=365)).isoformat()  # 1 year
        }

    def _recommend_debt_payoff(self, monthly_income: float) -> Dict:
        target = min(monthly_income * 2, 5000)  # Reasonable debt payoff goal
        return {
            "type": "debt_payoff",
            "title": "Debt Payoff Goal",
            "category": "Savings",
            "target_amount": target,
            "monthly_contribution": monthly_income * 0.15,
            "priority": "high",
            "priority_score": 95,
            "description": f"Pay off ${target:,.0f} in high-interest debt",
            "reasoning": "Reducing debt improves financial health and saves on interest",
            "suggested_deadline": (date.today() + timedelta(days=365)).isoformat()
        }

    def _recommend_category_goals(
        self,
        spending_analysis: Dict,
        existing_categories: set,
        monthly_income: float
    ) -> List[Dict]:
        """Recommend goals based on spending patterns"""
        recommendations = []

        # Travel goal if user has travel expenses
        travel_spending = spending_analysis.get('recurring_expenses', {}).get('Travel', {})
        if travel_spending and 'Travel' not in existing_categories:
            avg_travel = travel_spending.get('average', 0)
            if avg_travel > 50:
                recommendations.append({
                    "type": "travel",
                    "title": "Vacation Fund",
                    "category": "Travel",
                    "target_amount": avg_travel * 12,
                    "monthly_contribution": avg_travel,
                    "priority": "medium",
                    "priority_score": 60,
                    "description": f"Save for your next adventure (${avg_travel * 12:,.0f})",
                    "reasoning": f"Based on your average travel spending of ${avg_travel:.2f}/month",
                    "suggested_deadline": (date.today() + timedelta(days=365)).isoformat()
                })

        # Technology upgrade (if income > 3000)
        if monthly_income > 3000 and 'Technology' not in existing_categories:
            recommendations.append({
                "type": "technology",
                "title": "Technology Upgrade",
                "category": "Technology",
                "target_amount": 1500,
                "monthly_contribution": monthly_income * 0.03,
                "priority": "low",
                "priority_score": 40,
                "description": "Save for new laptop, phone, or other tech",
                "reasoning": "Stay up-to-date with technology without financial stress",
                "suggested_deadline": (date.today() + timedelta(days=365)).isoformat()
            })

        # Education (if income > 4000)
        if monthly_income > 4000 and 'Education' not in existing_categories:
            recommendations.append({
                "type": "education",
                "title": "Professional Development",
                "category": "Education",
                "target_amount": 2000,
                "monthly_contribution": monthly_income * 0.05,
                "priority": "medium",
                "priority_score": 70,
                "description": "Invest in courses, certifications, or skills",
                "reasoning": "Continuous learning increases earning potential",
                "suggested_deadline": (date.today() + timedelta(days=365)).isoformat()
            })

        return recommendations

    def _recommend_investment(self, monthly_income: float) -> Dict:
        target = monthly_income * 12  # 1 year of income
        contribution = monthly_income * 0.10
        return {
            "type": "investment",
            "title": "Investment Fund",
            "category": "Investment",
            "target_amount": target,
            "monthly_contribution": contribution,
            "priority": "medium",
            "priority_score": 75,
            "description": f"Start building wealth through investments (${target:,.0f})",
            "reasoning": "With your income level, investing can accelerate wealth building",
            "suggested_deadline": (date.today() + timedelta(days=730)).isoformat()  # 2 years
        }


def get_smart_goal_advisor(db: Session) -> SmartGoalAdvisor:
    """Get Smart Goal Advisor instance"""
    return SmartGoalAdvisor(db)
