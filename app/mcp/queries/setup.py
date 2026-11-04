"""What MITA already knows about the user, and what is still missing.

``users`` column defaults (USD, UTC, income 0, savings 0) are not answers, so
a field counts as set only when the user stated it: in ChatGPT
(``mcp_user_profiles.*_confirmed_at``) or by completing onboarding in the app,
which asks for income and sets the device timezone (``has_onboarded``).
Nothing here is estimated: an unknown field is reported missing.

Personalized onboarding (2.8, docs/chatgpt-app/personalization-2.8.md): the
onboarding stage is DERIVED on every call from what is stored — confirmed
profile facts, saved obligations, spending patterns, the user's own lines and
the answers in ``mcp_setup_answers`` — so it survives a reconnection and is
never a second source of truth. A topic nobody answered is ``unknown``, never
"none"; "none" and "skipped" exist only as the user's own answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Goal,
    McpBudgetLine,
    McpSetupAnswer,
    ScheduledExpense,
    SpendingPattern,
    Transaction,
)
from app.mcp.queries.periods import UserContext
from app.mcp.queries.recurring import REPEATING
from app.services.core.engine.expense_tracker import _safe_zone
from app.services.monthly_plan_service import latest_plan_month_before, month_has_plan

ZERO = Decimal("0.00")

FIELD_INCOME = "monthly_net_income"
FIELD_CURRENCY = "currency"
FIELD_TIMEZONE = "timezone"
FIELD_HOUSEHOLD = "household_size"
FIELD_SAVINGS = "monthly_savings_target"

# --- setup topics and the user's answers (mcp_setup_answers, 0043) ---------

TOPIC_REGULAR_PAYMENTS = "regular_payments"
TOPIC_EVERYDAY_SPENDING = "everyday_spending"
TOPIC_IRREGULAR_EXPENSES = "irregular_expenses"
TOPIC_INCOME_SCHEDULE = "income_schedule"
TOPIC_REGION = "region"
TOPIC_PROFILE = "profile"  # derived only (income, currency, timezone)

ANSWER_NONE = "none"
ANSWER_DESCRIBED = "described"
ANSWER_SKIPPED = "skipped"

# What the user may answer for each topic. A fact another table holds (a saved
# payment, a stated income schedule, a confirmed country) is never an answer.
TOPIC_ANSWERS: Dict[str, frozenset] = {
    TOPIC_REGULAR_PAYMENTS: frozenset({ANSWER_NONE, ANSWER_SKIPPED}),
    TOPIC_EVERYDAY_SPENDING: frozenset({ANSWER_DESCRIBED, ANSWER_SKIPPED}),
    TOPIC_IRREGULAR_EXPENSES: frozenset(
        {ANSWER_NONE, ANSWER_DESCRIBED, ANSWER_SKIPPED}
    ),
    TOPIC_INCOME_SCHEDULE: frozenset({ANSWER_SKIPPED}),
    TOPIC_REGION: frozenset({ANSWER_SKIPPED}),
}

# Topic states as reported (get_setup_status.onboarding.topics).
STATE_ANSWERED = "answered"
STATE_NONE = "none"
STATE_DESCRIBED = "described"
STATE_PARTIAL = "partially_known"
STATE_SKIPPED = "skipped"
STATE_UNKNOWN = "unknown"

# A plan is personalized only when the user answered both of these.
PERSONALIZED_REQUIRES = (TOPIC_REGULAR_PAYMENTS, TOPIC_EVERYDAY_SPENDING)
# The order the conversation asks in (the onboarding skill).
QUESTION_ORDER = (
    TOPIC_PROFILE,
    TOPIC_REGION,
    TOPIC_INCOME_SCHEDULE,
    TOPIC_REGULAR_PAYMENTS,
    TOPIC_EVERYDAY_SPENDING,
    TOPIC_IRREGULAR_EXPENSES,
)
OPTIONAL_TOPICS = frozenset(
    {TOPIC_REGION, TOPIC_INCOME_SCHEDULE, TOPIC_IRREGULAR_EXPENSES}
)

STAGE_NOT_STARTED = "not_started"
STAGE_IN_PROGRESS = "in_progress"
STAGE_BASIC_PROFILE = "basic_profile_completed"
STAGE_SPENDING_PARTIAL = "spending_partially_known"
STAGE_PRELIMINARY = "ready_for_preliminary_budget"
STAGE_PERSONALIZED = "ready_for_personalized_budget"
STAGE_SKIPPED = "optional_questions_skipped"
STAGE_ESTABLISHED = "established"

READINESS_NOT_READY = "not_ready"
READINESS_PRELIMINARY = "preliminary"
READINESS_PERSONALIZED = "personalized"


def setup_answers(db: Session, user_id) -> Dict[str, str]:
    """``{topic: answer}`` the user gave (mcp_setup_answers)."""
    rows = db.execute(
        select(McpSetupAnswer.topic, McpSetupAnswer.answer).where(
            McpSetupAnswer.user_id == user_id
        )
    ).all()
    return {topic: answer for topic, answer in rows}


def personalized_spending(answers: Dict[str, str]) -> bool:
    """True when the user said the spending they described is what they
    regularly spend on: MITA's lines they did not mention are then left out
    of a preview (``unknown``), never budgeted by assumption."""
    return answers.get(TOPIC_EVERYDAY_SPENDING) == ANSWER_DESCRIBED


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
    # Spending patterns the user stated (spending_patterns rows).
    spending_patterns_count: int = 0
    # 2.8: the user's answers, their own budget lines, the stated income
    # schedule and country, and whether any month holds a saved plan.
    answers: Dict[str, str] = field(default_factory=dict)
    own_lines_count: int = 0
    income_schedule_stated: bool = False
    country_confirmed: bool = False
    any_plan_saved: bool = False

    @property
    def profile_complete(self) -> bool:
        """Enough to build a budget: income, currency and timezone."""
        return self.income_set and self.currency_set and self.timezone_set

    def topic_state(self, topic: str) -> str:
        answer = self.answers.get(topic)
        if topic == TOPIC_PROFILE:
            if self.profile_complete:
                return STATE_ANSWERED
            return STATE_PARTIAL if self._anything_stated else STATE_UNKNOWN
        if topic == TOPIC_REGULAR_PAYMENTS:
            if self.recurring_expense_count:
                return STATE_ANSWERED  # a saved payment outranks an old "none"
            return {ANSWER_NONE: STATE_NONE, ANSWER_SKIPPED: STATE_SKIPPED}.get(
                answer, STATE_UNKNOWN
            )
        if topic == TOPIC_EVERYDAY_SPENDING:
            if answer == ANSWER_DESCRIBED:
                return STATE_DESCRIBED
            if answer == ANSWER_SKIPPED:
                return STATE_SKIPPED
            if self.spending_patterns_count or self.own_lines_count:
                return STATE_PARTIAL
            return STATE_UNKNOWN
        if topic == TOPIC_IRREGULAR_EXPENSES:
            return {
                ANSWER_NONE: STATE_NONE,
                ANSWER_DESCRIBED: STATE_DESCRIBED,
                ANSWER_SKIPPED: STATE_SKIPPED,
            }.get(answer, STATE_UNKNOWN)
        if topic == TOPIC_INCOME_SCHEDULE:
            if self.income_schedule_stated:
                return STATE_ANSWERED
            return STATE_SKIPPED if answer == ANSWER_SKIPPED else STATE_UNKNOWN
        if topic == TOPIC_REGION:
            if self.country_confirmed:
                return STATE_ANSWERED
            return STATE_SKIPPED if answer == ANSWER_SKIPPED else STATE_UNKNOWN
        raise KeyError(topic)

    @property
    def _anything_stated(self) -> bool:
        return any(
            (
                self.income_set,
                self.currency_set,
                self.timezone_set,
                self.household_size_set,
                self.savings_preference_set,
            )
        )

    @property
    def budget_readiness(self) -> str:
        if not self.profile_complete:
            return READINESS_NOT_READY
        if (
            self.topic_state(TOPIC_REGULAR_PAYMENTS)
            in (
                STATE_ANSWERED,
                STATE_NONE,
            )
            and self.topic_state(TOPIC_EVERYDAY_SPENDING) == STATE_DESCRIBED
        ):
            return READINESS_PERSONALIZED
        return READINESS_PRELIMINARY

    @property
    def stage(self) -> str:
        if self.monthly_plan_exists or self.any_plan_saved:
            return STAGE_ESTABLISHED  # a returning user: nothing is required
        anything = self._anything_stated or any(
            (
                self.transaction_count,
                self.recurring_expense_count,
                self.savings_goal_count,
                self.spending_patterns_count,
                self.own_lines_count,
                self.answers,
            )
        )
        if not anything:
            return STAGE_NOT_STARTED
        if not self.profile_complete:
            return STAGE_IN_PROGRESS
        payments = self.topic_state(TOPIC_REGULAR_PAYMENTS)
        if payments == STATE_UNKNOWN:
            return STAGE_BASIC_PROFILE
        if self.budget_readiness == READINESS_PERSONALIZED:
            return STAGE_PERSONALIZED
        spending = self.topic_state(TOPIC_EVERYDAY_SPENDING)
        if STATE_SKIPPED in (payments, spending):
            return STAGE_SKIPPED
        if spending == STATE_PARTIAL:
            return STAGE_SPENDING_PARTIAL
        return STAGE_PRELIMINARY

    def open_topics(self) -> Tuple[List[str], List[str]]:
        """``(next_questions, optional_questions)``: topics nobody answered,
        in the order the conversation asks. A returning user (a saved plan)
        is never asked again — every open topic is optional for them."""
        unanswered = [
            topic
            for topic in QUESTION_ORDER
            if self.topic_state(topic) in (STATE_UNKNOWN, STATE_PARTIAL)
        ]
        if self.stage == STAGE_ESTABLISHED:
            return [], unanswered
        return unanswered, []

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
            # known looks final but is not; ask once (never mandatory). "None"
            # and "skip" are answers: asked once, never again.
            if self.topic_state(TOPIC_REGULAR_PAYMENTS) == STATE_UNKNOWN:
                return "ask_about_obligations"
            if self.topic_state(TOPIC_EVERYDAY_SPENDING) == STATE_UNKNOWN:
                # Optional: what the user spends on and how often. A budget
                # without it plans every line as a flexible budget.
                return "describe_spending"
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
    patterns = db.scalar(
        select(func.count())
        .select_from(SpendingPattern)
        .where(SpendingPattern.user_id == ctx.user_id)
    )
    own_lines = db.scalar(
        select(func.count())
        .select_from(McpBudgetLine)
        .where(McpBudgetLine.user_id == ctx.user_id)
    )
    plan_now = month_has_plan(db, ctx.user_id, ctx.today.year, ctx.today.month)
    return SetupState(
        income_set=income_set(ctx),
        currency_set=currency_set(ctx),
        timezone_set=timezone_set(ctx),
        household_size_set=ctx.household_size is not None,
        savings_preference_set=savings_set(ctx),
        monthly_plan_exists=plan_now,
        transaction_count=int(transaction_count or 0),
        recurring_expense_count=int(recurring or 0),
        savings_goal_count=int(goals or 0),
        months_of_history=int(months or 0),
        spending_patterns_count=int(patterns or 0),
        answers=setup_answers(db, ctx.user_id),
        own_lines_count=int(own_lines or 0),
        income_schedule_stated=ctx.income_regularity is not None,
        country_confirmed=ctx.country is not None,
        any_plan_saved=plan_now
        or latest_plan_month_before(db, ctx.user_id, ctx.today.year, ctx.today.month)
        is not None,
    )
