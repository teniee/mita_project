"""
Real-time budget rebalancer — MITA's core promise.

"When you overspend in one category, MITA instantly rebalances
across remaining days." — product description

PHILOSOPHY:
- MITA suggests, user decides. This runs automatically but result
  is surfaced to user as a notification they can dismiss.
- Savings are SACRED: never take from savings_goal or savings_emergency.
- Take from DISCRETIONARY (dining, entertainment) first.
- Never wipe out any category — max 50% cut per category per rebalance.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.category_priority import get_category_level, is_sacred
from app.db.models.daily_plan import DailyPlan
from app.services.redistribution_audit_log import record_redistribution_event

logger = logging.getLogger(__name__)

REALTIME_ADJUSTMENT_KEY = "_mita_realtime_adjustment_v1"
CENT = Decimal("0.01")


def _plan_metadata(entry: DailyPlan) -> Dict:
    """Return mutable plan metadata without sharing the JSONB value in-place."""
    return dict(entry.plan_json) if isinstance(entry.plan_json, dict) else {}


def record_realtime_adjustment(entry: DailyPlan, delta: Decimal) -> None:
    """Persist the signed allocation delta applied to one DailyPlan row.

    Donor cuts are negative and target credits are positive. The month rebuild
    consumes these values to recover the pre-rebalance allocation exactly.
    """
    metadata = _plan_metadata(entry)
    current = Decimal(str(metadata.get(REALTIME_ADJUSTMENT_KEY, "0")))
    metadata[REALTIME_ADJUSTMENT_KEY] = format(current + delta, "f")
    entry.plan_json = metadata


def consume_realtime_adjustment(entry: DailyPlan) -> Decimal:
    """Remove and return this row's recorded real-time allocation delta."""
    metadata = _plan_metadata(entry)
    raw_delta = metadata.pop(REALTIME_ADJUSTMENT_KEY, "0")
    entry.plan_json = metadata or None
    return Decimal(str(raw_delta))


def _allocate_cents_with_caps(
    target: Decimal,
    capacities: List[Decimal],
) -> List[Decimal]:
    """Split ``target`` exactly across rows without exceeding any row cap.

    Money is allocated as integer cents. This avoids both over-crediting from
    per-row rounding (for example, $0.07 across two rows becoming $0.08) and
    stranded capacity when donor rows have uneven allocations.
    """
    target_cents = int(
        (max(Decimal("0"), target) * 100).to_integral_value(rounding=ROUND_DOWN)
    )
    capacity_cents = [
        int((max(Decimal("0"), capacity) * 100).to_integral_value(rounding=ROUND_DOWN))
        for capacity in capacities
    ]
    target_cents = min(target_cents, sum(capacity_cents))
    cuts = [0] * len(capacity_cents)
    active = [index for index, cap in enumerate(capacity_cents) if cap > 0]
    remaining = target_cents

    while remaining and active:
        share, remainder = divmod(remaining, len(active))
        allocated = 0
        next_active = []
        for position, index in enumerate(active):
            capacity_left = capacity_cents[index] - cuts[index]
            requested = share + (1 if position < remainder else 0)
            addition = min(requested, capacity_left)
            cuts[index] += addition
            allocated += addition
            if cuts[index] < capacity_cents[index]:
                next_active.append(index)

        if allocated == 0:
            break
        remaining -= allocated
        active = next_active

    return [Decimal(cents) / Decimal("100") for cents in cuts]


class RebalancePlan:
    """Result of a rebalance operation. Returned to caller for notification."""

    def __init__(self) -> None:
        self.overspent_category: str = ""
        self.overspend_amount: Decimal = Decimal("0")
        self.remaining_days: int = 0
        self.transfers: List[Dict] = []
        self.covered: Decimal = Decimal("0")
        self.uncovered: Decimal = Decimal("0")
        self.goal_context: Optional[Dict] = None

    @property
    def fully_covered(self) -> bool:
        return self.uncovered <= Decimal("0.01")

    def to_dict(self) -> Dict:
        return {
            "overspent_category": self.overspent_category,
            "overspend_amount": float(self.overspend_amount),
            "remaining_days": self.remaining_days,
            "covered": float(self.covered),
            "uncovered": float(self.uncovered),
            "transfers": self.transfers,
            "fully_covered": self.fully_covered,
            "goal_context": self.goal_context,
        }


def _plan_row_day(entry: DailyPlan) -> date:
    """Calendar day of a plan row, whether it is loaded as date or datetime."""
    value = entry.date
    return value.date() if hasattr(value, "date") else value


