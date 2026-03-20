"""
Velocity Alert Service — DB-aware orchestrator for proactive velocity alerts.

Two trigger modes:
  1. Real-time  — called from expense_tracker after each transaction.
                  Checks only the category that was just modified.
  2. Daily cron — called for every active user once per day.
                  Checks all categories + detects win-streaks.

Deduplication: before sending any alert the service checks the Notification
table for a recent alert with the same group_key. If one exists within the
cooldown window (24 h for velocity alerts, 7 days for wins) the alert is
silently suppressed.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import DailyPlan, Goal, Notification, User
from app.services.core.engine.velocity_alert_engine import (
    CategoryVelocity,
    DailyPlanData,
    GoalData,
    GoalImpact,
    SpendingWin,
    VelocityAlertLevel,
    VelocityAlertResult,
    compute_velocity_alerts,
)
from app.services.notification_integration import get_notification_integration

logger = get_logger(__name__)

# How long to suppress duplicate velocity alerts for the same category
VELOCITY_ALERT_COOLDOWN_HOURS: int = 24
# How long to suppress duplicate win notifications for the same milestone
WIN_NOTIFICATION_COOLDOWN_DAYS: int = 7

# group_key prefixes stored in the Notification table (indexed)
_GK_VELOCITY = "velocity_alert"
_GK_WIN = "spending_win"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_velocity_after_transaction(
    db: Session,
    user_id: UUID,
    category: str,
    transaction_date: date,
) -> Optional[VelocityAlertResult]:
    """
    Real-time velocity check for ONE category right after a transaction.

    Called from expense_tracker.apply_transaction_to_plan().
    Any exception is caught internally — non-blocking.
    """
    try:
        return _run_velocity_check(
            db=db,
            user_id=user_id,
            transaction_date=transaction_date,
            category_filter=category,
        )
    except Exception as exc:
        logger.warning(
            "velocity check failed (non-critical): user=%s cat=%s err=%s",
            user_id, category, exc,
        )
        return None


def run_velocity_check_for_user(
    db: Session,
    user_id: UUID,
    today: Optional[date] = None,
) -> Optional[VelocityAlertResult]:
    """
    Full velocity scan for one user: all categories + win detection.

    Called from the daily cron job.
    """
    if today is None:
        today = date.today()
    try:
        return _run_velocity_check(
            db=db,
            user_id=user_id,
            transaction_date=today,
            category_filter=None,
        )
    except Exception as exc:
        logger.warning(
            "velocity full scan failed: user=%s err=%s", user_id, exc
        )
        return None


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------

def _run_velocity_check(
    db: Session,
    user_id: UUID,
    transaction_date: date,
    category_filter: Optional[str],
) -> Optional[VelocityAlertResult]:
    """Fetch data, run engine, deduplicate, dispatch notifications."""
    year = transaction_date.year
    month = transaction_date.month

    # ------------------------------------------------------------------
    # Fetch DailyPlan rows for the whole month
    # ------------------------------------------------------------------
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = datetime(year, month, 1, 0, 0, 0)
    month_end = datetime(year, month, days_in_month, 23, 59, 59)

    plan_rows = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= month_start,
            DailyPlan.date <= month_end,
        )
        .all()
    )

    daily_plans: List[DailyPlanData] = []
    for row in plan_rows:
        if not row.category:
            continue
        plan_date = row.date.date() if hasattr(row.date, "date") else row.date
        daily_plans.append(
            DailyPlanData(
                plan_date=plan_date,
                category=row.category,
                planned_amount=Decimal(str(row.planned_amount or "0")),
                spent_amount=Decimal(str(row.spent_amount or "0")),
            )
        )

    # ------------------------------------------------------------------
    # Fetch active goals (soft-delete aware)
    # ------------------------------------------------------------------
    goal_rows = (
        db.query(Goal)
        .filter(
            Goal.user_id == user_id,
            Goal.status == "active",
            Goal.deleted_at.is_(None),
        )
        .all()
    )

    goals: List[GoalData] = []
    for g in goal_rows:
        try:
            goals.append(
                GoalData(
                    goal_id=str(g.id),
                    title=g.title or "Goal",
                    target_amount=Decimal(str(g.target_amount or "0")),
                    saved_amount=Decimal(str(g.saved_amount or "0")),
                    monthly_contribution=(
                        Decimal(str(g.monthly_contribution))
                        if g.monthly_contribution
                        else None
                    ),
                    target_date=g.target_date,
                )
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Run pure engine
    # ------------------------------------------------------------------
    result = compute_velocity_alerts(
        daily_plans=daily_plans,
        goals=goals,
        year=year,
        month=month,
        today=transaction_date,
        category=category_filter,
    )

    # ------------------------------------------------------------------
    # Dispatch notifications
    # ------------------------------------------------------------------
    notifier = get_notification_integration(db)

    for alert in result.alerts:
        _maybe_send_velocity_alert(
            db=db,
            notifier=notifier,
            user_id=user_id,
            alert=alert,
            goal_impacts=result.goal_impacts,
            year=year,
            month=month,
        )

    # Win notifications — only from full scan (category_filter is None)
    if category_filter is None:
        for win in result.wins:
            _maybe_send_win_notification(
                db=db,
                notifier=notifier,
                user_id=user_id,
                win=win,
                year=year,
                month=month,
            )

    return result


# ---------------------------------------------------------------------------
# Notification dispatchers (with deduplication)
# ---------------------------------------------------------------------------

def _maybe_send_velocity_alert(
    db: Session,
    notifier,
    user_id: UUID,
    alert: CategoryVelocity,
    goal_impacts: List[GoalImpact],
    year: int,
    month: int,
) -> None:
    """Send a velocity alert unless a duplicate was sent in the cooldown window."""
    group_key = (
        f"{_GK_VELOCITY}:{user_id}:{alert.category}:{year}-{month:02d}"
    )
    cooldown_cutoff = datetime.utcnow() - timedelta(hours=VELOCITY_ALERT_COOLDOWN_HOURS)

    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.group_key == group_key,
            Notification.created_at >= cooldown_cutoff,
        )
        .first()
    )
    if existing:
        logger.debug(
            "velocity alert suppressed (cooldown): user=%s cat=%s", user_id, alert.category
        )
        return

    # Pick the most impactful goal to mention
    top_impact: Optional[GoalImpact] = goal_impacts[0] if goal_impacts else None

    days_left = (
        float(alert.days_until_exhausted)
        if alert.days_until_exhausted is not None
        else None
    )

    level = alert.alert_level
    try:
        if level == VelocityAlertLevel.CRITICAL:
            notifier.notify_velocity_critical(
                user_id=user_id,
                category=alert.category,
                velocity_ratio=float(alert.velocity_ratio),
                days_until_exhausted=days_left,
                monthly_planned=float(alert.monthly_planned),
                monthly_spent=float(alert.monthly_spent),
                goal_impact=top_impact,
                group_key=group_key,
            )
        elif level == VelocityAlertLevel.WARNING:
            notifier.notify_velocity_warning(
                user_id=user_id,
                category=alert.category,
                velocity_ratio=float(alert.velocity_ratio),
                days_until_exhausted=days_left,
                monthly_planned=float(alert.monthly_planned),
                monthly_spent=float(alert.monthly_spent),
                goal_impact=top_impact,
                group_key=group_key,
            )
        else:  # WATCH
            notifier.notify_velocity_watch(
                user_id=user_id,
                category=alert.category,
                velocity_ratio=float(alert.velocity_ratio),
                days_until_exhausted=days_left,
                monthly_planned=float(alert.monthly_planned),
                monthly_spent=float(alert.monthly_spent),
                group_key=group_key,
            )

        logger.info(
            "velocity alert sent: user=%s cat=%s level=%s ratio=%.2f",
            user_id,
            alert.category,
            level.value,
            float(alert.velocity_ratio),
        )
    except Exception as exc:
        logger.error(
            "failed to send velocity alert: user=%s cat=%s err=%s",
            user_id, alert.category, exc,
        )


def _maybe_send_win_notification(
    db: Session,
    notifier,
    user_id: UUID,
    win: SpendingWin,
    year: int,
    month: int,
) -> None:
    """Send win notification unless the same milestone was sent this week."""
    group_key = f"{_GK_WIN}:{user_id}:{win.win_type}:{year}-{month:02d}"
    cooldown_cutoff = datetime.utcnow() - timedelta(days=WIN_NOTIFICATION_COOLDOWN_DAYS)

    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.group_key == group_key,
            Notification.created_at >= cooldown_cutoff,
        )
        .first()
    )
    if existing:
        return

    try:
        notifier.notify_spending_win(
            user_id=user_id,
            win_type=win.win_type,
            streak_days=win.streak_days,
            surplus_amount=float(win.surplus_amount),
            group_key=group_key,
        )
        logger.info(
            "win notification sent: user=%s type=%s streak=%d saved=%.2f",
            user_id, win.win_type, win.streak_days, float(win.surplus_amount),
        )
    except Exception as exc:
        logger.error(
            "failed to send win notification: user=%s type=%s err=%s",
            user_id, win.win_type, exc,
        )
