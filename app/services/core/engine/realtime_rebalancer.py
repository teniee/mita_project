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
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.category_priority import get_category_level, is_sacred
from app.db.models.daily_plan import DailyPlan
from app.services.redistribution_audit_log import record_redistribution_event

logger = logging.getLogger(__name__)


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


def rebalance_after_overspend(
    db: Session,
    user_id: UUID,
    overspent_category: str,
    overspend_amount: Decimal,
    transaction_date: date,
    dry_run: bool = False,
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
        23, 59, 59,
    )
    month_end_dt = datetime(month_end.year, month_end.month, month_end.day, 23, 59, 59)

    # 1. Fetch all FUTURE DailyPlan entries in this month (strictly after transaction_date)
    future_entries: List[DailyPlan] = (
        db.query(DailyPlan)
        .filter(
            DailyPlan.user_id == user_id,
            DailyPlan.date > day_start,
            DailyPlan.date <= month_end_dt,
        )
        .order_by(DailyPlan.date)
        .all()
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
        list(future_by_cat.keys()),
        key=lambda c: int(get_category_level(c)),
        reverse=True,
    )

    plan.remaining_days = len({e.date for e in future_entries})
    remaining = overspend_amount

    # 4. Take from donors in priority order
    for donor_cat in sorted_donors:
        if remaining <= Decimal("0.01"):
            break

        entries = sorted(future_by_cat[donor_cat], key=lambda e: e.date)
        if not entries:
            continue

        total_available = sum(Decimal(str(e.planned_amount or 0)) for e in entries)
        if total_available <= Decimal("0.01"):
            continue

        # Cap at 50% of donor budget to avoid wiping a category
        to_take = min(remaining, total_available * Decimal("0.50"))
        if to_take <= Decimal("0.01"):
            continue

        per_entry = (to_take / Decimal(len(entries))).quantize(Decimal("0.01"))
        actual = Decimal("0")

        for entry in entries:
            available = Decimal(str(entry.planned_amount or 0))
            cut = min(per_entry, available * Decimal("0.50"))
            if cut <= Decimal("0.01"):
                continue
            if not dry_run:
                # Use Decimal throughout — never convert to float for financial data
                entry.planned_amount = available - cut
            actual += cut

        if actual > Decimal("0.01"):
            plan.transfers.append(
                {
                    "from_category": donor_cat,
                    "amount_per_day": float(per_entry),
                    "days_affected": len(entries),
                    "total_taken": float(actual),
                }
            )
            remaining -= actual
            plan.covered += actual
            # Record to audit log — must never break rebalancing
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
                logger.warning("audit log write failed (non-critical): %s", _audit_err)

    plan.uncovered = max(Decimal("0"), remaining)

    # 5. Credit covered amount back to the overspent entry.
    #    Without this, the overspent day stays "red" even though the
    #    monthly budget has been rebalanced — confusing for the user.
    if not dry_run and plan.covered > Decimal("0.01"):
        day_start_credit = datetime(
            transaction_date.year,
            transaction_date.month,
            transaction_date.day,
            0, 0, 0,
        )
        day_end_credit = datetime(
            transaction_date.year,
            transaction_date.month,
            transaction_date.day,
            23, 59, 59,
        )
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
        if overspent_entry is not None:
            overspent_entry.planned_amount = (
                Decimal(str(overspent_entry.planned_amount or 0)) + plan.covered
            )
            logger.debug(
                "rebalance: credited $%.2f to %s on %s",
                float(plan.covered), overspent_category, transaction_date,
            )

    if not dry_run and plan.covered > Decimal("0.01"):
        try:
            db.commit()
            logger.info(
                "rebalance: committed user=%s overspent=%s covered=%.2f uncovered=%.2f",
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
) -> Optional[RebalancePlan]:
    """
    Check if category is overspent on given date, trigger rebalance if so.
    Call this after recording a transaction. Returns None if no overspend.
    """
    # DailyPlan.date is DateTime — match by date range covering the full day
    day_start = datetime(transaction_date.year, transaction_date.month, transaction_date.day, 0, 0, 0)
    day_end = datetime(transaction_date.year, transaction_date.month, transaction_date.day, 23, 59, 59)

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
    )