def rebalance_after_overspend(
    db: Session,
    user_id: UUID,
    overspent_category: str,
    overspend_amount: Decimal,
    transaction_date: date,
    dry_run: bool = False,
    commit: bool = True,
    record_audit: bool = True,
    month_rows: Optional[Dict] = None,
) -> RebalancePlan:
    """
    Core algorithm: redistribute future budget after overspend.

    Args:
        db: SQLAlchemy session
        user_id: user UUID
        overspent_category: the category that exceeded its budget
        overspend_amount: how much over the plan (positive Decimal)
        transaction_date: the date overspending occurred
        dry_run: if True, calculate but do NOT save changes to DB
        month_rows: optional {(day, category): DailyPlan} covering the whole
            month. A month rebuild already holds every row under the same
            advisory lock, so re-selecting them per (day, category) bucket
            costs two extra round trips each with no new information.

    Returns:
        RebalancePlan with summary of what was changed
    """
    plan = RebalancePlan()
    plan.overspent_category = overspent_category
    plan.overspend_amount = overspend_amount

    year = transaction_date.year
    month = transaction_date.month
    last_day = monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    # DailyPlan.date is DateTime — convert boundaries to datetime for safe comparison
    day_start = datetime(
        transaction_date.year,
        transaction_date.month,
        transaction_date.day,
        23,
        59,
        59,
    )
    month_end_dt = datetime(month_end.year, month_end.month, month_end.day, 23, 59, 59)

    # 1. All FUTURE DailyPlan entries in this month (strictly after transaction_date).
    #    Ordering must match the SQL path exactly — donor selection is
    #    order-sensitive and the replay has to stay deterministic.
    if month_rows is None:
        future_entries: List[DailyPlan] = (
            db.query(DailyPlan)
            .filter(
                DailyPlan.user_id == user_id,
                DailyPlan.date > day_start,
                DailyPlan.date <= month_end_dt,
            )
            .order_by(DailyPlan.date, DailyPlan.category, DailyPlan.id)
            .all()
        )
    else:
        future_entries = sorted(
            (
                entry
                for (row_day, _category), entry in month_rows.items()
                if transaction_date < row_day <= month_end
            ),
            key=lambda entry: (
                _plan_row_day(entry),
                entry.category or "",
                str(entry.id),
            ),
        )

    if not future_entries:
        logger.info(
            "rebalance: no future entries user=%s cat=%s date=%s",
            user_id,
            overspent_category,
            transaction_date,
        )
        plan.uncovered = overspend_amount
        return plan

    # 2. Group by category, excluding SACRED and the overspent category itself
    future_by_cat: Dict[str, List[DailyPlan]] = {}
    for entry in future_entries:
        cat = entry.category or ""
        if is_sacred(cat) or cat == overspent_category:
            continue
        future_by_cat.setdefault(cat, []).append(entry)

    # 3. Sort donor categories: DISCRETIONARY (3) first → FLEXIBLE (2) → PROTECTED (1)
    sorted_donors = sorted(
        future_by_cat,
        key=lambda category: (-int(get_category_level(category)), category),
    )

    plan.remaining_days = len({e.date for e in future_entries})
    remaining = overspend_amount

    # 4. Take from donors in priority order
    for donor_cat in sorted_donors:
        if remaining < CENT:
            break

        entries = sorted(
            future_by_cat[donor_cat],
            key=lambda entry: (entry.date, str(entry.id)),
        )
        if not entries:
            continue

        total_available = sum(Decimal(str(e.planned_amount or 0)) for e in entries)
        if total_available <= Decimal("0.01"):
            continue

        # Cap at 50% of donor budget to avoid wiping a category
        to_take = min(remaining, total_available * Decimal("0.50")).quantize(
            CENT,
            rounding=ROUND_DOWN,
        )
        if to_take < CENT:
            continue

        available_by_entry = [
            Decimal(str(entry.planned_amount or 0)) for entry in entries
        ]
        cuts = _allocate_cents_with_caps(
            to_take,
            [available * Decimal("0.50") for available in available_by_entry],
        )
        actual = sum(cuts, Decimal("0.00"))

        for entry, available, cut in zip(entries, available_by_entry, cuts):
            if cut <= Decimal("0"):
                continue
            if not dry_run:
                # Use Decimal throughout — never convert to float for financial data
                entry.planned_amount = available - cut
                # The enforceable limit moves with the allocation, otherwise
                # spending checks and the calendar day limit go stale.
                entry.daily_budget = entry.planned_amount
                record_realtime_adjustment(entry, -cut)

        if actual >= CENT:
            plan.transfers.append(
                {
                    "from_category": donor_cat,
                    "amount_per_day": float(
                        (actual / Decimal(len(entries))).quantize(CENT)
                    ),
                    "days_affected": len(entries),
                    "total_taken": float(actual),
                }
            )
            remaining -= actual
            plan.covered += actual
            # Record to audit log — must never break rebalancing
            if not dry_run and record_audit:
                try:
                    record_redistribution_event(
                        db=db,
                        user_id=user_id,
                        from_category=donor_cat,
                        to_category=overspent_category,
                        amount=actual,
                        reason="realtime_rebalance",
                    )
                except Exception as _audit_err:
                    logger.warning(
                        "audit log write failed (non-critical): %s", _audit_err
                    )

    plan.uncovered = max(Decimal("0"), remaining)

    # 5. Credit covered amount back to the overspent entry.
    #    Without this, the overspent day stays "red" even though the
    #    monthly budget has been rebalanced — confusing for the user.
    if not dry_run and plan.covered >= CENT:
        day_start_credit = datetime(
            transaction_date.year,
            transaction_date.month,
            transaction_date.day,
            0,
            0,
            0,
        )
        day_end_credit = datetime(
            transaction_date.year,
            transaction_date.month,
            transaction_date.day,
            23,
            59,
            59,
        )
        if month_rows is None:
            overspent_entry: Optional[DailyPlan] = (
                db.query(DailyPlan)
                .filter(
                    DailyPlan.user_id == user_id,
                    DailyPlan.category == overspent_category,
                    DailyPlan.date >= day_start_credit,
                    DailyPlan.date <= day_end_credit,
                )
                .first()
            )
        else:
            # uq_daily_plan_user_date_category makes this at most one row.
            overspent_entry = month_rows.get((transaction_date, overspent_category))
        if overspent_entry is not None:
            overspent_entry.planned_amount = (
                Decimal(str(overspent_entry.planned_amount or 0)) + plan.covered
            )
            overspent_entry.daily_budget = overspent_entry.planned_amount
            record_realtime_adjustment(overspent_entry, plan.covered)
            logger.debug(
                "rebalance: credited $%.2f to %s on %s",
                float(plan.covered),
                overspent_category,
                transaction_date,
            )

    if not dry_run and plan.covered >= CENT:
        try:
            if commit:
                db.commit()
            else:
                db.flush()
            logger.info(
                "rebalance: %s user=%s overspent=%s covered=%.2f uncovered=%.2f",
                "committed" if commit else "flushed",
                user_id,
                overspent_category,
                float(plan.covered),
                float(plan.uncovered),
            )
        except Exception as exc:
            db.rollback()
            logger.error("rebalance: commit failed: %s", exc)
            raise

    return plan


