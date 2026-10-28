"""A monthly budget draft, computed (never stored) from what MITA knows.

Inputs, in priority order — every one read from the database, none from the
model: the user's stated monthly net income; their saved repeating
obligations (scheduled expenses); their monthly savings target; the canonical
engine (``monthly_plan_service.allocations_from_profile`` →
``generate_budget_from_answers``, laid out by ``distribute_budget_over_days``).
Recorded history only produces warnings: it never changes an allocation.
No regional cost data, no income-class labels, no LLM.

Budget lines the user names and sets themselves (F-11: "Fuel €200",
"Cigarettes €200") are kept exactly — the month's saved lines plus the ones
asked for in this preview — and MITA allocates only the money left, leaving
out its own lines that a user line replaces (``mcp_budget_lines``).
ChatGPT decides what the user's words mean; nothing here interprets them.

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
from typing import Dict, FrozenSet, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense
from app.mcp.categories import PLAN_LABELS, label, source_of
from app.mcp.crypto import DraftClaims
from app.mcp.errors import ValidationError
from app.mcp.queries import budget_lines, ledger
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.calendar_engine import CATEGORY_BEHAVIOR
from app.services.core.engine.user_budget_lines import PlanDoesNotFit, is_user_line
from app.services.monthly_obligations import due_in_month, weekday_count
from app.services.monthly_plan_service import (
    ProfileAllocation,
    allocations_from_profile,
    latest_plan_month_before,
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


# One requested line: (name or line key, monthly amount, MITA lines it
# replaces — None keeps the saved choice for an existing line).
RequestLine = Tuple[str, Decimal, Optional[Tuple[str, ...]]]


@dataclass(frozen=True)
class DraftRequest:
    """The user's own budget lines asked for in a preview (F-11), and lines
    to take out of the month's plan."""

    lines: Tuple[RequestLine, ...] = ()
    remove: Tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.lines or self.remove)

    def claims(self, year: int, month: int, expires: int, digest: bytes) -> DraftClaims:
        return DraftClaims(
            year,
            month,
            expires,
            digest,
            tuple(
                (key, format(amount, "f"), replaces)
                for key, amount, replaces in self.lines
            ),
            self.remove,
        )

    @classmethod
    def from_claims(cls, claims: DraftClaims) -> "DraftRequest":
        return cls(
            tuple(
                (key, Decimal(amount), replaces)
                for key, amount, replaces in claims.lines
            ),
            tuple(claims.remove),
        )


@dataclass(frozen=True)
class LineChange:
    category: str
    before: Optional[Decimal]
    after: Optional[Decimal]


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
    # The request with every name resolved to its line key (what the token
    # carries), MITA's lines each user line replaces, what differs from the
    # saved month, and notes for the user.
    request: DraftRequest = field(default_factory=DraftRequest)
    replaces: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    changes: Tuple[LineChange, ...] = ()
    notes: Tuple[str, ...] = ()

    @property
    def user_lines(self) -> FrozenSet[str]:
        return frozenset(self.allocation.manual)

    @property
    def user_set_total(self) -> Decimal:
        return sum(self.allocation.manual.values(), ZERO)

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
        """Spending money a day: MITA's flexible part and the user's own lines."""
        flexible = self.allocation.discretionary_total + self.user_set_total
        return (flexible / self.days_in_month).quantize(CENT, rounding=ROUND_HALF_UP)

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
    year: int,
    month: int,
    allocation: ProfileAllocation,
    calendar_map,
    replaces: Optional[Dict[str, Tuple[str, ...]]] = None,
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
    if allocation.manual:
        # Only with user lines: a plan without them keeps the digest a bd1_
        # token issued before F-11 was signed over.
        canonical["lines"] = sorted(
            (key, sorted((replaces or {}).get(key, ()))) for key in allocation.manual
        )
    text = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(text.encode()).digest()


PLAN_DOES_NOT_FIT = (
    "The user's own budget lines, their bills and fixed payments and their "
    "savings target add up to more than their stated monthly net income "
    "({excess} over), so MITA prepared nothing. Tell the user each part "
    "(details) and ask what to change; never lower their amounts yourself."
)


