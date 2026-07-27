import hashlib
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import DailyPlan, Transaction, User
from app.services.core.engine.calendar_updater import calculate_day_status
from app.services.core.engine.realtime_rebalancer import (
    RebalancePlan,
    check_and_rebalance,
    consume_realtime_adjustment,
)
from app.services.redistribution_audit_log import record_redistribution_event

logger = logging.getLogger(__name__)

TRANSACTION_GENERATED_PLAN_KEY = "_mita_transaction_generated_v1"


def _safe_zone(tz: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def user_timezone_of(db: Session, user_id: UUID) -> str:
    tz = db.query(User.timezone).filter(User.id == user_id).scalar()
    return tz or "UTC"


def lock_user_ledger(db: Session, user_id: UUID) -> None:
    """Serialize every ledger/plan mutation for one user on PostgreSQL.

    The lock must be acquired before a Transaction row is inserted, updated,
    or deleted. A DailyPlan row lock alone cannot serialize an empty month and
    taking transaction-row locks after plan-row locks created a deadlock when
    two transactions in the same month were edited concurrently.
    """
    get_bind = getattr(db, "get_bind", None)
    if not callable(get_bind):
        return
    bind = get_bind()
    if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
        return

    digest = hashlib.blake2b(
        str(user_id).encode("utf-8"),
        digest_size=8,
        person=b"mita-ledger",
    ).digest()
    lock_key = int.from_bytes(digest, byteorder="big", signed=True)
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": lock_key},
    )


def local_day_of(spent_at: datetime, tz: Optional[str]) -> date:
    """Calendar day of a stored (UTC) transaction instant in the user's
    timezone — the day the user experienced the spend on."""
    if spent_at.tzinfo is None:
        spent_at = spent_at.replace(tzinfo=timezone.utc)
    return spent_at.astimezone(_safe_zone(tz)).date()


def local_day_start_utc(day: date, tz: Optional[str]) -> datetime:
    """UTC instant at which ``day`` starts in the user's timezone."""
    return datetime.combine(day, time.min, tzinfo=_safe_zone(tz)).astimezone(
        timezone.utc
    )


def local_day_utc_window(day: date, tz: Optional[str]) -> Tuple[datetime, datetime]:
    """UTC instant range [start, end) covering the user's local calendar day.

    Returned as naive datetimes meaning UTC — matching how spent_at is
    stored/compared across the codebase (and SQLite test databases, which
    cannot compare aware against stored-naive values).
    """
    start = local_day_start_utc(day, tz)
    end = local_day_start_utc(day + timedelta(days=1), tz)
    return (
        start.replace(tzinfo=None),
        end.replace(tzinfo=None),
    )


def _next_month_start(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _month_allocation_totals(
    db: Session,
    user_id: UUID,
    month_day: date,
) -> Dict[str, Decimal]:
    month_start = date(month_day.year, month_day.month, 1)
    next_month = _next_month_start(month_start)
    rows = (
        db.query(DailyPlan.category, DailyPlan.planned_amount)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= datetime.combine(month_start, time.min),
            DailyPlan.date < datetime.combine(next_month, time.min),
        )
        .all()
    )
    totals = defaultdict(lambda: Decimal("0.00"))
    for category, planned_amount in rows:
        totals[category or ""] += Decimal(planned_amount or 0)
    return dict(totals)


def _record_creation_redistribution(
    db: Session,
    user_id: UUID,
    to_category: str,
    before: Dict[str, Decimal],
    after: Dict[str, Decimal],
    result: RebalancePlan,
) -> None:
    """Audit only net allocation newly moved by this transaction creation.

    A month rebuild replays all prior overspends. Logging each replay would
    duplicate history, so the audit boundary is the top-level creation and
    only donor reductions relative to its pre-mutation plan are persisted.
    """
    donor_categories = sorted(
        {
            transfer["from_category"]
            for transfer in result.transfers
            if transfer.get("from_category")
        }
    )
    for donor_category in donor_categories:
        net_reduction = before.get(donor_category, Decimal("0.00")) - after.get(
            donor_category, Decimal("0.00")
        )
        if net_reduction < Decimal("0.01"):
            continue
        try:
            record_redistribution_event(
                db=db,
                user_id=user_id,
                from_category=donor_category,
                to_category=to_category,
                amount=net_reduction,
                reason="realtime_rebalance",
            )
        except Exception as audit_error:
            logger.warning(
                "audit log write failed (non-critical): %s",
                audit_error,
            )


