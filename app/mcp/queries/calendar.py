"""One month of the user's money, day by day: MITA's financial calendar.

Read-only. Every figure is a sum of stored rows — ``daily_plan`` allocations,
the ledger's non-deleted expenses keyed by local day, the user's saved
regular payments — or what MITA's forecast engine computes from the same rows
(``plan.forecast_from_rows``, the code behind ``get_budget_forecast``).
Nothing is projected per day: a future date shows its plan, never a forecast
of what will be spent on it. Definitions and limits:
docs/chatgpt-app/financial-calendar.md.

The month's budget lines are the ones ``get_budget_status`` shows
(``categories.group_lines``), and each line belongs to exactly one group, so
the groups always add up to the plan (owner decision 2026-10-24):

* **set aside** — savings, goal reservations, investments
  (``category_priority.SET_ASIDE_CATEGORIES``). Never spendable; shown apart
  from every day's spending plan, as in ``get_budget_status.today``.
* **commitments** — the essentials MITA never takes money from
  (``CATEGORY_PRIORITY`` SACRED and not set aside: rent, mortgage, utilities,
  debt repayment, medical insurance, school fees, online courses) plus the
  lines of the categories of the user's saved regular payments that belong
  to the month (``counts_in_month``: the reviewed budget's own rule).
* **everyday** — every other line, including spending with no plan behind it.

A day's ``over`` / ``within`` state compares EVERYDAY spending with that
date's everyday plan: rent planned on the 1st and paid on the 3rd is a
commitment paid, not €850 of overspending on the 3rd. A date with no everyday
plan is never "over" (the dashboard rule: no allocation, no verdict).

The pure ``build_calendar`` takes plain inputs so the sign-in page's
fictional example runs through exactly this code (tests_mcp/test_auth_ui.py).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from app.core.category_priority import is_sacred, is_set_aside
from app.db.models import ScheduledExpense
from app.mcp.categories import group_lines, line_key
from app.mcp.queries import ledger, plan
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.budget_forecast_engine import ForecastResult
from app.services.monthly_plan_service import month_has_plan

ZERO = Decimal("0.00")

GROUP_SET_ASIDE = "set_aside"
GROUP_COMMITMENT = "commitment"
GROUP_EVERYDAY = "everyday"
ALL_GROUPS = (GROUP_SET_ASIDE, GROUP_COMMITMENT, GROUP_EVERYDAY)

# ScheduledExpenseIn: recurrence in {"once", "weekly", "monthly"} or null.
MONTHLY = "monthly"
WEEKLY = "weekly"


@dataclass(frozen=True)
class SavedPayment:
    """One pending regular or one-time payment the user saved in MITA."""

    category: str
    amount: Decimal
    merchant: Optional[str]
    anchor: date  # scheduled_date: the next date the user scheduled it for
    recurrence: Optional[str]


@dataclass(frozen=True)
class BillOccurrence:
    day: date
    category: str
    amount: Decimal
    merchant: Optional[str]
    recurrence: Optional[str]  # "monthly" | "weekly" | None (one-time)


@dataclass(frozen=True)
class DayLine:
    line: str
    planned: Decimal
    spent: Decimal


@dataclass(frozen=True)
class CalendarDay:
    day: date
    kind: str  # past | today | future
    planned: Decimal  # every line except set-aside ones
    planned_everyday: Decimal
    set_aside: Decimal
    spent: Decimal
    spent_everyday: Decimal
    lines: Tuple[DayLine, ...]

    @property
    def planned_commitments(self) -> Decimal:
        return self.planned - self.planned_everyday

    @property
    def spent_commitments(self) -> Decimal:
        return self.spent - self.spent_everyday

    @property
    def status(self) -> str:
        """over | within | unplanned | quiet for a day that has begun;
        planned | free for a date still ahead."""
        if self.kind == "future":
            return "planned" if self.planned_everyday > ZERO else "free"
        if self.planned_everyday > ZERO:
            return "over" if self.spent_everyday > self.planned_everyday else "within"
        return "unplanned" if self.spent_everyday > ZERO else "quiet"

    @property
    def everyday_left(self) -> Optional[Decimal]:
        """Everyday plan minus everyday spending, for a day that has begun and
        had an everyday plan; negative when over."""
        if self.kind == "future" or self.planned_everyday <= ZERO:
            return None
        return self.planned_everyday - self.spent_everyday


@dataclass(frozen=True)
class CalendarLine:
    key: str
    label: str
    codes: Tuple[str, ...]
    group: str
    planned: Decimal
    spent: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.planned - self.spent


@dataclass(frozen=True)
class CalendarBill:
    occurrence: BillOccurrence
    line: str
    in_plan: bool  # the month's plan holds money on this bill's line


@dataclass(frozen=True)
class CalendarMonth:
    year: int
    month: int
    position: str  # past | current | future
    today: date
    plan_generated: bool
    days: List[CalendarDay]
    lines: List[CalendarLine]
    bills: List[CalendarBill]
    forecast: Optional[ForecastResult]
    stated_income: Optional[Decimal]
    other_currencies: Tuple[str, ...]

    def _sum(self, group: Optional[str], attr: str) -> Decimal:
        return sum(
            (
                getattr(line, attr)
                for line in self.lines
                if group is None or line.group == group
            ),
            ZERO,
        )

    @property
    def total_planned(self) -> Decimal:
        return self._sum(None, "planned")

    @property
    def total_spent(self) -> Decimal:
        return self._sum(None, "spent")

    @property
    def commitments_planned(self) -> Decimal:
        return self._sum(GROUP_COMMITMENT, "planned")

    @property
    def set_aside_planned(self) -> Decimal:
        return self._sum(GROUP_SET_ASIDE, "planned")

    @property
    def everyday_planned(self) -> Decimal:
        return self._sum(GROUP_EVERYDAY, "planned")

    @property
    def commitments_spent(self) -> Decimal:
        return self._sum(GROUP_COMMITMENT, "spent")

    @property
    def everyday_spent(self) -> Decimal:
        return self._sum(GROUP_EVERYDAY, "spent")

    @property
    def commitments_unrecorded(self) -> Decimal:
        """Money still planned on commitment lines and not yet recorded as
        spent there. It is inside the forecast's left-to-spend figure until
        the bills are recorded (a known limit of the safe daily figure)."""
        return sum(
            (
                max(ZERO, line.remaining)
                for line in self.lines
                if line.group == GROUP_COMMITMENT
            ),
            ZERO,
        )

    @property
    def planned_after_today(self) -> Decimal:
        """The plan on the dates after today (every line except money set
        aside). After MITA's automatic rebalancing it can hold less than what
        is left to spend: rebalancing takes money from later dates to cover a
        day that went over, and money left unspent on a past date stays on
        that date (``realtime_rebalancer.rebalance_after_overspend``)."""
        return sum((d.planned for d in self.days if d.kind == "future"), ZERO)

    @property
    def bills_due_after_today(self) -> Decimal:
        return sum(
            (b.occurrence.amount for b in self.bills if b.occurrence.day > self.today),
            ZERO,
        )


# --- saved payments -> dated occurrences ----------------------------------------


def occurrences_in_month(
    payment: SavedPayment, year: int, month: int
) -> List[BillOccurrence]:
    """The dates a saved payment falls on in one month, from the rule the user
    stated — never before the date it was scheduled for (``anchor``).

    Monthly: the anchor's day of the month, on the month's last day when the
    month is shorter. Weekly: every matching weekday. One-time: the anchor.
    """
    first, last = month_days(year, month)
    if payment.recurrence == MONTHLY:
        if (year, month) < (payment.anchor.year, payment.anchor.month):
            return []
        days = [date(year, month, min(payment.anchor.day, last.day))]
    elif payment.recurrence == WEEKLY:
        offset = (payment.anchor.weekday() - first.weekday()) % 7
        days = [
            first + timedelta(days=offset + 7 * week)
            for week in range(6)
            if first + timedelta(days=offset + 7 * week) <= last
        ]
    else:
        days = [payment.anchor] if first <= payment.anchor <= last else []
    return [
        BillOccurrence(
            day=day,
            category=payment.category,
            amount=payment.amount,
            merchant=payment.merchant,
            recurrence=(
                payment.recurrence if payment.recurrence in (MONTHLY, WEEKLY) else None
            ),
        )
        for day in days
        if day >= payment.anchor
    ]


def counts_in_month(payment: SavedPayment, year: int, month: int) -> bool:
    """Whether a saved payment belongs to the month's commitments — the rule
    the reviewed budget uses for its obligations
    (``budget_draft.obligations_for_month``): a repeating payment counts once
    it is running (its next date before the end of the following month), a
    one-time payment only in its own month. A monthly bill saved after this
    month's date has passed (next date next month) is still this month's."""
    first, last = month_days(year, month)
    if payment.recurrence in (MONTHLY, WEEKLY):
        index = year * 12 + (month - 1) + 2
        horizon = date(index // 12, index % 12 + 1, 1)
        return payment.anchor < horizon
    return first <= payment.anchor <= last


# --- the pure builder -----------------------------------------------------------


def _total(
    entries: Mapping[str, List[Decimal]],
    group_of: Mapping[str, str],
    index: int,
    groups: Tuple[str, ...],
) -> Decimal:
    """One day's planned (index 0) or spent (index 1) over the given groups."""
    return sum(
        (
            values[index]
            for key, values in entries.items()
            if group_of.get(key, GROUP_EVERYDAY) in groups
        ),
        ZERO,
    )