def _user_lines(
    db: Session,
    ctx: UserContext,
    month_label: str,
    saved_totals: Dict[str, Decimal],
    request: DraftRequest,
) -> Tuple[Dict[str, Decimal], Dict[str, Tuple[str, ...]], DraftRequest]:
    """The month's user lines after the request: ``({key: amount}, {key:
    MITA lines it replaces}, the request with names resolved to keys)``."""
    if request.empty and not any(is_user_line(c) for c in saved_totals):
        return {}, {}, request  # an automatic-only budget, as before F-11
    stored = budget_lines.stored_lines(db, ctx)
    known = set(stored) | {c for c in saved_totals if is_user_line(c)}
    lines = {c: a for c, a in saved_totals.items() if is_user_line(c)}
    replaces = {key: stored.get(key, ()) for key in lines}

    removed: List[str] = []
    for name in request.remove:
        key = budget_lines.key_for(name, known)
        if key not in lines:
            raise ValidationError(
                f"{label(key)} is not one of the user's budget lines in "
                f"{month_label}'s plan.",
                details={"reason": "unknown_budget_line"},
            )
        lines.pop(key)
        replaces.pop(key, None)
        removed.append(key)

    resolved: List[RequestLine] = []
    named = set()
    for name, amount, replaced in request.lines:
        key = budget_lines.key_for(name, known)
        if key.casefold() in named or key in removed:
            raise ValidationError(
                f"{label(key)} is named more than once. Give each budget line "
                "once: one amount, or remove it.",
                details={"reason": "duplicate_budget_line"},
            )
        named.add(key.casefold())
        known.add(key)
        lines[key] = amount
        if replaced is not None:
            replaces[key] = tuple(sorted(set(replaced)))
        else:
            replaces[key] = stored.get(key, replaces.get(key, ()))
        resolved.append((key, amount, replaced))
    return lines, replaces, DraftRequest(tuple(resolved), tuple(removed))


def _same_name_notes(allocation: ProfileAllocation) -> List[str]:
    """A user line named like one of MITA's lines still in the plan."""
    notes = []
    for key in sorted(allocation.manual):
        folded = label(key).casefold()
        for bucket in sorted(allocation.discretionary):
            if PLAN_LABELS.get(bucket, "").casefold() == folded:
                notes.append(
                    f"The user's line '{label(key)}' has the same name as MITA's "
                    f"'{PLAN_LABELS[bucket]}' line ({bucket}), which is still in "
                    "the plan. If they are the same spending, preview again with "
                    f"replaces ['{bucket}'] for the user's line, so it is not "
                    "budgeted twice."
                )
    return notes


def build_draft(
    db: Session,
    ctx: UserContext,
    year: int,
    month: int,
    request: DraftRequest = DraftRequest(),
) -> BudgetDraft:
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

    saved = month_base_plan(db, ctx.user_id, year, month)
    saved_totals = _by_category(saved)
    notes: List[str] = []
    line_totals = saved_totals
    if not saved:
        # No plan for the month yet: the user's own lines continue from their
        # latest month, as MITA's rollover carries a month forward.
        template = latest_plan_month_before(db, ctx.user_id, year, month)
        if template is not None:
            line_totals = {
                c: a
                for c, a in _by_category(
                    month_base_plan(db, ctx.user_id, *template)
                ).items()
                if is_user_line(c)
            }
            if line_totals:
                notes.append(
                    "The user's own budget lines from "
                    f"{template[0]:04d}-{template[1]:02d} continue in this month."
                )
    lines, replaces, resolved = _user_lines(
        db, ctx, f"{year:04d}-{month:02d}", line_totals, request
    )
    try:
        allocation = allocations_from_profile(
            monthly_income=income,
            savings_goal=savings,
            region=ctx.region,
            fixed_expenses=fixed,
            manual_allocations=lines,
            replaced_buckets={code for codes in replaces.values() for code in codes},
        )
    except PlanDoesNotFit as error:
        details = {"reason": "plan_exceeds_income", "currency": ctx.currency}
        details.update(error.conflict.details())
        raise ValidationError(
            PLAN_DOES_NOT_FIT.format(excess=format(error.conflict.excess, "f")),
            details=details,
        ) from None
    except ValueError:
        raise ValidationError(
            "The user's saved repeating obligations add up to more than their "
            "stated monthly net income, so MITA cannot build a budget. Check both "
            "with the user."
        ) from None
    calendar_map = month_calendar(year, month, allocation.allocations)
    changes = tuple(
        LineChange(
            category, saved_totals.get(category), allocation.allocations.get(category)
        )
        for category in sorted(
            set(saved_totals) | set(allocation.allocations),
            key=lambda c: (source_of(c) != "set_by_you", c),
        )
        if saved and saved_totals.get(category) != allocation.allocations.get(category)
    )
    return BudgetDraft(
        year=year,
        month=month,
        income=income,
        savings_requested=savings,
        obligations=obligations,
        allocation=allocation,
        calendar_map=calendar_map,
        digest=_digest(year, month, allocation, calendar_map, replaces),
        existing_plan=bool(saved),
        history=history_before(db, ctx, year, month),
        request=resolved,
        replaces={key: replaces.get(key, ()) for key in allocation.manual},
        changes=changes,
        notes=tuple(notes + _same_name_notes(allocation)),
    )


def _by_category(plan: Dict[Tuple[date, str], Decimal]) -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = {}
    for (_, category), amount in plan.items():
        totals[category] = totals.get(category, ZERO) + amount
    return totals


def layout_of(category: str) -> str:
    return CATEGORY_BEHAVIOR.get(category, "spread")


def region_note(region: Optional[str]) -> str:
    if region in UNSTATED_REGIONS:
        return "No region is stated, so MITA's default allocation rules are used."
    return f"MITA's allocation rules for region {region} are used."
