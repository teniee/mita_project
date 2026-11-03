"""A monthly budget draft, computed (never stored) from what MITA knows.

Inputs, in priority order — every one read from the database, none from the
model: the user's stated monthly net income; their saved repeating
obligations (scheduled expenses); their monthly savings target; the canonical
engine (``monthly_plan_service.allocations_from_profile`` →
``generate_budget_from_answers``, laid out by ``distribute_budget_over_days``).
Each saved obligation is planned in full on its due dates
(``monthly_obligations.due_dates_in_month``; owner decision 2026-11-02, F-8),
never spread over other days.
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
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScheduledExpense
from app.mcp.categories import PLAN_LABELS, label, source_of
from app.mcp.crypto import DraftClaims
from app.mcp.errors import ValidationError
from app.mcp.queries import budget_lines, ledger
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.spending_schedule import (
    KIND_NOT_APPLICABLE,
    PatternError,
    SpendingPattern,
    purchase_dates,
)
from app.services.core.engine.user_budget_lines import (
    ENGINE_BUCKETS,
    PlanDoesNotFit,
    is_user_line,
)
from app.services.monthly_obligations import due_dates_in_month
from app.services.monthly_plan_service import (
    ProfileAllocation,
    allocations_from_profile,
    behavioral_month_calendar,
    latest_plan_month_before,
    month_base_plan,
)
from app.services.obligation_lines import bill_key, is_bill_key
from app.services.spending_patterns import not_applicable, stored_patterns

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
    # the dates it is due on in the month, each for ``unit_amount``
    due_dates: Tuple[date, ...] = ()
    unit_amount: Decimal = ZERO
    obligation_id: Optional[UUID] = None  # scheduled_expenses.id

    @property
    def line(self) -> str:
        """Its own plan line (``obligation_lines``): its money never shares
        a row with everyday money of the same category."""
        return bill_key(self.obligation_id) if self.obligation_id else self.category


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
# One requested spending pattern: (line name or key, how it is bought).
RequestPattern = Tuple[str, SpendingPattern]


def _pattern_claim(name: str, p: SpendingPattern):
    return (
        name,
        p.kind,
        p.frequency,
        tuple(p.weekdays),
        tuple(p.days_of_month),
        p.times_per_month,
        p.anchor_date.isoformat() if p.anchor_date else None,
        format(p.typical_amount, "f") if p.typical_amount is not None else None,
    )


def _pattern_from_claim(claim) -> RequestPattern:
    name, kind, freq, wd, dom, times, anchor, typical = claim
    return name, SpendingPattern(
        kind=kind,
        frequency=freq,
        weekdays=tuple(wd),
        days_of_month=tuple(dom),
        times_per_month=times,
        anchor_date=date.fromisoformat(anchor) if anchor else None,
        typical_amount=Decimal(typical) if typical is not None else None,
    )


@dataclass(frozen=True)
class DraftRequest:
    """The user's own budget lines asked for in a preview (F-11), lines to
    take out of the month's plan, and how the user buys for a line (spending
    patterns, saved with the plan)."""

    lines: Tuple[RequestLine, ...] = ()
    remove: Tuple[str, ...] = ()
    patterns: Tuple[RequestPattern, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.lines or self.remove or self.patterns)

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
            tuple(_pattern_claim(name, p) for name, p in self.patterns),
        )

    @classmethod
    def from_claims(cls, claims: DraftClaims) -> "DraftRequest":
        return cls(
            tuple(
                (key, Decimal(amount), replaces)
                for key, amount, replaces in claims.lines
            ),
            tuple(claims.remove),
            tuple(_pattern_from_claim(c) for c in claims.patterns),
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
    # How each line's money is laid out (spending_schedule.LINE_KINDS) and
    # the stated pattern behind it; where it came from (the user's saved
    # pattern, or this preview); MITA lines the user said do not apply.
    line_kinds: Dict[str, str] = field(default_factory=dict)
    patterns: Dict[str, SpendingPattern] = field(default_factory=dict)
    pattern_sources: Dict[str, str] = field(default_factory=dict)
    not_applicable: Tuple[str, ...] = ()

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
            ScheduledExpense.id,
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
        .order_by(
            ScheduledExpense.scheduled_date,
            ScheduledExpense.category,
            ScheduledExpense.id,
        )
    ).all()
    found: List[Obligation] = []
    for obligation_id, merchant, category, amount, due, recurrence in rows:
        amount = Decimal(str(amount))
        name = (merchant or "").strip() or None
        dates = tuple(due_dates_in_month(due, recurrence, year, month))
        counted = amount * len(dates)
        if counted <= ZERO:
            continue
        if recurrence == "monthly":
            basis = "monthly"
        elif recurrence == "weekly":
            basis = f"weekly × {len(dates)} {calendar.day_name[due.weekday()]}s"
        else:
            basis = f"one-time on {due.isoformat()}"
        found.append(
            Obligation(name, category, counted, basis, dates, amount, obligation_id)
        )
    return found


def dated_bills(obligations: List[Obligation]) -> List[Tuple[date, str, Decimal]]:
    """``(due date, plan line, amount)`` for every date an obligation is due
    on: what ``month_calendar`` places in full on those dates."""
    return [
        (day, item.line, item.unit_amount)
        for item in obligations
        for day in item.due_dates
    ]


def comparable_saved_totals(
    saved_totals: Dict[str, Decimal], obligations: List[Obligation]
) -> Tuple[Dict[str, Decimal], bool]:
    """The saved month's line totals as the draft names its lines, and
    whether a legacy plan's obligations were re-keyed to compare them.

    A plan saved before obligations had lines of their own holds each saved
    payment's money under its category (``transportation`` 270.00 for the
    car loan). When a category holds exactly what its obligations ask for,
    it is those obligations: compared on their own lines, it is unchanged.
    """
    if any(is_bill_key(c) for c in saved_totals):
        return dict(saved_totals), False
    by_category: Dict[str, List[Obligation]] = {}
    for item in obligations:
        by_category.setdefault(item.category, []).append(item)
    out = dict(saved_totals)
    rekeyed = False
    for category, items in by_category.items():
        if out.get(category) == sum((i.amount for i in items), ZERO):
            out.pop(category)
            for item in items:
                out[item.line] = out.get(item.line, ZERO) + item.amount
            rekeyed = True
    return out, rekeyed


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
    kinds: Optional[Dict[str, str]] = None,
    patterns: Optional[Dict[str, SpendingPattern]] = None,
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
    if kinds:
        # What each line is (a planned purchase and a flexible budget can
        # share dates) and the patterns that would be saved with the plan.
        canonical["kinds"] = sorted(kinds.items())
        canonical["patterns"] = sorted(
            _pattern_claim(line, pattern) for line, pattern in (patterns or {}).items()
        )
    text = json.dumps(canonical, separators=(",", ":"), default=str)
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
        fixed[item.line] = fixed.get(item.line, ZERO) + item.amount

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
    # How the user buys for each line: their saved patterns, overridden by
    # the ones asked for in this preview (saved with the plan).
    stored = stored_patterns(db, ctx.user_id)
    asked = _requested_patterns(request.patterns, lines)
    patterns: Dict[str, SpendingPattern] = {
        line: p for line, p in stored.items() if line in lines or line in ENGINE_BUCKETS
    }
    patterns.update(asked)
    # A line of the user's own that takes the place of one of MITA's lines
    # keeps how the user said they buy for it ("groceries every Wednesday",
    # then "my groceries are €200"), unless it has a pattern of its own.
    for key in lines:
        if key in patterns:
            continue
        inherited = [
            patterns[code]
            for code in replaces.get(key, ())
            if code in patterns and patterns[code].kind != KIND_NOT_APPLICABLE
        ]
        if len(inherited) == 1:
            patterns[key] = inherited[0]
    sources = {line: (ASKED if line in asked else SAVED) for line in patterns}
    excluded = tuple(sorted(not_applicable(patterns)))
    try:
        allocation = allocations_from_profile(
            monthly_income=income,
            savings_goal=savings,
            region=ctx.region,
            fixed_expenses=fixed,
            manual_allocations=lines,
            replaced_buckets={code for codes in replaces.values() for code in codes}
            | set(excluded),
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
    calendar_map, kinds = behavioral_month_calendar(
        year, month, allocation.allocations, dated_bills(obligations), patterns
    )
    shown = {
        line: p
        for line, p in patterns.items()
        if line in allocation.allocations or line in excluded
    }
    for line, pattern in sorted(shown.items()):
        if (
            pattern.typical_amount is not None
            and kinds.get(line) == "planned"
            and line in allocation.allocations
        ):
            dates = purchase_dates(pattern, year, month)
            each = (allocation.allocations[line] / len(dates)).quantize(
                CENT, ROUND_HALF_UP
            )
            if dates and abs(each - pattern.typical_amount) >= CENT:
                notes.append(
                    f"{label(line)}: {len(dates)} purchases this month of about "
                    f"{format(each, 'f')} each from its monthly amount; the user "
                    f"said a purchase is usually {format(pattern.typical_amount, 'f')}."
                )
    compared, rekeyed = comparable_saved_totals(saved_totals, obligations)
    if saved and rekeyed:
        notes.append(OWN_LINES_NOTE.format(month=f"{year:04d}-{month:02d}"))
    if (
        saved
        and compared == allocation.allocations
        and saved != _entries(calendar_map)
        and not rekeyed
    ):
        notes.append(LAYOUT_ONLY_NOTE.format(month=f"{year:04d}-{month:02d}"))
    changes = tuple(
        LineChange(
            category, compared.get(category), allocation.allocations.get(category)
        )
        for category in sorted(
            set(compared) | set(allocation.allocations),
            key=lambda c: (source_of(c) != "set_by_you", c),
        )
        if saved and compared.get(category) != allocation.allocations.get(category)
    )
    return BudgetDraft(
        year=year,
        month=month,
        income=income,
        savings_requested=savings,
        obligations=obligations,
        allocation=allocation,
        calendar_map=calendar_map,
        digest=_digest(year, month, allocation, calendar_map, replaces, kinds, asked),
        existing_plan=bool(saved),
        history=history_before(db, ctx, year, month),
        request=DraftRequest(
            resolved.lines,
            resolved.remove,
            tuple(sorted(asked.items())),
        ),
        replaces={key: replaces.get(key, ()) for key in allocation.manual},
        changes=changes,
        notes=tuple(notes + _same_name_notes(allocation)),
        line_kinds=kinds,
        patterns=shown,
        pattern_sources={line: sources[line] for line in shown},
        not_applicable=excluded,
    )


# Where a line's pattern came from.
SAVED = "saved"  # the user stated it earlier (spending_patterns)
ASKED = "this_preview"  # stated now, saved with the plan


def resolve_line(name: str, user_lines) -> str:
    """The plan line a name refers to: one of the user's own lines (by name
    or ``my:`` key), else one of MITA's lines (by code or display name)."""
    text = " ".join(str(name or "").split())
    folded = text.casefold()
    for key in user_lines:
        if folded in (key.casefold(), label(key).casefold()):
            return key
    for code in ENGINE_BUCKETS:
        if folded in (code.casefold(), PLAN_LABELS.get(code, "").casefold()):
            return code
    raise ValidationError(
        f"'{text[:60]}' is not a line of this plan. Name one of the user's own "
        "lines (budget_lines) or one of MITA's lines "
        f"({', '.join(sorted(ENGINE_BUCKETS))}).",
        details={"reason": "unknown_budget_line"},
    )


