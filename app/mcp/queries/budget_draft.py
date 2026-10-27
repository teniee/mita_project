"""A monthly budget draft, computed (never stored) from what MITA knows.

Inputs, in priority order — every one read from the database, none from the
model: the user's stated monthly net income; their saved repeating
obligations (scheduled expenses); their monthly savings target; the canonical
engine (``monthly_plan_service.allocations_from_profile`` →
``generate_budget_from_answers``, laid out by ``distribute_budget_over_days``).
Recorded history only produces warnings: it never changes an allocation.
No regional cost data, no income-class labels, no LLM.

The draft's digest covers exactly what would be saved (allocations and the
day-by-day layout). ``save_monthly_budget`` recomputes the draft from the
same inputs and saves it only if the digest is unchanged — so what the user
reviewed is, byte for byte, what is saved, and a draft can never be edited
in transit (see ``app/mcp/crypto.py`` for the signed token).
"""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense
from app.mcp.errors import ValidationError
from app.mcp.queries import ledger
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.calendar_engine import CATEGORY_BEHAVIOR
from app.services.monthly_obligations import due_in_month, weekday_count
from app.services.monthly_plan_service import (
    ProfileAllocation,
    allocations_from_profile,
    month_base_plan,
    month_calendar,
)

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HISTORY_MONTHS = 3
# How long a reviewed preview stays savable. Integrity does not depend on it —
# save_monthly_budget rebuilds the draft under the ledger lock and compares the
# digest, refuses changed inputs and a month that has ended — so this only
# bounds how stale a confirmation may be: one sitting, including a pause to
# check other figures before saying yes.
DRAFT_TTL = timedelta(hours=2)
UNSTATED_REGIONS = {None, "", "ZZ"}


@dataclass(frozen=True)
class Obligation:
    name: Optional[str]
    category: str
    amount: Decimal  # counted in this month
    basis: str


