"""When a budget line's money is meant to be spent: purchase dates or an envelope.

The owner's model (docs/chatgpt-app/behavioral-budget.md, 2026-11-03): a
monthly budget is laid out by HOW the user spends it, not divided by the days
of the month.

* **Planned purchases** — groceries every Wednesday, a big shop twice a month,
  a haircut on the 20th. The line's monthly amount is split exactly over the
  real purchase dates of that month: €200 every Wednesday in November 2026 is
  €50 on 4, 11, 18 and 25 Nov; every Monday it is five purchases of €40. A
  planned purchase is an allocation, never a transaction.
* **Flexible spending** — coffee and walks, cigarettes, small things: an
  envelope with no purchase dates. Its money is laid evenly over every day of
  the month only so that each date carries its share; MITA shows it as
  guidance ("about €3 a day left"), never as a purchase on any date.
* A line with **no stated pattern** is flexible: MITA never invents purchase
  dates and presents them as facts.

Pure and deterministic: integer cents (``split_amount_exactly``), real
calendar dates (four- and five-occurrence months, February, leap years,
month ends), no clock, no randomness.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from app.services.core.engine.calendar_engine import split_amount_exactly

ZERO = Decimal("0.00")

KIND_PLANNED = "planned"
KIND_FLEXIBLE = "flexible"
KIND_NOT_APPLICABLE = "not_applicable"
PATTERN_KINDS = (KIND_PLANNED, KIND_FLEXIBLE, KIND_NOT_APPLICABLE)

# What a laid-out month's line is (stamped on its plan rows).
LINE_OBLIGATION = "obligation"
LINE_PLANNED = KIND_PLANNED
LINE_FLEXIBLE = KIND_FLEXIBLE
LINE_SET_ASIDE = "set_aside"
LINE_KINDS = (LINE_OBLIGATION, LINE_PLANNED, LINE_FLEXIBLE, LINE_SET_ASIDE)
# Lines whose own money follows their spending within the month (R2).
SELF_SETTLING = (LINE_PLANNED, LINE_FLEXIBLE)

# Stamped in every plan row's ``plan_json`` of a month laid out by how its
# money is spent, so the ledger, the rollover and the calendar know a
# planned purchase from a flexible budget's daily share or a bill. A month
# without it is a legacy layout (CATEGORY_BEHAVIOR), kept as it is until the
# user saves it again.
LINE_KIND_KEY = "_mita_line_kind_v1"

DAILY = "daily"
WEEKDAYS = "weekdays"  # several days of every week (Mon–Fri lunches)
WEEKLY = "weekly"  # one day of every week
BIWEEKLY = "biweekly"
TIMES_PER_MONTH = "times_per_month"
MONTHLY = "monthly"
DATES = "dates"
FREQUENCIES = (DAILY, WEEKDAYS, WEEKLY, BIWEEKLY, TIMES_PER_MONTH, MONTHLY, DATES)

WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def line_kinds_of(rows) -> Dict[str, str]:
    """``{line: kind}`` stamped on a month's plan rows (any objects with
    ``category`` and ``plan_json``); empty for a legacy layout."""
    kinds: Dict[str, str] = {}
    for row in rows:
        metadata = row.plan_json if isinstance(row.plan_json, dict) else {}
        kind = metadata.get(LINE_KIND_KEY)
        if kind in LINE_KINDS and row.category:
            kinds[row.category] = kind
    return kinds


class PatternError(ValueError):
    """A pattern that does not say when the purchases happen."""


@dataclass(frozen=True)
class SpendingPattern:
    """How the user buys what one line is for, as they stated it."""

    kind: str
    frequency: Optional[str] = None
    weekdays: Tuple[int, ...] = ()  # 0 = Monday … 6 = Sunday
    days_of_month: Tuple[int, ...] = ()  # 1 … 31 (31 = the month's last day)
    times_per_month: Optional[int] = None
    anchor_date: Optional[date] = None  # every two weeks: one purchase date
    typical_amount: Optional[Decimal] = None

    def validated(self) -> "SpendingPattern":
        """The same pattern, normalized; raises ``PatternError``."""
        if self.kind not in PATTERN_KINDS:
            raise PatternError(f"kind must be one of {', '.join(PATTERN_KINDS)}.")
        weekdays = tuple(sorted(set(self.weekdays)))
        days = tuple(sorted(set(self.days_of_month)))
        if any(not 0 <= d <= 6 for d in weekdays):
            raise PatternError("weekdays are 0 (Monday) to 6 (Sunday).")
        if any(not 1 <= d <= 31 for d in days):
            raise PatternError("days of the month are 1 to 31.")
        if self.typical_amount is not None and self.typical_amount <= ZERO:
            raise PatternError("a typical purchase amount must be above 0.")
        if self.kind != KIND_PLANNED:
            if self.frequency or weekdays or days or self.times_per_month:
                raise PatternError(
                    "only planned purchases have a frequency, weekdays or dates; "
                    "a flexible budget has no purchase dates."
                )
            return SpendingPattern(self.kind, typical_amount=self.typical_amount)
        frequency = self.frequency
        if frequency not in FREQUENCIES:
            raise PatternError(
                "planned purchases need a frequency: " + ", ".join(FREQUENCIES) + "."
            )
        times = self.times_per_month
        anchor = self.anchor_date
        if frequency == DAILY:
            weekdays, days, times, anchor = (), (), None, None
        elif frequency in (WEEKDAYS, WEEKLY):
            if not weekdays:
                raise PatternError("say which day(s) of the week the purchase happens.")
            if frequency == WEEKLY and len(weekdays) != 1:
                frequency = WEEKDAYS  # "every Monday and Thursday"
            days, times, anchor = (), None, None
        elif frequency == BIWEEKLY:
            if anchor is None:
                raise PatternError(
                    "every two weeks needs one of the purchase dates (the next one)."
                )
            weekdays, days, times = (anchor.weekday(),), (), None
        elif frequency == TIMES_PER_MONTH:
            if not times or not 1 <= times <= 31:
                raise PatternError("say how many times a month (1 to 31).")
            days, anchor = (), None
        elif frequency in (MONTHLY, DATES):
            if not days:
                raise PatternError("say which day(s) of the month.")
            if frequency == MONTHLY and len(days) != 1:
                frequency = DATES
            weekdays, times, anchor = (), None, None
        return SpendingPattern(
            KIND_PLANNED,
            frequency,
            weekdays,
            days,
            times,
            anchor,
            self.typical_amount,
        )


def _month_days(year: int, month: int) -> List[date]:
    last = calendar.monthrange(year, month)[1]
    return [date(year, month, day) for day in range(1, last + 1)]


def _spaced(candidates: Sequence[date], count: int) -> List[date]:
    """``count`` dates spread evenly over ``candidates`` (centered, so twice a
    month over November is the 8th and the 23rd, not the 1st and the 16th)."""
    if count >= len(candidates):
        return list(candidates)
    size = len(candidates)
    return [candidates[((2 * i + 1) * size) // (2 * count)] for i in range(count)]


def purchase_dates(pattern: SpendingPattern, year: int, month: int) -> List[date]:
    """The real dates of ``(year, month)`` the planned purchases fall on, in
    order. Empty for a flexible pattern."""
    pattern = pattern.validated()
    if pattern.kind != KIND_PLANNED:
        return []
    days = _month_days(year, month)
    frequency = pattern.frequency
    if frequency == DAILY:
        return days
    if frequency in (WEEKDAYS, WEEKLY):
        return [d for d in days if d.weekday() in pattern.weekdays]
    if frequency == BIWEEKLY:
        anchor = pattern.anchor_date
        return [d for d in days if (d - anchor).days % 14 == 0]
    if frequency == TIMES_PER_MONTH:
        candidates = (
            [d for d in days if d.weekday() in pattern.weekdays]
            if pattern.weekdays
            else days
        )
        return _spaced(candidates, pattern.times_per_month)
    # monthly / dates: the day of the month, the month's last day when shorter
    last = days[-1].day
    return sorted({date(year, month, min(day, last)) for day in pattern.days_of_month})


def dates_are_stated(pattern: SpendingPattern) -> bool:
    """True when the user named the dates or weekdays; False when MITA spaced
    a number of purchases over the month (``times_per_month`` without days)."""
    pattern = pattern.validated()
    return not (pattern.frequency == TIMES_PER_MONTH and not pattern.weekdays)


@dataclass(frozen=True)
class LineLayout:
    """One line of a month: what it is and its money by date."""

    kind: str  # LINE_KINDS
    by_date: Dict[date, Decimal] = field(default_factory=dict)


def lay_out_line(
    total: Decimal,
    pattern: Optional[SpendingPattern],
    year: int,
    month: int,
) -> LineLayout:
    """A spending line's money over the month, to the cent: split over its
    planned purchase dates, or evenly over every day (flexible, the default
    without a stated pattern). ``not_applicable`` lines never reach here —
    they are left out of the plan."""
    total = Decimal(total)
    if pattern is not None:
        pattern = pattern.validated()
    if pattern is not None and pattern.kind == KIND_PLANNED:
        dates = purchase_dates(pattern, year, month)
        kind = LINE_PLANNED
    else:
        dates = _month_days(year, month)
        kind = LINE_FLEXIBLE
    shares = split_amount_exactly(total, len(dates))
    return LineLayout(kind, {d: s for d, s in zip(dates, shares) if s != ZERO})


def describe(pattern: Optional[SpendingPattern]) -> str:
    """Plain words for a pattern ("every Wednesday", "flexible")."""
    if pattern is None:
        return "flexible (no purchase dates)"
    pattern = pattern.validated()
    if pattern.kind == KIND_FLEXIBLE:
        return "flexible (no purchase dates)"
    if pattern.kind == KIND_NOT_APPLICABLE:
        return "does not apply"
    names = [WEEKDAY_NAMES[d].capitalize() for d in pattern.weekdays]
    f = pattern.frequency
    if f == DAILY:
        return "every day"
    if f == WEEKLY:
        return f"every {names[0]}"
    if f == WEEKDAYS:
        return "every " + ", ".join(names)
    if f == BIWEEKLY:
        return f"every other {names[0]} (from {pattern.anchor_date.isoformat()})"
    if f == TIMES_PER_MONTH:
        times = f"{pattern.times_per_month} times a month"
        return times + (" on " + "/".join(names) if names else "")
    ordinal = ", ".join(str(d) for d in pattern.days_of_month)
    return (
        f"on day {ordinal} of each month"
        if f == MONTHLY
        else f"on days {ordinal} of each month"
    )


def next_dates(pattern: SpendingPattern, start: date, months: int = 2) -> List[date]:
    """Purchase dates from ``start`` on, over this month and the next ones."""
    found: List[date] = []
    year, month = start.year, start.month
    for _ in range(months):
        found.extend(d for d in purchase_dates(pattern, year, month) if d >= start)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return found


def week_of(day: date) -> Tuple[date, date]:
    """Monday–Sunday week holding ``day``."""
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)