def _requested_patterns(
    requested: Tuple[RequestPattern, ...], user_lines
) -> Dict[str, SpendingPattern]:
    found: Dict[str, SpendingPattern] = {}
    for name, pattern in requested:
        line = resolve_line(name, user_lines)
        if line in found:
            raise ValidationError(
                f"{label(line)} has more than one spending pattern. Give each "
                "line one pattern.",
                details={"reason": "duplicate_pattern"},
            )
        try:
            pattern = pattern.validated()
        except PatternError as error:
            raise ValidationError(f"{label(line)}: {error}") from None
        if pattern.kind == KIND_NOT_APPLICABLE and line not in ENGINE_BUCKETS:
            raise ValidationError(
                f"{label(line)} is the user's own line: to take it out of the "
                "plan, use remove_lines.",
                details={"reason": "not_applicable_user_line"},
            )
        found[line] = pattern
    return found


OWN_LINES_NOTE = (
    "The plan saved for {month} kept the user's regular payments under their "
    "categories. Saving this preview gives each saved payment a line of its "
    "own (same amount, on its due dates): only an expense the user says paid "
    "it settles it — other spending in the same category no longer does."
)

LAYOUT_ONLY_NOTE = (
    "No amount differs from the plan saved for {month}. Saving this preview "
    "changes only the day-by-day plan: each saved bill is planned in full on "
    "its due date (the saved plan spread some of them over other dates)."
)


def _entries(calendar_map) -> Dict[Tuple[date, str], Decimal]:
    return {
        (date.fromisoformat(day), category): Decimal(str(amount))
        for day, categories in calendar_map.items()
        for category, amount in categories.items()
    }


def _by_category(plan: Dict[Tuple[date, str], Decimal]) -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = {}
    for (_, category), amount in plan.items():
        totals[category] = totals.get(category, ZERO) + amount
    return totals


def region_note(region: Optional[str]) -> str:
    if region in UNSTATED_REGIONS:
        return "No region is stated, so MITA's default allocation rules are used."
    return f"MITA's allocation rules for region {region} are used."
