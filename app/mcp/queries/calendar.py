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
are planned in full on their due dates. Each bill date carries what is paid
on it — ONLY the expenses the user linked to that due date
(``obligation_payments``; docs/chatgpt-app/behavioral-budget.md): a purchase
in the bill's category never pays it — and its state relative to the user's
today: ``paid``, ``overdue`` (past and not paid in MITA), ``due_today``,
``upcoming`` (within ``REMINDER_DAYS``) or ``later``. "Paid" means the user
told MITA which expense paid it; MITA has no bank connection to confirm it.

The pure ``build_calendar`` takes plain inputs so the sign-in page's
fictional example runs through exactly this code (tests_mcp/test_auth_ui.py).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.category_priority import is_set_aside
from app.db.models import ScheduledExpense
from app.mcp.categories import group_lines, line_key, line_source
from app.mcp.queries import budget_lines, ledger, obligations, plan
from app.mcp.queries.periods import UserContext, month_days
from app.services.core.engine.budget_forecast_engine import (
    RISK_PACE_RATIO,
    ForecastResult,
    is_bill_line,
    is_recordable,
)
from app.services.core.engine.spending_schedule import (
    dates_are_stated,
    describe,
    purchase_dates,
)
from app.services.monthly_obligations import due_dates_in_month, due_in_month
from app.services.obligation_lines import bill_key, month_is_keyed
from app.services.spending_patterns import stored_patterns

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

BILL_PAID = "paid"
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
    obligation_id: Optional[UUID] = None  # scheduled_expenses.id


@dataclass(frozen=True)
class BillOccurrence:
    day: date
    category: str
    amount: Decimal
    merchant: Optional[str]
    recurrence: Optional[str]  # "monthly" | "weekly" | None (one-time)
    obligation_id: Optional[UUID] = None


@dataclass(frozen=True)
class DayLine:
    line: str
    planned: Decimal
    spent: Decimal


