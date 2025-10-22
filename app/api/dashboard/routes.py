"""
Dashboard API Routes for MITA Main Screen

Provides comprehensive dashboard data including:
- Current balance and spending
- Daily budget targets by category
- Recent transactions
- Weekly spending overview
- AI insights preview
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract, func

from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.user import User
from app.db.models import Transaction, DailyPlan
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive dashboard data for Main Screen

    Returns:
    - balance: Current available balance
    - spent: Amount spent today
    - daily_targets: Budget targets by category with current spending
    - week: Weekly spending status overview
    - transactions: Recent transactions (last 10)
    - insights_preview: Preview of AI insights
    """
    try:
        user_id = user.id
        today = datetime.now().date()
        now = datetime.now()

        # Get user's monthly income
        monthly_income = float(user.monthly_income) if user.monthly_income else 0.0

        # Calculate current balance (simplified - should be based on actual account balance)
        # For now: monthly_income - spent_this_month
        first_day_of_month = today.replace(day=1)

        total_spent_this_month = db.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= first_day_of_month,
            Transaction.spent_at < now
        ).scalar() or 0.0

        current_balance = monthly_income - float(total_spent_this_month)

        # Get today's spending
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        today_spent = db.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= today_start,
            Transaction.spent_at <= today_end
        ).scalar() or 0.0

        # Get daily targets from DailyPlan for today
        today_plans = db.query(DailyPlan).filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date == today
        ).all()

        # Get today's spending by category
        today_spending_by_category = {}
        today_transactions = db.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= today_start,
            Transaction.spent_at <= today_end
        ).group_by(Transaction.category).all()

        for cat, total in today_transactions:
            today_spending_by_category[cat or 'other'] = float(total)

        # Build daily targets
        daily_targets = []
        category_icons = {
            'food': 'restaurant',
            'transportation': 'directions_car',
            'entertainment': 'movie',
            'shopping': 'shopping_bag',
            'healthcare': 'local_hospital',
            'utilities': 'power',
            'other': 'category'
        }

        category_colors = {
            'food': '#4CAF50',
            'transportation': '#2196F3',
            'entertainment': '#9C27B0',
            'shopping': '#FF9800',
            'healthcare': '#F44336',
            'utilities': '#607D8B',
            'other': '#9E9E9E'
        }

        if today_plans:
            for plan in today_plans:
                category = plan.category or 'other'
                planned_amount = float(plan.planned_amount or 0.0)
                spent_amount = today_spending_by_category.get(category, 0.0)

                daily_targets.append({
                    'category': category.title(),
                    'limit': planned_amount,
                    'spent': spent_amount,
                    'icon': category_icons.get(category.lower(), 'category'),
                    'color': category_colors.get(category.lower(), '#9E9E9E'),
                })
        else:
            # Fallback: generate default targets based on monthly income
            daily_budget = monthly_income / 30  # Simple daily budget

            default_weights = {
                'Food & Dining': 0.35,
                'Transportation': 0.25,
                'Entertainment': 0.20,
                'Shopping': 0.20,
            }

            for category, weight in default_weights.items():
                category_key = category.lower().replace(' & ', '_').replace(' ', '_')
                spent = today_spending_by_category.get(category_key, 0.0)

                daily_targets.append({
                    'category': category,
                    'limit': daily_budget * weight,
                    'spent': spent,
                    'icon': category_icons.get(category_key, 'category'),
                    'color': category_colors.get(category_key, '#9E9E9E'),
                })

        # Get weekly overview (last 7 days)
        week_data = []
        days_of_week = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

        for i in range(7):
            day_date = today - timedelta(days=6-i)
            day_start = datetime.combine(day_date, datetime.min.time())
            day_end = datetime.combine(day_date, datetime.max.time())

            day_spent = db.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.user_id == user_id,
                Transaction.spent_at >= day_start,
                Transaction.spent_at <= day_end
            ).scalar() or 0.0

            day_budget = db.query(
                func.sum(DailyPlan.daily_budget)
            ).filter(
                DailyPlan.user_id == user_id,
                DailyPlan.date == day_date
            ).scalar() or (monthly_income / 30)

            # Determine status
            if float(day_spent) > float(day_budget):
                status = 'over'
            elif float(day_spent) > float(day_budget) * 0.9:
                status = 'warning'
            else:
                status = 'good'

            week_data.append({
                'day': days_of_week[day_date.weekday()],
                'status': status,
                'spent': float(day_spent),
                'budget': float(day_budget),
            })

        # Get recent transactions (last 10)
        recent_transactions = db.query(Transaction).filter(
            Transaction.user_id == user_id
        ).order_by(Transaction.spent_at.desc()).limit(10).all()

        transactions_data = []
        for txn in recent_transactions:
            transactions_data.append({
                'id': str(txn.id),
                'amount': float(txn.amount),
                'category': txn.category or 'other',
                'action': txn.description or 'Transaction',
                'date': txn.spent_at.isoformat(),
                'icon': category_icons.get((txn.category or 'other').lower(), 'attach_money'),
                'color': category_colors.get((txn.category or 'other').lower(), '#9E9E9E'),
            })

        # Simple insights preview
        insights_preview = {
            'text': 'Track your expenses to receive personalized insights',
            'title': 'Getting Started',
        }

        if total_spent_this_month > 0:
            spending_rate = (float(total_spent_this_month) / monthly_income) * 100 if monthly_income > 0 else 0

            if spending_rate > 80:
                insights_preview = {
                    'text': f'You\'ve spent {spending_rate:.0f}% of your monthly budget. Consider reducing discretionary spending.',
                    'title': 'Budget Alert',
                }
            elif spending_rate > 60:
                insights_preview = {
                    'text': f'You\'re on track! {spending_rate:.0f}% of budget used. Keep monitoring your spending.',
                    'title': 'On Track',
                }
            else:
                insights_preview = {
                    'text': f'Great job! Only {spending_rate:.0f}% of budget used. You\'re managing well.',
                    'title': 'Excellent',
                }

        return success_response({
            'balance': float(current_balance),
            'spent': float(today_spent),
            'daily_targets': daily_targets,
            'week': week_data,
            'transactions': transactions_data,
            'insights_preview': insights_preview,
            'user_income': monthly_income,
        })

    except Exception as e:
        logger.error(f"Error generating dashboard data: {str(e)}", exc_info=True)

        # Return minimal fallback data
        return success_response({
            'balance': 0.0,
            'spent': 0.0,
            'daily_targets': [],
            'week': [{'day': d, 'status': 'neutral'} for d in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']],
            'transactions': [],
            'insights_preview': {
                'text': 'Unable to load dashboard data. Please refresh.',
                'title': 'Error',
            },
            'error': True,
        })


@router.get("/quick-stats")
async def get_quick_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get quick statistics for dashboard widgets

    Returns:
    - monthly_spending: Total spent this month
    - daily_average: Average daily spending
    - top_category: Category with most spending
    - savings_rate: Percentage of income saved
    """
    try:
        user_id = user.id
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        now = datetime.now()

        monthly_income = float(user.monthly_income) if user.monthly_income else 0.0

        # Monthly spending
        monthly_spending = db.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= first_day_of_month,
            Transaction.spent_at < now
        ).scalar() or 0.0

        # Daily average
        days_in_month = today.day
        daily_average = float(monthly_spending) / days_in_month if days_in_month > 0 else 0.0

        # Top category
        top_category_result = db.query(
            Transaction.category,
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == user_id,
            Transaction.spent_at >= first_day_of_month,
            Transaction.spent_at < now
        ).group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc()).first()

        top_category = {
            'name': (top_category_result[0] or 'other').title() if top_category_result else 'None',
            'amount': float(top_category_result[1]) if top_category_result else 0.0,
        }

        # Savings rate
        savings = monthly_income - float(monthly_spending)
        savings_rate = (savings / monthly_income * 100) if monthly_income > 0 else 0.0

        return success_response({
            'monthly_spending': float(monthly_spending),
            'daily_average': daily_average,
            'top_category': top_category,
            'savings_rate': savings_rate,
            'savings_amount': savings,
        })

    except Exception as e:
        logger.error(f"Error generating quick stats: {str(e)}", exc_info=True)
        return success_response({
            'monthly_spending': 0.0,
            'daily_average': 0.0,
            'top_category': {'name': 'None', 'amount': 0.0},
            'savings_rate': 0.0,
            'savings_amount': 0.0,
            'error': True,
        })
