"""
Scheduled Expense Cron Task — fires due expenses and sends reminders.

Runs daily at 06:00 UTC:
  1. Find all expenses due today → create real Transaction → apply to DailyPlan
     → auto-rebalance (core MITA promise kept even for planned bills).
  2. Find expenses due within 3 days → send push reminder if not already sent.
  3. For recurring expenses: schedule next occurrence after processing.

Only rows created in the mobile app (``origin = "app"``). An obligation saved
in ChatGPT (``origin = "chatgpt"``), or a row of unknown origin, is a bill to
remind of in the calendar, paid only by an expense the user links to it
(``obligation_payments``): this processor never turns it into an expense and
never pushes about it (PR #288 review P1).

And an app row the user pays through links — any expense ever linked to any
of its due dates — is theirs from then on, like a ChatGPT obligation: never
recorded, marked processed, rolled forward or reminded of. Every surface
shows its due dates paid or unpaid from the links, so a deleted, partial or
early payment can neither lose the bill nor record it twice (independent
review of the Gate 1 commit, findings 3-5 and 8). Each row is re-read under
the user's ledger lock, so two runs never record it twice (finding 6).

Integrates with the sync cron infrastructure (same pattern as velocity alerts):
  • run_scheduled_expenses_daily() — no-arg wrapper for rq_scheduler
  • run_scheduled_expenses_batch(db, today) — testable core, accepts injected session
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.services.monthly_obligations import APP_ORIGIN

logger = logging.getLogger(__name__)

REMINDER_DAYS_AHEAD = 3


def run_scheduled_expenses_batch(
    db: Session,
    today: Optional[date] = None,
) -> dict:
    """
    Core processing logic.

    Returns a summary dict for logging / testing.
    """
    if today is None:
        today = date.today()

    summary = {
        "processed": 0,
        "paid_through_links": 0,
        "reminders_sent": 0,
        "recurrences_scheduled": 0,
        "errors": 0,
    }

    _process_due_expenses(db, today, summary)
    _send_reminders(db, today, summary)

    logger.info(
        "scheduled_expense cron: processed=%d reminders=%d recurrences=%d errors=%d",
        summary["processed"],
        summary["reminders_sent"],
        summary["recurrences_scheduled"],
        summary["errors"],
    )
    return summary


def run_scheduled_expenses_daily() -> None:
    """
    No-arg entrypoint for rq_scheduler.
    Mirrors the pattern used by run_velocity_alerts_daily().
    """
    from app.core.session import get_db

    db: Session = next(get_db())
    try:
        run_scheduled_expenses_batch(db=db)
    finally:
        db.close()


# ─── Phase 1: Process due expenses ───────────────────────────────────────────


def _process_due_expenses(db: Session, today: date, summary: dict) -> None:
    """Create transactions for all expenses whose scheduled_date is today."""
    from app.db.models.scheduled_expense import ScheduledExpense
    from app.db.models.transaction import Transaction
    from app.services.core.engine.expense_tracker import (
        apply_transaction_to_plan,
        lock_user_ledger,
        run_transaction_plan_side_effects,
    )

    due: list[ScheduledExpense] = (
        db.query(ScheduledExpense)
        .filter(
            ScheduledExpense.scheduled_date == today,
            ScheduledExpense.status == "pending",
            ScheduledExpense.deleted_at.is_(None),
            # never an obligation saved in ChatGPT (see the module docstring)
            ScheduledExpense.origin == APP_ORIGIN,
        )
        .all()
    )

    logger.info("scheduled_expense cron: %d expenses due on %s", len(due), today)

    # ids taken while the rows are fresh: a later rollback expires them, and
    # a row deleted meanwhile could not be read again (not even for a log)
    for expense_id, expense in [(e.id, e) for e in due]:
        try:
            lock_user_ledger(db, expense.user_id)
            # 0a. Re-read under the lock: another run may have handled it, or
            #     the row may be gone — either way, not ours to record.
            try:
                db.refresh(expense)
            except Exception:
                db.rollback()
                continue
            if expense.status != "pending" or expense.deleted_at is not None:
                db.rollback()
                continue
            # 0b. The user pays this row through links: theirs, never ours.
            if _paid_through_links(db, expense):
                db.rollback()
                summary["paid_through_links"] += 1
                logger.info(
                    "scheduled_expense cron: id=%s is paid through links; left alone",
                    expense.id,
                )
                continue

            # 1. Create the real Transaction
            txn = Transaction(
                user_id=expense.user_id,
                category=expense.category,
                amount=expense.amount,
                description=expense.description or f"Scheduled: {expense.category}",
                merchant=expense.merchant,
                spent_at=datetime.now(timezone.utc),
            )
            db.add(txn)
            db.flush()

            # 2. Mark the scheduled expense as processed
            expense.status = "processed"
            expense.processed_at = datetime.now(timezone.utc)
            expense.transaction_id = txn.id
            db.flush()

            # 3. Apply to DailyPlan + auto-rebalance (core MITA promise).
            #    apply_transaction_to_plan calls check_and_rebalance internally.
            rebalance_result = apply_transaction_to_plan(
                db,
                txn,
                commit=False,
                run_side_effects=False,
            )

            db.commit()
            run_transaction_plan_side_effects(db, txn, rebalance_result)
            summary["processed"] += 1

            # 4. "Expense processed" push notification
            _notify_processed(db, expense, txn)

            # 5. Schedule next recurrence
            if expense.recurrence:
                try:
                    _schedule_next_recurrence(db, expense, today)
                    db.commit()
                    summary["recurrences_scheduled"] += 1
                except Exception as exc:
                    db.rollback()
                    logger.error(
                        "scheduled_expense cron: recurrence failed id=%s err=%s",
                        expense.id,
                        exc,
                    )

            logger.info(
                "scheduled_expense cron: processed id=%s txn=%s user=%s amount=%.2f",
                expense.id,
                txn.id,
                expense.user_id,
                float(expense.amount),
            )

        except Exception as exc:
            db.rollback()
            summary["errors"] += 1
            logger.error(
                "scheduled_expense cron: failed to process id=%s err=%s",
                expense_id,
                exc,
            )
            # Mark as failed so we don't retry indefinitely
            try:
                expense.status = "failed"
                db.commit()
            except Exception:
                db.rollback()


# ─── Phase 2: Send reminders ─────────────────────────────────────────────────


def _send_reminders(db: Session, today: date, summary: dict) -> None:
    """Push reminder for expenses coming up in 1 – REMINDER_DAYS_AHEAD days."""
    from app.db.models.scheduled_expense import ScheduledExpense
    from app.services.notification_integration import NotificationIntegration

    reminder_end = today + timedelta(days=REMINDER_DAYS_AHEAD)

    upcoming: list[ScheduledExpense] = (
        db.query(ScheduledExpense)
        .filter(
            ScheduledExpense.scheduled_date > today,
            ScheduledExpense.scheduled_date <= reminder_end,
            ScheduledExpense.status == "pending",
            ScheduledExpense.reminder_sent_at.is_(None),
            ScheduledExpense.deleted_at.is_(None),
            # ChatGPT's obligations are reminded of in the calendar only
            ScheduledExpense.origin == APP_ORIGIN,
        )
        .all()
    )

    logger.info("scheduled_expense cron: %d reminders to send", len(upcoming))

    notif = NotificationIntegration(db)

    for expense in upcoming:
        if _paid_through_links(db, expense):
            continue  # the user pays it through links: no "due in N days" push
        days_until = (expense.scheduled_date - today).days
        try:
            notif.notify_scheduled_expense_reminder(
                user_id=expense.user_id,
                category=expense.category,
                amount=float(expense.amount),
                scheduled_date=expense.scheduled_date,
                days_until=days_until,
                merchant=expense.merchant,
            )
            expense.reminder_sent_at = datetime.now(timezone.utc)
            db.flush()
            summary["reminders_sent"] += 1
        except Exception as exc:
            logger.error(
                "scheduled_expense cron: reminder failed id=%s err=%s",
                expense.id,
                exc,
            )

    if upcoming:
        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("scheduled_expense cron: reminder commit failed: %s", exc)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _paid_through_links(db: Session, expense) -> bool:
    """Whether this user ever linked an expense to any due date of this row
    (``obligation_payments``, from ChatGPT's obligation_ref) — deleted or
    not, partial or not. Such a row follows the links, never this processor:
    what is paid shows as paid on every surface, what is not stays held."""
    from app.db.models import ObligationPayment

    return (
        db.query(ObligationPayment.transaction_id)
        .filter(
            ObligationPayment.scheduled_expense_id == expense.id,
            ObligationPayment.user_id == expense.user_id,
        )
        .first()
        is not None
    )


def _notify_processed(db: Session, expense, txn) -> None:
    """Non-blocking: send 'your scheduled expense fired' push notification."""
    try:
        from app.services.notification_integration import NotificationIntegration

        notif = NotificationIntegration(db)
        notif.notify_scheduled_expense_processed(
            user_id=expense.user_id,
            category=expense.category,
            amount=float(expense.amount),
            scheduled_date=expense.scheduled_date,
            transaction_id=str(txn.id),
        )
    except Exception as exc:
        logger.warning(
            "scheduled_expense cron: processed notification failed id=%s err=%s",
            expense.id,
            exc,
        )


def _schedule_next_recurrence(db: Session, expense, fired_date: date) -> None:
    """Create the next occurrence row for weekly / monthly recurring expenses."""
    from app.db.models.scheduled_expense import ScheduledExpense

    if expense.recurrence == "weekly":
        next_date = fired_date + timedelta(weeks=1)
    elif expense.recurrence == "monthly":
        # The day of the month asked for (kept apart from the clamped date
        # since migration 0045: "the 31st" fired on 30 November is next due
        # on 31 December), else the fired date's own day; clamped to the last
        # day of a shorter month.
        year = fired_date.year
        month = fired_date.month + 1
        if month > 12:
            month = 1
            year += 1
        last_day = calendar.monthrange(year, month)[1]
        wanted = expense.day_of_month or fired_date.day
        day = min(wanted, last_day)
        next_date = date(year, month, day)
    else:
        return  # "once" or unknown — no recurrence

    next_expense = ScheduledExpense(
        user_id=expense.user_id,
        category=expense.category,
        amount=expense.amount,
        description=expense.description,
        merchant=expense.merchant,
        scheduled_date=next_date,
        recurrence=expense.recurrence,
        # The requested day travels with the row. An app row's own date is the
        # day the user chose (the app takes an explicit date), so "the 31st"
        # recorded on 28 February is next due on 31 March, not the 28th.
        day_of_month=(
            expense.day_of_month or expense.scheduled_date.day
            if expense.recurrence == "monthly"
            else None
        ),
        origin=expense.origin,
        status="pending",
    )
    db.add(next_expense)
    db.flush()

    logger.info(
        "scheduled_expense cron: recurrence scheduled id=%s → next=%s",
        expense.id,
        next_date,
    )
