"""
Dashboard API Routes for MITA Main Screen

Provides comprehensive dashboard data including:
- Current balance and spending
- Daily budget targets by category
- Recent transactions
- Weekly spending overview
- AI insights preview
- Active goals with progress tracking (MODULE 5)
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
from app.db.models import Transaction, DailyPlan, Goal, ChallengeParticipation, Challenge
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
        today = datetime.utcnow().date()
        now = datetime.utcnow()

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

        # MODULE 5: Get active goals with progress
        goals_data = []
        goals_summary = {
            'total_active': 0,
            'near_completion': 0,
            'overdue': 0,
        }

        try:
            # Get active goals ordered by priority and progress
            active_goals = db.query(Goal).filter(
                Goal.user_id == user_id,
                Goal.status == 'active'
            ).order_by(
                Goal.priority.desc(),
                Goal.progress.desc()
            ).limit(5).all()  # Show top 5 goals on dashboard

            goals_summary['total_active'] = db.query(func.count(Goal.id)).filter(
                Goal.user_id == user_id,
                Goal.status == 'active'
            ).scalar() or 0

            for goal in active_goals:
                progress = float(goal.progress or 0)

                # Check if near completion (>= 80%)
                if progress >= 80:
                    goals_summary['near_completion'] += 1

                # Check if overdue
                is_overdue = False
                if goal.target_date and goal.target_date < today:
                    is_overdue = True
                    goals_summary['overdue'] += 1

                goals_data.append({
                    'id': str(goal.id),
                    'title': goal.title,
                    'category': goal.category or 'Other',
                    'target_amount': float(goal.target_amount),
                    'saved_amount': float(goal.saved_amount),
                    'progress': progress,
                    'priority': goal.priority or 'medium',
                    'is_overdue': is_overdue,
                    'target_date': goal.target_date.isoformat() if goal.target_date else None,
                    'remaining_amount': float(goal.target_amount) - float(goal.saved_amount),
                })

        except Exception as e:
            logger.error(f"Error loading goals for dashboard: {str(e)}", exc_info=True)
            # Continue with empty goals data

        # MODULE 5: Get active challenges
        challenges_data = []
        challenges_summary = {
            'active_challenges': 0,
            'completed_this_month': 0,
            'current_streak': 0,
        }

        try:
            current_month = today.strftime("%Y-%m")

            # Get active challenge participations
            active_participations = db.query(ChallengeParticipation).filter(
                ChallengeParticipation.user_id == user_id,
                ChallengeParticipation.status == 'active'
            ).order_by(
                ChallengeParticipation.progress_percentage.desc()
            ).limit(3).all()  # Show top 3 active challenges

            challenges_summary['active_challenges'] = db.query(func.count(ChallengeParticipation.id)).filter(
                ChallengeParticipation.user_id == user_id,
                ChallengeParticipation.status == 'active'
            ).scalar() or 0

            challenges_summary['completed_this_month'] = db.query(func.count(ChallengeParticipation.id)).filter(
                ChallengeParticipation.user_id == user_id,
                ChallengeParticipation.status == 'completed',
                ChallengeParticipation.month == current_month
            ).scalar() or 0

            # Get max current streak
            max_streak = db.query(func.max(ChallengeParticipation.current_streak)).filter(
                ChallengeParticipation.user_id == user_id,
                ChallengeParticipation.status == 'active'
            ).scalar() or 0
            challenges_summary['current_streak'] = max_streak

            for participation in active_participations:
                challenge = db.query(Challenge).filter(
                    Challenge.id == participation.challenge_id
                ).first()

                if challenge:
                    challenges_data.append({
                        'id': challenge.id,
                        'name': challenge.name,
                        'description': challenge.description,
                        'type': challenge.type,
                        'difficulty': challenge.difficulty,
                        'duration_days': challenge.duration_days,
                        'reward_points': challenge.reward_points,
                        'progress_percentage': participation.progress_percentage,
                        'days_completed': participation.days_completed,
                        'current_streak': participation.current_streak,
                        'started_at': participation.started_at.isoformat() if participation.started_at else None,
                    })

        except Exception as e:
            logger.error(f"Error loading challenges for dashboard: {str(e)}", exc_info=True)
            # Continue with empty challenges data

        return success_response({
            'balance': float(current_balance),
            'spent': float(today_spent),
            'daily_targets': daily_targets,
            'week': week_data,
            'transactions': transactions_data,
            'insights_preview': insights_preview,
            'user_income': monthly_income,
            'goals': goals_data,
            'goals_summary': goals_summary,
            'challenges': challenges_data,
            'challenges_summary': challenges_summary,
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
            'goals': [],
            'goals_summary': {'total_active': 0, 'near_completion': 0, 'overdue': 0},
            'challenges': [],
            'challenges_summary': {'active_challenges': 0, 'completed_this_month': 0, 'current_streak': 0},
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
    - goals_stats: Goals statistics (MODULE 5)
    """
    try:
        user_id = user.id
        today = datetime.utcnow().date()
        first_day_of_month = today.replace(day=1)
        now = datetime.utcnow()

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

        # MODULE 5: Goals statistics
        goals_stats = {
            'total_goals': 0,
            'active_goals': 0,
            'completed_goals': 0,
            'total_target_amount': 0.0,
            'total_saved_amount': 0.0,
            'average_progress': 0.0,
        }

        try:
            all_goals = db.query(Goal).filter(Goal.user_id == user_id).all()
            goals_stats['total_goals'] = len(all_goals)

            active_goals = [g for g in all_goals if g.status == 'active']
            completed_goals = [g for g in all_goals if g.status == 'completed']

            goals_stats['active_goals'] = len(active_goals)
            goals_stats['completed_goals'] = len(completed_goals)

            if all_goals:
                goals_stats['total_target_amount'] = sum(float(g.target_amount) for g in all_goals)
                goals_stats['total_saved_amount'] = sum(float(g.saved_amount) for g in all_goals)
                goals_stats['average_progress'] = sum(float(g.progress or 0) for g in all_goals) / len(all_goals)
        except Exception as e:
            logger.error(f"Error calculating goals stats: {str(e)}", exc_info=True)

        return success_response({
            'monthly_spending': float(monthly_spending),
            'daily_average': daily_average,
            'top_category': top_category,
            'savings_rate': savings_rate,
            'savings_amount': savings,
            'goals_stats': goals_stats,
        })

    except Exception as e:
        logger.error(f"Error generating quick stats: {str(e)}", exc_info=True)
        return success_response({
            'monthly_spending': 0.0,
            'daily_average': 0.0,
            'top_category': {'name': 'None', 'amount': 0.0},
            'savings_rate': 0.0,
            'savings_amount': 0.0,
            'goals_stats': {
                'total_goals': 0,
                'active_goals': 0,
                'completed_goals': 0,
                'total_target_amount': 0.0,
                'total_saved_amount': 0.0,
                'average_progress': 0.0,
            },
            'error': True,
        })