def _day_kind(day: date, today: date) -> str:
    if day < today:
        return "past"
    return "today" if day == today else "future"


def build_calendar(
    *,
    year: int,
    month: int,
    today: date,
    planned: Mapping[Tuple[date, str], Decimal],
    spent: Mapping[Tuple[date, str], Decimal],
    payments: Iterable[SavedPayment] = (),
    plan_generated: bool,
    forecast: Optional[ForecastResult] = None,
    stated_income: Optional[Decimal] = None,
    other_currencies: Sequence[str] = (),
) -> CalendarMonth:
    """The calendar of one month from per-(local day, stored category) plan
    and spend. Pure: no I/O, no clock."""
    first, last = month_days(year, month)
    planned_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    spent_by_cat: Dict[str, Decimal] = defaultdict(lambda: ZERO)
    for (_, category), amount in planned.items():
        planned_by_cat[category] += amount
    for (_, category), amount in spent.items():
        spent_by_cat[category] += amount
    buckets: Set[str] = set(planned_by_cat)

    payments = list(payments)
    occurrences = sorted(
        (
            occurrence
            for payment in payments
            for occurrence in occurrences_in_month(payment, year, month)
        ),
        key=lambda o: (o.day, o.category, -o.amount),
    )

    grouped = group_lines(planned_by_cat, spent_by_cat)
    commitment_keys = {
        key
        for key, _, codes, _, _ in grouped
        if any(is_sacred(c) and not is_set_aside(c) for c in codes)
    } | {
        line_key(payment.category, buckets)
        for payment in payments
        if counts_in_month(payment, year, month)
    }

    lines: List[CalendarLine] = []
    group_of: Dict[str, str] = {}
    for key, name, codes, line_planned, line_spent in grouped:
        if any(is_set_aside(c) for c in codes):
            group = GROUP_SET_ASIDE
        elif key in commitment_keys:
            group = GROUP_COMMITMENT
        else:
            group = GROUP_EVERYDAY
        group_of[key] = group
        lines.append(
            CalendarLine(
                key=key,
                label=name,
                codes=tuple(codes),
                group=group,
                planned=line_planned,
                spent=line_spent,
            )
        )
    lines.sort(key=lambda line: (-line.planned, -line.spent, line.key))

    per_day: Dict[date, Dict[str, List[Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: [ZERO, ZERO])
    )
    for (day, code), amount in planned.items():
        per_day[day][line_key(code, buckets)][0] += amount
    for (day, code), amount in spent.items():
        per_day[day][line_key(code, buckets)][1] += amount

    days: List[CalendarDay] = []
    day = first
    while day <= last:
        entries = per_day.get(day, {})
        days.append(
            CalendarDay(
                day=day,
                kind=_day_kind(day, today),
                planned=_total(
                    entries, group_of, 0, (GROUP_COMMITMENT, GROUP_EVERYDAY)
                ),
                planned_everyday=_total(entries, group_of, 0, (GROUP_EVERYDAY,)),
                set_aside=_total(entries, group_of, 0, (GROUP_SET_ASIDE,)),
                spent=_total(entries, group_of, 1, ALL_GROUPS),
                spent_everyday=_total(entries, group_of, 1, (GROUP_EVERYDAY,)),
                lines=tuple(
                    sorted(
                        (
                            DayLine(line=key, planned=values[0], spent=values[1])
                            for key, values in entries.items()
                            if values[0] != ZERO or values[1] != ZERO
                        ),
                        key=lambda dl: (-max(dl.planned, dl.spent), dl.line),
                    )
                ),
            )
        )
        day += timedelta(days=1)

    planned_lines = {line.key for line in lines if line.planned > ZERO}
    bills = [
        CalendarBill(
            occurrence=o,
            line=line_key(o.category, buckets),
            in_plan=line_key(o.category, buckets) in planned_lines,
        )
        for o in occurrences
    ]
    position = (
        "past"
        if (year, month) < (today.year, today.month)
        else "future" if (year, month) > (today.year, today.month) else "current"
    )
    return CalendarMonth(
        year=year,
        month=month,
        position=position,
        today=today,
        plan_generated=plan_generated,
        days=days,
        lines=lines,
        bills=bills,
        forecast=forecast if plan_generated else None,
        stated_income=stated_income,
        other_currencies=tuple(other_currencies),
    )


# --- from the database ----------------------------------------------------------


def saved_payments(db: Session, ctx: UserContext) -> List[SavedPayment]:
    rows = (
        db.query(
            ScheduledExpense.category,
            ScheduledExpense.amount,
            ScheduledExpense.merchant,
            ScheduledExpense.scheduled_date,
            ScheduledExpense.recurrence,
        )
        .filter(
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
        )
        .order_by(ScheduledExpense.scheduled_date, ScheduledExpense.category)
        .all()
    )
    return [
        SavedPayment(
            category=category,
            amount=Decimal(str(amount)),
            merchant=(merchant or "").strip() or None,
            anchor=anchor,
            recurrence=recurrence,
        )
        for category, amount, merchant, anchor, recurrence in rows
    ]


def calendar_month(
    db: Session, ctx: UserContext, year: int, month: int
) -> CalendarMonth:
    """Five indexed reads inside the caller's READ ONLY transaction; never
    materializes a month (``ensure_month_plan`` writes)."""
    first, last = month_days(year, month)
    generated = month_has_plan(db, ctx.user_id, year, month)
    planned = plan.planned_by_day_and_category(db, ctx, year, month)
    spent = ledger.spend_by_day_and_category(db, ctx, first, last)
    forecast = (
        plan.forecast_from_rows(planned, spent, year, month, ctx.today)
        if generated
        else None
    )
    return build_calendar(
        year=year,
        month=month,
        today=ctx.today,
        planned=planned,
        spent=spent,
        payments=saved_payments(db, ctx),
        plan_generated=generated,
        forecast=forecast,
        stated_income=ctx.stated_monthly_income,
        other_currencies=ledger.other_currencies_in_range(db, ctx, first, last),
    )