@dataclass(frozen=True)
class HistorySummary:
    months_used: int
    period_start: Optional[date]
    period_end: Optional[date]
    average_monthly_spending: Optional[Decimal]
    category_averages: Dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetDraft:
    year: int
    month: int
    income: Decimal
    savings_requested: Decimal
    obligations: List[Obligation]
    allocation: ProfileAllocation
    calendar_map: Dict[str, Dict[str, Decimal]]
    digest: bytes
    existing_plan: bool
    history: HistorySummary

    @property
    def plan_total(self) -> Decimal:
        return sum(self.allocation.allocations.values(), ZERO)

    @property
    def fixed_total(self) -> Decimal:
        return sum(self.allocation.fixed.values(), ZERO)

    @property
    def days_in_month(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    @property
    def daily_flexible_average(self) -> Decimal:
        return (self.allocation.discretionary_total / self.days_in_month).quantize(
            CENT, rounding=ROUND_HALF_UP
        )

    def calendar_entries(self) -> Dict[Tuple[date, str], Decimal]:
        return {
            (date.fromisoformat(day), category): Decimal(str(amount))
            for day, categories in self.calendar_map.items()
            for category, amount in categories.items()
        }


def _months_after(year: int, month: int, count: int) -> Tuple[int, int]:
    index = year * 12 + (month - 1) + count
    return index // 12, index % 12 + 1


def target_month(ctx: UserContext, month: Optional[str]) -> Tuple[int, int]:
    """'YYYY-MM' limited to the user's current or next month."""
    current = (ctx.today.year, ctx.today.month)
    allowed = (current, _months_after(*current, 1))
    if month is None:
        return current
    try:
        year, number = (int(part) for part in month.split("-"))
    except ValueError:
        raise ValidationError("month must be written YYYY-MM.") from None
    if (year, number) not in allowed:
        raise ValidationError(
            f"A budget can be planned for the current month ({allowed[0][0]}-"
            f"{allowed[0][1]:02d}) or the next one ({allowed[1][0]}-{allowed[1][1]:02d})."
        )
    return year, number


def obligations_for_month(
    db: Session, ctx: UserContext, year: int, month: int
) -> List[Obligation]:
    """The user's saved obligations that fall in this month.

    Repeating ones count for the whole month when they are already running
    (next due date before the end of the following month); a weekly one
    counts once per matching weekday of the month. One-time ones count only
    when dated inside the month.
    """
    rows = db.execute(
        select(
            ScheduledExpense.merchant,
            ScheduledExpense.category,
            ScheduledExpense.amount,
            ScheduledExpense.scheduled_date,
            ScheduledExpense.recurrence,
        )
        .where(
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
        )
        .order_by(ScheduledExpense.scheduled_date, ScheduledExpense.category)
    ).all()
    found: List[Obligation] = []
    for merchant, category, amount, due, recurrence in rows:
        amount = Decimal(str(amount))
        name = (merchant or "").strip() or None
        counted = due_in_month(amount, due, recurrence, year, month)
        if counted <= ZERO:
            continue
        if recurrence == "monthly":
            basis = "monthly"
        elif recurrence == "weekly":
            count = weekday_count(year, month, due.weekday())
            basis = f"weekly × {count} {calendar.day_name[due.weekday()]}s"
        else:
            basis = f"one-time on {due.isoformat()}"
        found.append(Obligation(name, category, counted, basis))
    return found


def history_before(
    db: Session, ctx: UserContext, year: int, month: int
) -> HistorySummary:
    """Recorded spending in up to three complete months before the target,
    counting only months on or after the user's first recorded expense."""
    first_recorded = ledger.first_expense_day(db, ctx)
    if first_recorded is None:
        return HistorySummary(0, None, None, None)
    months: List[Tuple[int, int]] = []
    for back in range(HISTORY_MONTHS, 0, -1):
        y, m = _months_after(year, month, -back)
        if (y, m) >= (first_recorded.year, first_recorded.month) and (y, m) < (
            ctx.today.year,
            ctx.today.month,
        ):
            months.append((y, m))
    if not months:
        return HistorySummary(0, None, None, None)
    start = date(*months[0], 1)
    end = month_days(*months[-1])[1]
    totals = ledger.totals_by_category(db, ctx, start, end)
    count = Decimal(len(months))
    overall = sum((t.total for t in totals), ZERO)
    return HistorySummary(
        months_used=len(months),
        period_start=start,
        period_end=end,
        average_monthly_spending=(overall / count).quantize(CENT, ROUND_HALF_UP),
        category_averages={
            t.category: (t.total / count).quantize(CENT, ROUND_HALF_UP) for t in totals
        },
    )


def _digest(
    year: int, month: int, allocation: ProfileAllocation, calendar_map
) -> bytes:
    canonical = {
        "month": f"{year:04d}-{month:02d}",
        "allocations": sorted(
            (category, str(amount))
            for category, amount in allocation.allocations.items()
        ),
        "days": sorted(
            (day, category, str(Decimal(str(amount))))
            for day, categories in calendar_map.items()
            for category, amount in categories.items()
        ),
    }
    text = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(text.encode()).digest()


def build_draft(db: Session, ctx: UserContext, year: int, month: int) -> BudgetDraft:
    if not setup_queries.income_set(ctx) or ctx.stated_monthly_income is None:
        raise ValidationError(
            "MITA needs the user's monthly net income to build a budget. Ask for it "
            "and save it with update_financial_profile first."
        )
    if not setup_queries.currency_set(ctx):
        raise ValidationError(
            "MITA does not know the user's currency yet. Ask for it and save it "
            "with update_financial_profile first."
        )
    income = ctx.stated_monthly_income
    savings = setup_queries.known_monthly_savings(ctx) or ZERO
    if savings >= income:
        savings = ZERO  # the same clamp the rollover path applies
    obligations = obligations_for_month(db, ctx, year, month)
    fixed: Dict[str, Decimal] = {}
    for item in obligations:
        fixed[item.category] = fixed.get(item.category, ZERO) + item.amount
    try:
        allocation = allocations_from_profile(
            monthly_income=income,
            savings_goal=savings,
            region=ctx.region,
            fixed_expenses=fixed,
        )
    except ValueError:
        raise ValidationError(
            "The user's saved repeating obligations add up to more than their "
            "stated monthly net income, so MITA cannot build a budget. Check both "
            "with the user."
        ) from None
    calendar_map = month_calendar(year, month, allocation.allocations)
    return BudgetDraft(
        year=year,
        month=month,
        income=income,
        savings_requested=savings,
        obligations=obligations,
        allocation=allocation,
        calendar_map=calendar_map,
        digest=_digest(year, month, allocation, calendar_map),
        existing_plan=bool(month_base_plan(db, ctx.user_id, year, month)),
        history=history_before(db, ctx, year, month),
    )


def layout_of(category: str) -> str:
    return CATEGORY_BEHAVIOR.get(category, "spread")


def region_note(region: Optional[str]) -> str:
    if region in UNSTATED_REGIONS:
        return "No region is stated, so MITA's default allocation rules are used."
    return f"MITA's allocation rules for region {region} are used."