@dataclass(frozen=True)
class Purchase:
    """One planned purchase of a planned line: its date, the money the
    reviewed plan put on it and what was spent on the line that date."""

    line: str
    day: date
    planned: Decimal
    spent: Decimal
    proposed: bool = False  # a date MITA proposed, not one the user named


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
    # The flexible budgets' share of ``planned`` on this date (guidance, never
    # a purchase); the rest is planned purchases, bills and legacy lines.
    planned_flexible: Decimal = ZERO
    purchases: Tuple[Purchase, ...] = ()

    @property
    def planned_scheduled(self) -> Decimal:
        return self.planned - self.planned_flexible

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
    # obligation | planned | flexible | set_aside, or legacy for a month laid
    # out before spending patterns existed (and spending with no plan)
    spending_type: str = "legacy"
    pattern: Optional[str] = None
    purchases: Tuple[Purchase, ...] = ()
    next_purchase: Optional[Purchase] = None  # the first from today on
    days_left: int = 0  # today and the days after it, for a month not ended
    # True when the user named the purchase days; False when MITA proposed
    # them (about once a week / N times a month with no day named).
    purchase_dates_stated: Optional[bool] = None
    # The forecast engine's pace for this line (get_budget_forecast's own
    # per-category figures): spent per day so far, the plan per day of the
    # month, and spent pace ÷ planned pace.
    pace_per_day: Optional[Decimal] = None
    planned_per_day: Optional[Decimal] = None
    pace_ratio: Optional[Decimal] = None
    days_until_exhausted: Optional[int] = None

    @property
    def remaining(self) -> Decimal:
        return self.planned - self.spent

    def guidance(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """For a flexible line of a month not ended: what is left of it per
        day (today included) and per week — arithmetic, never a forecast."""
        if self.spending_type != "flexible" or self.days_left <= 0:
            return None, None
        left = max(ZERO, self.remaining)
        per_day = (left / self.days_left).quantize(Decimal("0.01"), ROUND_HALF_UP)
        per_week = (
            (left * 7 / self.days_left).quantize(Decimal("0.01"), ROUND_HALF_UP)
            if self.days_left >= 7
            else left
        )
        return per_day, per_week

    @property
    def pace_status(self) -> Optional[str]:
        """For a flexible line: not_started | on_pace | faster_than_pace
        (spending at least RISK_PACE_RATIO × its planned pace — the
        forecast's "at risk" rule) | over_limit (beyond the month's amount).
        Guidance, not a verdict on any date."""
        if self.spending_type != "flexible" or self.planned <= ZERO:
            return None
        if self.spent > self.planned:
            return PACE_OVER_LIMIT
        if self.spent <= ZERO:
            return PACE_NOT_STARTED
        if self.pace_ratio is not None and self.pace_ratio >= RISK_PACE_RATIO:
            return PACE_FAST
        return PACE_ON


PACE_NOT_STARTED = "not_started"
PACE_ON = "on_pace"
PACE_FAST = "faster_than_pace"
PACE_OVER_LIMIT = "over_limit"


@dataclass(frozen=True)
class CalendarBill:
    occurrence: BillOccurrence
    line: str
    in_plan: bool  # the month's plan holds money on this bill's line
    # The expenses the user linked to this due date (obligation_payments),
    # whenever they were recorded.
    paid: Decimal = ZERO
    paid_on: Tuple[date, ...] = ()
    state: str = BILL_LATER
    days_until: int = 0

    @property
    def reminder_from(self) -> date:
        return self.occurrence.day - timedelta(days=REMINDER_DAYS)

    @property
    def outstanding(self) -> Decimal:
        return max(ZERO, self.occurrence.amount - self.paid)


def bill_state(day: date, amount: Decimal, paid: Decimal, today: date) -> str:
    """paid | overdue | due_today | upcoming | later, relative to today.
    Paid in full ends the reminders; a part paid does not."""
    if amount > ZERO and paid >= amount:
        return BILL_PAID
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
    def flexible_lines(self) -> List[CalendarLine]:
        return [line for line in self.lines if line.spending_type == "flexible"]

    @property
    def flexible_left(self) -> Decimal:
        """What the flexible budgets still hold for the month (never below 0
        per line: an overspent line holds nothing)."""
        return sum((max(ZERO, line.remaining) for line in self.flexible_lines), ZERO)

    @property
    def flexible_per_day(self) -> Optional[Decimal]:
        """The flexible budgets' guidance for each day left, today included:
        the sum of each line's left per day — never more than the month's
        safe average a day (the forecast's safe_daily_limit, never below 0).
        Envelopes can still hold money that is no longer safe to spend (an
        overspend nothing could cover, a bill paid without its link); then
        the safe average is the guide. Guidance, not cash on hand."""
        days = [line.guidance()[0] for line in self.flexible_lines]
        known = [d for d in days if d is not None]
        if not known:
            return None
        guide = sum(known, ZERO)
        if self.forecast is not None and self.position != "past":
            guide = min(guide, max(ZERO, self.forecast.safe_daily_limit))
        return guide

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
            obligation_id=payment.obligation_id,
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


def _bill_line(o: BillOccurrence, buckets: Set[str], keyed: bool) -> str:
    """The plan line a bill's money is on: its own in a keyed month, its
    category's (shown with its paired bucket) in a legacy one."""
    if keyed and o.obligation_id is not None:
        return bill_key(o.obligation_id)
    return line_key(o.category, buckets)


def _settled_bills(
    occurrences: Sequence[BillOccurrence],
    payments: Mapping[Tuple[UUID, date], Sequence[Tuple[date, Decimal]]],
    buckets: Set[str],
    planned_lines: Set[str],
    today: date,
    keyed: bool,
) -> List[CalendarBill]:
    """Each bill date with what the user linked to it as paid
    (``obligation_payments``); nothing else counts."""
    bills = []
    for o in occurrences:
        linked = list(payments.get((o.obligation_id, o.day), ()))
        paid = sum((amount for _, amount in linked), ZERO)
        line = _bill_line(o, buckets, keyed)
        bills.append(
            CalendarBill(
                occurrence=o,
                line=line,
                in_plan=line in planned_lines,
                paid=paid,
                paid_on=tuple(sorted({day for day, _ in linked})),
                state=bill_state(o.day, o.amount, paid, today),
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
    next_month_paid: Optional[
        Mapping[Tuple[UUID, date], Sequence[Tuple[date, Decimal]]]
    ] = None,
) -> Tuple[CalendarBill, ...]:
    """The bills to remind of from today: this month's bills due within
    REMINDER_DAYS, due today or past due and not paid (the current month
    only), and the next month's bills due within REMINDER_DAYS of today —
    with what the user already linked to them (``next_month_paid``)."""
    current = (year, month) == (today.year, today.month)
    found = [
        bill
        for bill in bills
        if bill.state in (BILL_DUE_TODAY, BILL_UPCOMING)
        or (bill.state == BILL_OVERDUE and current)
    ]
    following = _next_month(year, month)
    horizon = today + timedelta(days=REMINDER_DAYS)
    next_month_paid = next_month_paid or {}
    for payment in payments:
        for o in occurrences_in_month(payment, *following):
            if today <= o.day <= horizon:
                linked = list(next_month_paid.get((o.obligation_id, o.day), ()))
                paid = sum((amount for _, amount in linked), ZERO)
                if o.amount > ZERO and paid >= o.amount:
                    continue  # already paid early: nothing to remind of
                line = line_key(o.category, buckets)
                found.append(
                    CalendarBill(
                        occurrence=o,
                        line=line,
                        in_plan=line in planned_lines,
                        paid=paid,
                        paid_on=tuple(sorted({day for day, _ in linked})),
                        state=bill_state(o.day, o.amount, paid, today),
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
    paid: Optional[Mapping[Tuple[UUID, date], Sequence[Tuple[date, Decimal]]]] = None,
    next_month_paid: Optional[
        Mapping[Tuple[UUID, date], Sequence[Tuple[date, Decimal]]]
    ] = None,
    commitment_lines: Optional[Iterable[str]] = None,
    names: Optional[Mapping[str, str]] = None,
    kinds: Optional[Mapping[str, str]] = None,
    base: Optional[Mapping[Tuple[date, str], Decimal]] = None,
    patterns: Optional[Mapping[str, str]] = None,
    stated_dates: Optional[Mapping[str, bool]] = None,
) -> CalendarMonth:
    """The calendar of one month from per-(local day, plan line) plan and
    spend. Pure: no I/O, no clock. ``replaces``: the user's own lines and
    the MITA lines each takes the place of, as stored. ``paid``: per (saved
    payment, due date) the ``(recorded day, amount)`` of the expenses the
    user linked to it. ``commitment_lines``: the month's commitments
    (``obligation_lines.month_commitments``); without them (the sign-in
    page's fictional month) they are derived from the plan and the saved
    payments' categories, as before obligations had lines of their own.
    ``names``: the user's names for their saved payments' lines. ``kinds``:
    each line's kind as the month's rows say (``spending_schedule``); ``base``:
    the month's reviewed plan per (date, line) — a planned line's purchases;
    ``patterns``: each planned line's pattern in words."""
    replaces = replaces or {}
    paid = paid or {}
    kinds = kinds or {}
    base = base or {}
    patterns = patterns or {}
    stated_dates = stated_dates or {}
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

    keyed = month_is_keyed(buckets)
    grouped = group_lines(planned_by_cat, spent_by_cat, names)
    # The forecast's bills: the month's commitments — the rule
    # ``get_budget_status.today`` uses too (``plan.bill_line_keys``).
    codes_in_month = [code for _, _, codes, _, _ in grouped for code in codes]
    if commitment_lines is None:
        commitment_lines = [c for c in codes_in_month if is_bill_line(c)] + [
            p.category
            for p in payments
            if counts_in_month(p, year, month) and is_recordable(p.category)
        ]
    commitment_keys = plan.bill_line_keys(codes_in_month, buckets, commitment_lines)

    # A planned line's purchases: the reviewed plan's dates and amounts,
    # with what was spent on the line each date.
    spent_on: Dict[Tuple[date, str], Decimal] = defaultdict(lambda: ZERO)
    for (day, code), amount in spent.items():
        spent_on[(day, line_key(code, buckets))] += amount
    purchases_of: Dict[str, List[Purchase]] = defaultdict(list)
    for (day, code), amount in sorted(base.items()):
        if kinds.get(code) == "planned" and amount > ZERO:
            key = line_key(code, buckets)
            purchases_of[key].append(
                Purchase(
                    key,
                    day,
                    amount,
                    spent_on[(day, key)],
                    proposed=stated_dates.get(key) is False,
                )
            )
    month_open = (year, month) >= (today.year, today.month)
    days_left = 0 if not month_open else (last - max(today, first)).days + 1

    pace = (
        {c.category: c for c in forecast.all_categories}
        if forecast is not None and plan_generated
        else {}
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
        kind = next((kinds[c] for c in codes if c in kinds), "legacy")
        purchases = tuple(purchases_of.get(key, ()))
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
                spending_type=kind,
                pattern=patterns.get(key),
                purchases=purchases,
                # the first still ahead: a purchase made today is not upcoming
                next_purchase=next(
                    (
                        p
                        for p in purchases
                        if p.day > today or (p.day == today and p.spent <= ZERO)
                    ),
                    None,
                ),
                days_left=days_left,
                purchase_dates_stated=stated_dates.get(key),
                pace_per_day=pace[key].daily_pace if key in pace else None,
                planned_per_day=pace[key].planned_per_day if key in pace else None,
                pace_ratio=pace[key].overspend_ratio if key in pace else None,
                days_until_exhausted=(
                    pace[key].days_until_exhausted if key in pace else None
                ),
            )
        )
    lines.sort(key=lambda line: (-line.planned, -line.spent, line.key))
    flexible_lines = {line.key for line in lines if line.spending_type == "flexible"}
    purchases_by_day: Dict[date, List[Purchase]] = defaultdict(list)
    for line in lines:
        for p in line.purchases:
            purchases_by_day[p.day].append(p)

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
                planned_flexible=sum(
                    (v[0] for k, v in entries.items() if k in flexible_lines), ZERO
                ),
                purchases=tuple(purchases_by_day.get(day, ())),
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
    bills = _settled_bills(occurrences, paid, buckets, planned_lines, today, keyed)
    reminders = _reminders(
        bills,
        payments,
        year,
        month,
        today,
        buckets,
        planned_lines,
        next_month_paid,
    )
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
            ScheduledExpense.id,
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
        .order_by(
            ScheduledExpense.scheduled_date,
            ScheduledExpense.category,
            ScheduledExpense.id,
        )
        .all()
    )
    return [
        SavedPayment(
            category=category,
            amount=Decimal(str(amount)),
            merchant=(merchant or "").strip() or None,
            anchor=anchor,
            recurrence=recurrence,
            obligation_id=obligation_id,
        )
        for obligation_id, category, amount, merchant, anchor, recurrence in rows
    ]


def _as_pairs(found) -> Dict[Tuple[UUID, date], List[Tuple[date, Decimal]]]:
    return {
        key: [(p.day, p.amount) for p in payments] for key, payments in found.items()
    }


def calendar_month(
    db: Session, ctx: UserContext, year: int, month: int
) -> CalendarMonth:
    """Indexed reads inside the caller's READ ONLY transaction (plan, ledger,
    base plan and saved payments for the bills' reserve); never materializes a
    month (``ensure_month_plan`` writes)."""
    first, last = month_days(year, month)
    view = plan.month_plan(db, ctx, year, month)  # the month's rows, once
    planned, generated, kinds, base = (
        view.planned,
        view.generated,
        view.kinds,
        view.base,
    )
    spent = plan.month_spent(db, ctx, year, month, view)
    commitments = plan.commitments_from(db, ctx, year, month, view)
    needs, paid_by_line = plan.by_display_line(commitments, planned)
    stated = stored_patterns(db, ctx.user_id) if "planned" in kinds.values() else {}
    # A stored pattern describes a planned line only when it gives this plan's
    # own dates (one changed after the month was saved applies once it is
    # saved again).
    current = {
        line: stated[line]
        for line, kind in kinds.items()
        if kind == "planned"
        and line in stated
        and set(purchase_dates(stated[line], year, month))
        == {d for (d, c), a in base.items() if c == line and a > 0}
    }
    forecast = (
        plan.forecast_from_rows(
            planned, spent, year, month, ctx.today, needs, paid_by_line
        )
        if generated
        else None
    )
    following = (year + 1, 1) if month == 12 else (year, month + 1)
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
        paid=_as_pairs(obligations.payments_by_due(db, ctx, year, month)),
        next_month_paid=_as_pairs(obligations.payments_by_due(db, ctx, *following)),
        commitment_lines=commitments.lines,
        names=obligations.obligation_names(db, ctx),
        kinds=kinds,
        base=base,
        patterns={line: describe(p) for line, p in current.items()},
        stated_dates={line: dates_are_stated(p) for line, p in current.items()},
    )
