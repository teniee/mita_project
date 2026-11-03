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
* **commitments** — the bills of the forecast's reserve (R3,
  ``budget_forecast_engine.commitment_expectations``): essential lines MITA
  can see paid (``is_bill_line``: rent, mortgage, utilities) plus the lines
  of the recordable categories of the user's saved regular payments that
  belong to the month (``counts_in_month``: the reviewed budget's own rule).
  Other SACRED names — the budget engine's medical-insurance allowance,
  school fees, debt repayment, online courses — are never recorded against,
  so they are everyday lines (still never a rebalancing donor).
* **everyday** — every other line, including spending with no plan behind it.

A day's ``over`` / ``within`` state compares EVERYDAY spending with that
date's everyday plan: rent planned on the 1st and paid on the 3rd is a
commitment paid, not €850 of overspending on the 3rd. A date with no everyday
plan is never "over" (the dashboard rule: no allocation, no verdict).

Saved bills (owner decision 2026-11-02, F-8; docs/chatgpt-app/bill-due-dates.md)
are planned in full on their due dates. Each bill date carries what is
recorded against it — spending recorded under the bill's category this month,
matched to the category's bill dates in date order (``bill_timing.settle``,
the rule the ledger moves the bill's money by) — and its state relative to
the user's today: ``recorded``, ``overdue`` (past and not recorded),
``due_today``, ``upcoming`` (within ``REMINDER_DAYS``) or ``later``. MITA's
data has no link between an expense and a saved payment, so "recorded" means
recorded under the bill's category, never proof that a particular bill was
paid.

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

from app.core.category_priority import is_set_aside
from app.db.models import ScheduledExpense
from app.mcp.categories import group_lines, line_key, line_source
from app.mcp.queries import budget_lines, ledger, plan
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.bill_timing import settle
from app.services.core.engine.budget_forecast_engine import ForecastResult
from app.services.monthly_obligations import due_dates_in_month, due_in_month
from app.services.monthly_plan_service import month_has_plan

ZERO = Decimal("0.00")

GROUP_SET_ASIDE = "set_aside"
GROUP_COMMITMENT = "commitment"
GROUP_EVERYDAY = "everyday"
ALL_GROUPS = (GROUP_SET_ASIDE, GROUP_COMMITMENT, GROUP_EVERYDAY)

# ScheduledExpenseIn: recurrence in {"once", "weekly", "monthly"} or null.
MONTHLY = "monthly"
WEEKLY = "weekly"

# A bill is announced this many calendar days before its due date (owner
# decision 2026-11-02). A reminder window, never an allocation: the bill's
# money stays on its due date.
REMINDER_DAYS = 5

BILL_RECORDED = "recorded"
BILL_OVERDUE = "overdue"
BILL_DUE_TODAY = "due_today"
BILL_UPCOMING = "upcoming"
BILL_LATER = "later"
REMINDER_STATES = (BILL_OVERDUE, BILL_DUE_TODAY, BILL_UPCOMING)


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
    source: Optional[str] = None  # categories.line_source
    # a user line's stored MITA lines it takes the place of (mcp_budget_lines)
    replaces: Tuple[str, ...] = ()

    @property
    def remaining(self) -> Decimal:
        return self.planned - self.spent


@dataclass(frozen=True)
class CalendarBill:
    occurrence: BillOccurrence
    line: str
    in_plan: bool  # the month's plan holds money on this bill's line
    # Spending recorded under the bill's category this month and matched to
    # this date (category and date order, ``bill_timing.settle``).
    recorded: Decimal = ZERO
    recorded_on: Tuple[date, ...] = ()
    state: str = BILL_LATER
    days_until: int = 0

    @property
    def reminder_from(self) -> date:
        return self.occurrence.day - timedelta(days=REMINDER_DAYS)


def bill_state(day: date, amount: Decimal, recorded: Decimal, today: date) -> str:
    """recorded | overdue | due_today | upcoming | later, relative to today.
    Recorded in full ends the reminders; a part recorded does not."""
    if amount > ZERO and recorded >= amount:
        return BILL_RECORDED
    if day < today:
        return BILL_OVERDUE
    if day == today:
        return BILL_DUE_TODAY
    if (day - today).days <= REMINDER_DAYS:
        return BILL_UPCOMING
    return BILL_LATER


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
    # bills to remind of from today: due within REMINDER_DAYS (this month or
    # the first days of the next), due today, or past due and not recorded
    reminders: Tuple[CalendarBill, ...] = ()

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
    stated (``monthly_obligations.due_dates_in_month``, the dates the plan
    holds its money on) — never before the date it was scheduled for
    (``anchor``).

    Monthly: the anchor's day of the month, on the month's last day when the
    month is shorter. Weekly: every matching weekday. One-time: the anchor.
    """
    days = due_dates_in_month(payment.anchor, payment.recurrence, year, month)
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
    return (
        due_in_month(payment.amount, payment.anchor, payment.recurrence, year, month)
        > ZERO
    )


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


def _settled_bills(
    occurrences: Sequence[BillOccurrence],
    spent: Mapping[Tuple[date, str], Decimal],
    buckets: Set[str],
    planned_lines: Set[str],
    today: date,
) -> List[CalendarBill]:
    """Each bill date with what is recorded against it: per category, the
    month's recorded spending matched to the category's bill dates in date
    order (the ledger's rule, ``bill_timing.settle``)."""
    by_category: Dict[str, List[int]] = defaultdict(list)
    for index, occurrence in enumerate(occurrences):
        by_category[occurrence.category].append(index)
    recorded: Dict[int, Tuple[Decimal, Tuple[date, ...]]] = {}
    for category, indexes in by_category.items():
        settlement = settle(
            [(occurrences[i].day, occurrences[i].amount) for i in indexes],
            [
                (day, amount)
                for (day, code), amount in spent.items()
                if code == category
            ],
        )
        for position, index in enumerate(indexes):
            recorded[index] = (
                settlement.covered[position],
                tuple(day for day, _ in settlement.paid[position]),
            )
    bills = []
    for index, o in enumerate(occurrences):
        amount, dates = recorded.get(index, (ZERO, ()))
        line = line_key(o.category, buckets)
        bills.append(
            CalendarBill(
                occurrence=o,
                line=line,
                in_plan=line in planned_lines,
                recorded=amount,
                recorded_on=dates,
                state=bill_state(o.day, o.amount, amount, today),
                days_until=(o.day - today).days,
            )
        )
    return bills


def _next_month(year: int, month: int) -> Tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _reminders(
    bills: Sequence[CalendarBill],
    payments: Sequence[SavedPayment],
    year: int,
    month: int,
    today: date,
    buckets: Set[str],
    planned_lines: Set[str],
) -> Tuple[CalendarBill, ...]:
    """The bills to remind of from today: this month's bills due within
    REMINDER_DAYS, due today or past due and not recorded (the current month
    only), and the next month's bills due within REMINDER_DAYS of today. A
    next-month bill's recordings belong to that month, so it carries none."""
    current = (year, month) == (today.year, today.month)
    found = [
        bill
        for bill in bills
        if bill.state in (BILL_DUE_TODAY, BILL_UPCOMING)
        or (bill.state == BILL_OVERDUE and current)
    ]
    following = _next_month(year, month)
    horizon = today + timedelta(days=REMINDER_DAYS)
    for payment in payments:
        for o in occurrences_in_month(payment, *following):
            if today <= o.day <= horizon:
                line = line_key(o.category, buckets)
                found.append(
                    CalendarBill(
                        occurrence=o,
                        line=line,
                        in_plan=line in planned_lines,
                        state=bill_state(o.day, o.amount, ZERO, today),
                        days_until=(o.day - today).days,
                    )
                )
    found.sort(
        key=lambda b: (b.occurrence.day, b.occurrence.category, -b.occurrence.amount)
    )
    return tuple(found)


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
    replaces: Optional[Mapping[str, Sequence[str]]] = None,
) -> CalendarMonth:
    """The calendar of one month from per-(local day, stored category) plan
    and spend. Pure: no I/O, no clock. ``replaces``: the user's own lines and
    the MITA lines each takes the place of, as stored."""
    replaces = replaces or {}
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
    # The forecast's bills (``commitment_expectations``): essential lines MITA
    # can see paid, and the saved payments that belong to the month — the
    # rule ``get_budget_status.today`` uses too (``plan.bill_line_keys``).
    commitment_keys = plan.bill_line_keys(
        [code for _, _, codes, _, _ in grouped for code in codes],
        buckets,
        [p.category for p in payments if counts_in_month(p, year, month)],
    )

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
                source=line_source(codes, line_planned),
                replaces=tuple(replaces.get(key, ())),
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
    bills = _settled_bills(occurrences, spent, buckets, planned_lines, today)
    reminders = _reminders(bills, payments, year, month, today, buckets, planned_lines)
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
        reminders=reminders,
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
    """Indexed reads inside the caller's READ ONLY transaction (plan, ledger,
    base plan and saved payments for the bills' reserve); never materializes a
    month (``ensure_month_plan`` writes)."""
    first, last = month_days(year, month)
    generated = month_has_plan(db, ctx.user_id, year, month)
    planned = plan.planned_by_day_and_category(db, ctx, year, month)
    spent = ledger.spend_by_day_and_category(db, ctx, first, last)
    forecast = (
        plan.forecast_from_rows(
            planned,
            spent,
            year,
            month,
            ctx.today,
            plan.month_commitments(db, ctx, year, month, planned),
        )
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
        replaces=budget_lines.stored_lines(db, ctx),
    )