def rebuild_month_plan(
    db: Session,
    user_id: UUID,
    month_day: date,
    *,
    tz: Optional[str] = None,
    commit: bool = True,
) -> Dict[Tuple[date, str], RebalancePlan]:
    """Rebuild one month from its base allocations and active ledger.

    Real-time redistribution writes a signed adjustment into each affected
    DailyPlan row. Rebuild first consumes every adjustment in the month,
    restoring the pre-rebalance allocations, then recomputes spend from all
    non-deleted transactions and replays each local-day/category overspend
    exactly once in deterministic order.
    """
    lock_user_ledger(db, user_id)

    if tz is None:
        tz = user_timezone_of(db, user_id)

    month_start = date(month_day.year, month_day.month, 1)
    next_month = _next_month_start(month_start)
    plan_start = datetime(month_start.year, month_start.month, 1)
    plan_end = datetime(next_month.year, next_month.month, 1)

    rows = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date >= plan_start,
            DailyPlan.date < plan_end,
        )
        .with_for_update()
        .all()
    )

    rows_by_key = {}
    for row in rows:
        adjustment = consume_realtime_adjustment(row)
        if adjustment:
            restored = Decimal(row.planned_amount or 0) - adjustment
            row.planned_amount = restored
            row.daily_budget = restored
        row.spent_amount = Decimal("0.00")
        row_day = row.date.date() if hasattr(row.date, "date") else row.date
        rows_by_key[(row_day, row.category)] = row

    txn_start = local_day_utc_window(month_start, tz)[0]
    txn_end = local_day_utc_window(next_month, tz)[0]
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= txn_start,
            Transaction.spent_at < txn_end,
        )
        .order_by(Transaction.spent_at, Transaction.category, Transaction.id)
        .all()
    )

    totals = defaultdict(lambda: Decimal("0.00"))
    for txn in transactions:
        if txn.category:
            totals[(local_day_of(txn.spent_at, tz), txn.category)] += Decimal(
                txn.amount or 0
            )

    for key, total in totals.items():
        row = rows_by_key.get(key)
        if row is None:
            day, category = key
            row = DailyPlan(
                user_id=user_id,
                date=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
                category=category,
                planned_amount=Decimal("0.00"),
                daily_budget=Decimal("0.00"),
                spent_amount=total,
                plan_json={TRANSACTION_GENERATED_PLAN_KEY: True},
            )
            db.add(row)
            rows.append(row)
            rows_by_key[key] = row
        else:
            row.spent_amount = total

    db.flush()

    rebalance_results = {}
    for day, category in sorted(totals):
        # rows_by_key already holds every plan row in this month, loaded FOR
        # UPDATE under the advisory lock. Handing it to the rebalancer keeps
        # the replay from re-selecting the same rows once per bucket.
        result = check_and_rebalance(
            db=db,
            user_id=user_id,
            category=category,
            transaction_date=day,
            commit=False,
            record_audit=False,
            month_rows=rows_by_key,
        )
        if result is not None:
            rebalance_results[(day, category)] = result

    active_keys = set(totals)
    for key, row in list(rows_by_key.items()):
        metadata = row.plan_json if isinstance(row.plan_json, dict) else {}
        if (
            key not in active_keys
            and metadata.get(TRANSACTION_GENERATED_PLAN_KEY) is True
            and Decimal(row.planned_amount or 0) == 0
            and Decimal(row.spent_amount or 0) == 0
        ):
            db.delete(row)
            rows_by_key.pop(key)

    rows_by_day = defaultdict(list)
    for (row_day, _category), row in rows_by_key.items():
        rows_by_day[row_day].append(row)
    for day_rows in rows_by_day.values():
        total_planned = sum(
            (Decimal(row.planned_amount or 0) for row in day_rows),
            Decimal("0.00"),
        )
        total_spent = sum(
            (Decimal(row.spent_amount or 0) for row in day_rows),
            Decimal("0.00"),
        )
        status, _delta = calculate_day_status(total_planned, total_spent)
        for row in day_rows:
            row.status = status

    if commit:
        db.commit()
    else:
        db.flush()

    return rebalance_results


def recalculate_plan_spent(
    db: Session,
    user_id: UUID,
    day: date,
    category: str,
    tz: Optional[str] = None,
    commit: bool = True,
) -> Optional[RebalancePlan]:
    """Rebuild the affected local month and return this bucket's rebalance."""
    results = rebuild_month_plan(
        db,
        user_id,
        day,
        tz=tz,
        commit=commit,
    )
    return results.get((day, category))


