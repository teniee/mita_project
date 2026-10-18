"""What MITA already knows about the user, and what is still missing.

``users`` column defaults (USD, UTC, income 0, savings 0) are not answers, so
a field counts as set only when the user stated it: in ChatGPT
(``mcp_user_profiles.*_confirmed_at``) or by completing onboarding in the app,
which asks for income and sets the device timezone (``has_onboarded``).
Nothing here is estimated: an unknown field is reported missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db.models import Goal, ScheduledExpense, Transaction
from app.mcp.queries.periods import UserContext
from app.mcp.queries.recurring import REPEATING
from app.services.core.engine.expense_tracker import _safe_zone
from app.services.monthly_plan_service import month_has_plan

ZERO = Decimal("0.00")

FIELD_INCOME = "monthly_net_income"
FIELD_CURRENCY = "currency"
FIELD_TIMEZONE = "timezone"
FIELD_HOUSEHOLD = "household_size"
FIELD_SAVINGS = "monthly_savings_target"


@dataclass(frozen=True)
class SetupState:
    income_set: bool
    currency_set: bool
    timezone_set: bool
    household_size_set: bool
    savings_preference_set: bool
    monthly_plan_exists: bool
    transaction_count: int
    recurring_expense_count: int
    savings_goal_count: int
    months_of_history: int

    @property
    def profile_complete(self) -> bool:
        """Enough to build a budget: income, currency and timezone."""
        return self.income_set and self.currency_set and self.timezone_set

    @property
    def setup_complete(self) -> bool:
        return self.profile_complete and self.monthly_plan_exists

    @property
    def missing_fields(self) -> List[str]:
        flags = (
            (FIELD_INCOME, self.income_set),
            (FIELD_CURRENCY, self.currency_set),
            (FIELD_TIMEZONE, self.timezone_set),
            (FIELD_HOUSEHOLD, self.household_size_set),
            (FIELD_SAVINGS, self.savings_preference_set),
        )
        return [name for name, present in flags if not present]

    @property
    def suggested_next_step(self) -> str:
        if not self.profile_complete:
            return "complete_profile"
        if not self.monthly_plan_exists:
            # A first budget built before rent or other regular payments are
            # known looks final but is not; ask once (never mandatory).
            if self.recurring_expense_count == 0:
                return "ask_about_obligations"
            return "build_budget"
        if self.transaction_count == 0:
            return "record_expenses"
        return "ready"


def income_set(ctx: UserContext) -> bool:
    return ctx.income_confirmed or (
        ctx.has_onboarded and ctx.stated_monthly_income is not None
    )


def currency_set(ctx: UserContext) -> bool:
    return ctx.currency_confirmed or ctx.has_onboarded


def timezone_set(ctx: UserContext) -> bool:
    return ctx.timezone_confirmed or ctx.has_onboarded


def savings_set(ctx: UserContext) -> bool:
    target = ctx.monthly_savings_target
    return ctx.savings_confirmed or (
        ctx.has_onboarded and target is not None and target > ZERO
    )


def known_monthly_savings(ctx: UserContext) -> Optional[Decimal]:
    return ctx.monthly_savings_target if savings_set(ctx) else None


def setup_state(db: Session, ctx: UserContext) -> SetupState:
    transaction_count = db.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.user_id == ctx.user_id, Transaction.deleted_at.is_(None)
        )
    )
    zone = _safe_zone(ctx.timezone).key
    months = db.scalar(
        select(
            func.count(
                distinct(
                    func.date_trunc("month", func.timezone(zone, Transaction.spent_at))
                )
            )
        ).where(Transaction.user_id == ctx.user_id, Transaction.deleted_at.is_(None))
    )
    recurring = db.scalar(
        select(func.count(ScheduledExpense.id)).where(
            ScheduledExpense.user_id == ctx.user_id,
            ScheduledExpense.deleted_at.is_(None),
            ScheduledExpense.status == "pending",
            ScheduledExpense.recurrence.in_(sorted(REPEATING)),
        )
    )
    goals = db.scalar(
        select(func.count(Goal.id)).where(
            Goal.user_id == ctx.user_id,
            Goal.deleted_at.is_(None),
            Goal.status == "active",
        )
    )
    return SetupState(
        income_set=income_set(ctx),
        currency_set=currency_set(ctx),
        timezone_set=timezone_set(ctx),
        household_size_set=ctx.household_size is not None,
        savings_preference_set=savings_set(ctx),
        monthly_plan_exists=month_has_plan(
            db, ctx.user_id, ctx.today.year, ctx.today.month
        ),
        transaction_count=int(transaction_count or 0),
        recurring_expense_count=int(recurring or 0),
        savings_goal_count=int(goals or 0),
        months_of_history=int(months or 0),
    )
