"""The user's local calendar: who they are, what "today" and "this month" mean."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import User
from app.mcp.errors import AuthError, ValidationError
from app.services.core.engine.expense_tracker import local_day_of, local_day_utc_window

MAX_RANGE_DAYS = 366
EARLIEST_SUPPORTED_YEAR = 2000


@dataclass(frozen=True)
class UserContext:
    """The authenticated user as the query layer sees them."""

    user_id: UUID
    timezone: str
    currency: str
    today: date  # the user's local calendar day
    name: Optional[str]
    email: str
    has_onboarded: bool
    stated_monthly_income: Optional[Decimal]
    token_version: int


def load_user_context(
    db: Session, user_id: UUID, *, now: Optional[datetime] = None
) -> UserContext:
    user = db.get(User, user_id)
    if user is None:
        # A valid token for an account that no longer exists.
        raise AuthError("This MITA account is no longer available. Reconnect MITA.")
    tz = user.timezone or "UTC"
    instant = now or datetime.now(timezone.utc)
    income = user.monthly_income
    stated_income = (
        Decimal(str(income))
        if income is not None and Decimal(str(income)) > 0
        else None
    )
    return UserContext(
        user_id=user.id,
        timezone=tz,
        currency=(user.currency or "USD").upper(),
        today=local_day_of(instant, tz),
        name=(user.name or "").strip() or None,
        email=user.email,
        has_onboarded=bool(user.has_onboarded),
        stated_monthly_income=stated_income,
        token_version=int(user.token_version or 1),
    )


def utc_window(start: date, end_inclusive: date, tz: str) -> Tuple[datetime, datetime]:
    """Naive-UTC ``[from, to)`` covering local days ``start..end_inclusive``."""
    lower, _ = local_day_utc_window(start, tz)
    upper, _ = local_day_utc_window(end_inclusive + timedelta(days=1), tz)
    return lower, upper


def resolve_date_range(
    ctx: UserContext,
    start: Optional[date],
    end: Optional[date],
    *,
    default_days: int = 30,
) -> Tuple[date, date]:
    """Inclusive local date range. ``end`` defaults to the user's today and
    ``start`` to ``default_days`` days before ``end``."""
    if end is None:
        end = ctx.today
    if start is None:
        start = end - timedelta(days=default_days - 1)
    if start > end:
        raise ValidationError("start_date must be on or before end_date.")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ValidationError(
            f"The date range can cover at most {MAX_RANGE_DAYS} days."
        )
    if start.year < EARLIEST_SUPPORTED_YEAR:
        raise ValidationError(
            f"Dates before {EARLIEST_SUPPORTED_YEAR} are not supported."
        )
    return start, end


def resolve_month(
    ctx: UserContext, year: Optional[int], month: Optional[int]
) -> Tuple[int, int]:
    """A calendar month; defaults to the user's current local month."""
    if (year is None) != (month is None):
        raise ValidationError(
            "Provide both year and month, or neither for the current month."
        )
    if year is None or month is None:
        return ctx.today.year, ctx.today.month
    if not 1 <= month <= 12:
        raise ValidationError("month must be between 1 and 12.")
    if not EARLIEST_SUPPORTED_YEAR <= year <= ctx.today.year + 1:
        raise ValidationError(
            f"year must be between {EARLIEST_SUPPORTED_YEAR} and {ctx.today.year + 1}."
        )
    return year, month


def month_days(year: int, month: int) -> Tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def month_position(ctx: UserContext, year: int, month: int) -> str:
    """'past' | 'current' | 'future' relative to the user's local today."""
    key = (year, month)
    today_key = (ctx.today.year, ctx.today.month)
    if key < today_key:
        return "past"
    if key > today_key:
        return "future"
    return "current"


def days_elapsed(ctx: UserContext, year: int, month: int) -> int:
    """Days of the month already begun in the user's timezone (today counts)."""
    position = month_position(ctx, year, month)
    if position == "past":
        return month_days(year, month)[1].day
    if position == "future":
        return 0
    return ctx.today.day