def run_transaction_plan_side_effects(
    db: Session,
    txn: Transaction,
    rebalance_result: Optional[RebalancePlan] = None,
) -> None:
    """Run non-ledger alerts after the transaction and plan commit."""
    tz = user_timezone_of(db, txn.user_id)
    txn_day = local_day_of(txn.spent_at, tz)
    day_start = datetime(txn_day.year, txn_day.month, txn_day.day)
    day_end = day_start + timedelta(days=1)
    plan = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == txn.user_id,
            DailyPlan.date >= day_start,
            DailyPlan.date < day_end,
            DailyPlan.category == txn.category,
        )
        .first()
    )

    # MODULE 10: Check budget and send alerts if needed.
    if plan and rebalance_result is not None:
        # Rebalancing credits the target before this post-commit notification.
        # The result captured the exact limit immediately before that credit,
        # including any earlier cuts to this row in the deterministic replay.
        alert_budget_limit = Decimal(plan.spent_amount or 0) - Decimal(
            rebalance_result.overspend_amount
        )
    elif plan:
        alert_budget_limit = Decimal(plan.planned_amount or 0)
    else:
        alert_budget_limit = Decimal("0.00")

    if plan and alert_budget_limit > 0:
        try:
            from app.services.budget_alert_service import get_budget_alert_service

            alert_service = get_budget_alert_service(db)
            alert_service.check_single_category(
                user_id=txn.user_id,
                category=txn.category,
                spent_amount=plan.spent_amount,
                budget_limit=alert_budget_limit,
            )
        except Exception as e:
            logger.warning(f"Failed to check budget alerts: {e}")

    # VELOCITY ALERT: check if this category is burning budget too fast.
    try:
        from app.services.velocity_alert_service import check_velocity_after_transaction

        check_velocity_after_transaction(
            db=db,
            user_id=txn.user_id,
            category=txn.category,
            transaction_date=txn_day,
        )
    except Exception as e:
        logger.warning(f"Velocity check failed (non-critical): {e}")


def apply_transaction_to_plan(
    db: Session,
    txn: Transaction,
    *,
    commit: bool = True,
    run_side_effects: bool = True,
) -> Optional[RebalancePlan]:
    """Apply an already saved transaction to the DailyPlan table.

    The plan day is the user's LOCAL calendar day of the spend — a txn at
    02:00 Sofia (23:00Z previous day) belongs to the Sofia date the user
    picked, not the UTC date.
    """
    lock_user_ledger(db, txn.user_id)
    tz = user_timezone_of(db, txn.user_id)
    txn_day = local_day_of(txn.spent_at, tz)
    before_allocations = _month_allocation_totals(db, txn.user_id, txn_day)
    results = rebuild_month_plan(
        db,
        txn.user_id,
        txn_day,
        tz=tz,
        commit=False,
    )
    rebalance_result = results.get((txn_day, txn.category))
    if rebalance_result is not None:
        after_allocations = _month_allocation_totals(db, txn.user_id, txn_day)
        _record_creation_redistribution(
            db,
            txn.user_id,
            txn.category,
            before_allocations,
            after_allocations,
            rebalance_result,
        )
        logger.info(
            "Auto-rebalance: covered=%.2f uncovered=%.2f transfers=%d",
            float(rebalance_result.covered),
            float(rebalance_result.uncovered),
            len(rebalance_result.transfers),
        )

    if commit:
        db.commit()
    else:
        db.flush()

    if run_side_effects:
        run_transaction_plan_side_effects(db, txn, rebalance_result)

    return rebalance_result


def commit_transaction_to_ledger(
    db: Session,
    txn: Transaction,
    *,
    run_side_effects: bool = True,
) -> Optional[RebalancePlan]:
    """Make a new Transaction visible in the ledger. The only sanctioned way.

    Every writer must go through here so that a transaction row and the
    DailyPlan allocations it implies move together:

    * the per-user advisory lock is taken before the row is inserted and is
      held, by the surrounding transaction, until the plan rebuild commits;
    * the insert and the month rebuild share one commit, so a failing rebuild
      rolls the transaction back instead of leaving spend the plan never saw;
    * notifications run only after that commit, and never abort the ledger.

    Callers that build a Transaction and commit it themselves silently skip
    redistribution: the money leaves the user's budget in the transaction
    list but never reaches the daily plan, so the dashboard, the calendar and
    every alert disagree with the ledger.
    """
    lock_user_ledger(db, txn.user_id)
    db.add(txn)
    try:
        db.flush()
        rebalance_result = apply_transaction_to_plan(
            db,
            txn,
            commit=False,
            run_side_effects=False,
        )
        db.commit()
        db.refresh(txn)
    except Exception:
        db.rollback()
        raise

    if run_side_effects:
        run_transaction_plan_side_effects(db, txn, rebalance_result)

    return rebalance_result


def record_expense(
    db: Session,
    user_id: UUID,
    day: date,
    category: str,
    amount: float,
    description: str = "",
):
    # Transaction has no `date` column — the temporal column is spent_at.
    # Decimal(str(...)) avoids importing binary-float error into money.
    lock_user_ledger(db, user_id)
    user_timezone = user_timezone_of(db, user_id)
    txn = Transaction(
        user_id=user_id,
        spent_at=local_day_start_utc(day, user_timezone),
        category=category,
        amount=Decimal(str(amount)),
        description=description,
    )
    db.add(txn)
    db.flush()
    rebalance_result = apply_transaction_to_plan(
        db,
        txn,
        commit=False,
        run_side_effects=False,
    )
    db.commit()
    db.refresh(txn)
    run_transaction_plan_side_effects(db, txn, rebalance_result)

    return {
        "status": "recorded",
        "date": day.isoformat(),
        "category": category,
        "amount": float(amount),
    }