def check_and_rebalance(
    db: Session,
    user_id: UUID,
    category: str,
    transaction_date: date,
    dry_run: bool = False,
    commit: bool = True,
    record_audit: bool = True,
    month_rows: Optional[Dict] = None,
) -> Optional[RebalancePlan]:
    """
    Check if category is overspent on given date, trigger rebalance if so.
    Call this after recording a transaction. Returns None if no overspend.

    ``month_rows`` lets a caller that already holds the month's plan rows
    (see rebuild_month_plan) skip the per-bucket lookups entirely.
    """
    if month_rows is None:
        # DailyPlan.date is DateTime — match by date range covering the full day
        day_start = datetime(
            transaction_date.year, transaction_date.month, transaction_date.day, 0, 0, 0
        )
        day_end = datetime(
            transaction_date.year,
            transaction_date.month,
            transaction_date.day,
            23,
            59,
            59,
        )

        entry: Optional[DailyPlan] = (
            db.query(DailyPlan)
            .filter(
                DailyPlan.user_id == user_id,
                DailyPlan.category == category,
                DailyPlan.date >= day_start,
                DailyPlan.date <= day_end,
            )
            .first()
        )
    else:
        entry = month_rows.get((transaction_date, category))

    if not entry:
        return None

    planned = Decimal(str(entry.planned_amount or 0))
    spent = Decimal(str(entry.spent_amount or 0))

    if spent <= planned:
        return None

    overspend = spent - planned
    logger.info(
        "check_and_rebalance: overspend user=%s cat=%s amount=%.2f",
        user_id,
        category,
        float(overspend),
    )

    return rebalance_after_overspend(
        db=db,
        user_id=user_id,
        overspent_category=category,
        overspend_amount=overspend,
        transaction_date=transaction_date,
        dry_run=dry_run,
        commit=commit,
        record_audit=record_audit,
        month_rows=month_rows,
    )
