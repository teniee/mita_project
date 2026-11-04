"""Tool output models — published to ChatGPT as each tool's ``outputSchema``.

Money is a decimal string with exactly two fractional digits (``"1234.50"``),
never a float. Every response carries the currency the amounts are in. No
model contains an internal id, a timestamp of when the response was produced,
an email address or a free-text description the user typed.
"""

from __future__ import annotations

import datetime as dt
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_serializer

Money = str  # validated by MONEY_PATTERN in tests_mcp; kept a plain alias for schema clarity
MONEY_PATTERN = r"^-?\d+\.\d{2}$"

PlanStatus = Literal["generated", "not_generated"]
MonthPosition = Literal["past", "current", "future"]
# Who decides a budget line's amount (app/mcp/categories.source_of).
LineSource = Literal["set_by_you", "calculated_by_mita", "fixed_payment", "savings"]
SOURCE_DESCRIPTION = (
    "Who decides this line's amount: set_by_you (a budget line the user named "
    "and set; its category starts with 'my:'; MITA keeps the amount exactly), "
    "calculated_by_mita (MITA's allocation rules), fixed_payment (a bill or "
    "other stated payment) or savings. Never call a calculated_by_mita line the "
    "user's choice."
)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


def money_field(description: str) -> object:
    return Field(description=description, pattern=MONEY_PATTERN)


CATEGORY_LABEL_DESCRIPTION = (
    "MITA's display name for this category (app/mcp/categories.py). Show it "
    "exactly as given, translated consistently if you answer in another "
    "language; never rename or merge categories yourself. `category` is the "
    "stored code."
)


def category_label_field() -> object:
    return Field(description=CATEGORY_LABEL_DESCRIPTION)


# --- get_profile -----------------------------------------------------------


def _standard_profile_schema(schema: dict) -> None:
    """Publish exactly OpenAI's profile response schema: ``name`` is a string
    when present (absent, never null) and only ``id`` is required."""
    schema["properties"]["name"] = {
        "type": "string",
        "description": schema["properties"]["name"]["description"],
    }
    schema["required"] = ["id"]


class ProfileOut(_Out):
    """The ``openai/profile`` tool's result. OpenAI validates it against its
    standard profile schema (``id`` plus optional ``name``, ``email``,
    ``nickname``; nothing else) and an invalid response can prevent account
    connection (developers.openai.com/plugins/build/auth, "Support multiple
    accounts"). Currency and timezone are in get_setup_status and every result
    that needs them, not here."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra=_standard_profile_schema
    )

    id: str = Field(
        min_length=1,
        pattern=r"\S",
        description=(
            "Opaque MITA profile id: unique, unchanged across token refresh, "
            "reconnection and name changes, never reassigned; not the account's "
            "database id."
        ),
    )
    name: Optional[str] = Field(
        default=None,
        description="Display name the user set in MITA; omitted when none is set.",
    )
    nickname: str = Field(description="Masked e-mail address, to tell accounts apart.")

    @model_serializer(mode="wrap")
    def _omit_absent(self, handler):
        # An unset name is left out: the standard schema has no null.
        return {k: v for k, v in handler(self).items() if v is not None}


# --- list_transactions -----------------------------------------------------


REF_DESCRIPTION = (
    "Opaque reference to this expense, only for update_transaction or "
    "delete_transaction. Not meaningful to the user; do not show it."
)


class TransactionOut(_Out):
    ref: str = Field(description=REF_DESCRIPTION)
    date: dt.date = Field(
        description="Local calendar day of the expense in the user's timezone."
    )
    amount: Money = money_field("Expense amount (positive).")
    currency: str = Field(description="Currency recorded on the transaction.")
    category: str
    category_label: str = category_label_field()
    merchant: Optional[str] = Field(description="Merchant, if the user recorded one.")


class TransactionsOut(_Out):
    start_date: dt.date
    end_date: dt.date
    currency: str = Field(
        description="The user's MITA currency; matching_total is in it."
    )
    transactions: List[TransactionOut] = Field(description="Newest first.")
    returned_count: int
    matching_count: int = Field(
        description="All transactions matching the filters in the range."
    )
    matching_total: Money = money_field(
        "Sum of every matching transaction, not only the returned page."
    )
    has_more: bool = Field(
        description="True when more matching transactions exist than were returned."
    )
    next_cursor: Optional[str] = Field(
        description=(
            "When has_more is true: pass this as `cursor` (with the same dates and "
            "filters) to get the next page. Null on the last page."
        )
    )
    timezone: str = Field(description="IANA timezone the dates are in.")
    notes: List[str]


# --- get_spending_breakdown ------------------------------------------------


class CategorySpendOut(_Out):
    category: str = Field(
        description=(
            "MITA's stored category code, as recorded (for example 'subscriptions'). "
            "Do not rename it or merge it with other categories."
        )
    )
    category_label: str = category_label_field()
    total: Money = money_field("Total spent in this category in the range.")
    transaction_count: int
    share_percent: str = Field(
        description="This category's share of total spending, one decimal place.",
        pattern=r"^\d+\.\d$",
    )


class SpendingBreakdownOut(_Out):
    start_date: dt.date
    end_date: dt.date
    currency: str
    total_spent: Money = money_field("Sum of all expenses in the range.")
    transaction_count: int
    categories: List[CategorySpendOut] = Field(description="Largest first.")
    notes: List[str]


# --- get_financial_summary -------------------------------------------------


class FinancialSummaryOut(_Out):
    year: int
    month: int
    month_position: MonthPosition
    currency: str
    stated_monthly_income: Optional[Money] = Field(
        description=(
            "Monthly income the user entered in MITA. It is self-reported, not "
            "measured from deposits. Null when the user has not entered one."
        ),
        pattern=MONEY_PATTERN,
    )
    plan_status: PlanStatus
    planned_total: Optional[Money] = Field(
        description="Total budget allocated for the month. Null when no plan exists.",
        pattern=MONEY_PATTERN,
    )
    spent_total: Money = money_field("Total recorded expenses in the month.")
    remaining_total: Optional[Money] = Field(
        description="planned_total minus spent_total; negative means over budget. Null without a plan.",
        pattern=MONEY_PATTERN,
    )
    transaction_count: int
    top_categories: List[CategorySpendOut] = Field(
        description=(
            "Up to three largest spending categories, by MITA category name. Not a "
            "full breakdown: spending in any other category is not itemized here "
            "(get_spending_breakdown lists every category)."
        )
    )
    days_in_month: int
    days_elapsed: int = Field(
        description="Days of the month passed, counting today, in the user's timezone."
    )
    notes: List[str]


# --- get_budget_status -----------------------------------------------------


class CategoryBudgetOut(_Out):
    category: str = Field(
        description=(
            "Stored code of this budget line: the plan category when the line "
            "combines a plan category with the expenses recorded for it."
        )
    )
    category_label: str = category_label_field()
    category_codes: List[str] = Field(
        description=(
            "Every stored category this line adds up — e.g. plan 'transport gas' "
            "and expenses recorded as 'gas' are one line, 'Fuel'."
        )
    )
    planned: Money = money_field("Budget allocated to this category for the month.")
    spent: Money = money_field("Recorded spending in this category this month.")
    remaining: Money = money_field("planned minus spent; negative means over budget.")
    percent_used: Optional[str] = Field(
        description="spent / planned × 100, one decimal place. Null when nothing was planned.",
        pattern=r"^\d+\.\d$",
    )
    state: Literal["within_budget", "over_budget", "unplanned_spending", "not_started"]
    source: Optional[LineSource] = Field(
        description=SOURCE_DESCRIPTION + " Null when nothing was planned on the line."
    )


class DayBudgetOut(_Out):
    date: dt.date
    planned: Money = money_field(
        "Sum of today's spending allocations. Money set aside for savings, goals "
        "or investments is not included: it is not for spending. Bills planned "
        "for today (rent, mortgage, utilities, saved regular payments) are "
        "included and are not free to spend: see everyday_remaining."
    )
    spent: Money = money_field("Recorded spending today.")
    remaining: Money = money_field("planned minus spent for today.")
    everyday_planned: Money = money_field(
        "Today's plan without bills and money set aside: the everyday part, as "
        "the calendar shows it for today (planned_everyday)."
    )
    everyday_spent: Money = money_field("Recorded spending today outside bills.")
    everyday_remaining: Money = money_field(
        "everyday_planned minus everyday_spent: what today's plan leaves for "
        "everyday spending. The average a day for the rest of the month is "
        "get_budget_forecast.safe_daily_limit."
    )


class BudgetStatusOut(_Out):
    year: int
    month: int
    month_position: MonthPosition
    currency: str
    plan_status: PlanStatus
    total_planned: Money = money_field("Total allocation for the month.")
    total_spent: Money = money_field("Total recorded spending in the month.")
    total_remaining: Money = money_field("total_planned minus total_spent.")
    categories: List[CategoryBudgetOut]
    today: Optional[DayBudgetOut] = Field(description="Only for the current month.")
    notes: List[str]


# --- get_budget_forecast ---------------------------------------------------


class CategoryRiskOut(_Out):
    category: str = Field(
        description="Stored code of the budget line (see get_budget_status)."
    )
    category_label: str = category_label_field()
    monthly_planned: Money = money_field("Category allocation for the month.")
    monthly_spent: Money = money_field("Category spending so far.")
    daily_pace: Money = money_field("Average spent per elapsed day.")
    planned_per_day: Money = money_field("Allocation divided by days in the month.")
    pace_ratio: str = Field(
        description="daily_pace / planned_per_day (capped at 9.99).",
        pattern=r"^\d+\.\d{2}$",
    )
    days_until_exhausted: Optional[int] = Field(
        description="Days until the category allocation runs out at the current pace; 0 if already exhausted; null if nothing is being spent."
    )


class ForecastOut(_Out):
    year: int
    month: int
    month_position: MonthPosition
    currency: str
    plan_status: PlanStatus
    status: Optional[Literal["on_track", "warning", "danger", "no_data"]] = Field(
        description="on_track: projected balance ≥ 0; warning: projected overspend under 10% of plan; danger: 10% or more; no_data: month not started or nothing planned. Null without a plan. The projection compares spending with the whole plan, including savings_set_aside."
    )
    method: str
    days_in_month: int
    days_elapsed: int
    days_remaining: int
    total_planned: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    total_spent: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    remaining_budget: Optional[Money] = Field(
        default=None,
        description="total_planned minus total_spent: what is left of the whole plan, including money set aside.",
        pattern=MONEY_PATTERN,
    )
    savings_set_aside: Optional[Money] = Field(
        default=None,
        description="Part of remaining_budget that the plan sets aside for savings, savings goals or investments and that is not yet used. It is not spendable, so safe_daily_limit leaves it out.",
        pattern=MONEY_PATTERN,
    )
    current_daily_pace: Optional[Money] = Field(
        default=None,
        description="total_spent / days_elapsed.",
        pattern=MONEY_PATTERN,
    )
    commitments_reserved: Optional[Money] = Field(
        default=None,
        description="Part of remaining_budget that the month's bills still need. Bills are the rent, mortgage and utilities lines and the categories of saved regular payments due this month; each needs its reviewed plan — or the saved payments due on it when more — minus what is recorded under that category, never below zero. Not spendable, so safe_daily_limit leaves it out. Other plan lines, including medical insurance, are everyday money: no expense is recorded under them, so MITA cannot see them paid.",
        pattern=MONEY_PATTERN,
    )
    safe_daily_limit: Optional[Money] = Field(
        default=None,
        description="(remaining_budget minus savings_set_aside minus commitments_reserved) / days_remaining: how much can be spent per day after today while keeping the money set aside and the money the bills still need untouched. Negative when spending has already used more than the plan leaves for spending.",
        pattern=MONEY_PATTERN,
    )
    projected_month_end_spend: Optional[Money] = Field(
        default=None, pattern=MONEY_PATTERN
    )
    projected_month_end_balance: Optional[Money] = Field(
        default=None,
        description="total_planned minus projected_month_end_spend (the whole plan, including savings_set_aside); negative is projected overspend.",
        pattern=MONEY_PATTERN,
    )
    categories_at_risk: List[CategoryRiskOut] = Field(
        description="Categories spending at 1.2× or more of their planned daily rate, worst first."
    )
    notes: List[str]


# --- get_goals -------------------------------------------------------------


class GoalProjectionOut(_Out):
    basis: Literal[
        "funded", "no_target_date", "target_date_passed", "monthly_contribution"
    ]
    on_track: Optional[bool] = Field(
        description="Whether saved + monthly_contribution × months left reaches the target by the target date. Null when there is no target date."
    )
    months_remaining: Optional[str] = Field(default=None, pattern=r"^\d+\.\d{2}$")
    required_monthly_contribution: Optional[Money] = Field(
        default=None, pattern=MONEY_PATTERN
    )
    projected_saved_by_target_date: Optional[Money] = Field(
        default=None, pattern=MONEY_PATTERN
    )
    shortfall: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)


class GoalOut(_Out):
    title: str
    category: Optional[str]
    category_label: str = category_label_field()
    status: Literal["active", "paused", "completed", "cancelled"]
    priority: Optional[str]
    target_amount: Money = money_field("Goal target.")
    saved_amount: Money = money_field("Saved so far.")
    remaining_amount: Money = money_field("Target minus saved, never below zero.")
    progress_percent: str = Field(pattern=r"^\d+\.\d$")
    monthly_contribution: Optional[Money] = Field(pattern=MONEY_PATTERN)
    target_date: Optional[dt.date]
    projection: Optional[GoalProjectionOut] = Field(
        description="Only for active goals."
    )


class GoalsOut(_Out):
    currency: str
    goals: List[GoalOut]
    notes: List[str]


# --- get_recurring_expenses ------------------------------------------------


class DueThisMonthOut(_Out):
    due_date: dt.date
    amount: Money = money_field("Amount due on this date.")
    paid: Money = money_field(
        "Paid by the expenses the user linked to this due date (obligation_ref). "
        "Spending in the same category never counts."
    )
    outstanding: Money = money_field("amount minus paid, never below 0.")


class ScheduledExpenseOut(_Out):
    obligation_ref: str = Field(
        description=(
            "Opaque reference of this saved payment: pass it as obligation_ref "
            "when the user records (or corrects) the expense that paid it."
        )
    )
    category: str
    category_label: str = category_label_field()
    amount: Money = money_field("Scheduled amount.")
    merchant: Optional[str]
    due_date: dt.date = Field(
        description="Next date the user scheduled this expense for."
    )
    recurrence: Optional[str] = Field(
        description="Repeat rule the user set, e.g. 'monthly'; null for one-time."
    )
    due_this_month: List[DueThisMonthOut] = Field(
        description="Its due dates in the user's current month and what is paid on each."
    )


class MarkedRecurringOut(_Out):
    label: str = Field(
        description="Merchant if recorded, otherwise the category label."
    )
    category: str
    category_label: str = category_label_field()
    last_amount: Money = money_field("Amount of the most recent marked transaction.")
    last_date: dt.date
    occurrences_in_lookback: int


class RecurringOut(_Out):
    currency: str
    scheduled_recurring: List[ScheduledExpenseOut] = Field(
        description="Repeating expenses the user scheduled in MITA (confirmed)."
    )
    upcoming_one_time: List[ScheduledExpenseOut] = Field(
        description="One-time expenses the user scheduled for the next 60 days (confirmed)."
    )
    marked_recurring: List[MarkedRecurringOut] = Field(
        description="Transactions the user marked as recurring when recording them, grouped by merchant/category (confirmed by the user, not detected)."
    )
    lookback_start_date: dt.date
    inferred: List[MarkedRecurringOut] = Field(
        description="Always empty: MITA does not infer subscriptions from merchant names."
    )
    notes: List[str]


# --- errors ----------------------------------------------------------------


class ErrorOut(_Out):
    category: Literal[
        "auth", "forbidden", "validation", "rate_limited", "unavailable", "internal"
    ]
    message: str


# --- get_setup_status / update_financial_profile ---------------------------

ProfileField = Literal[
    "monthly_net_income",
    "currency",
    "timezone",
    "household_size",
    "monthly_savings_target",
]
# Everything update_financial_profile can change (the five fields above are
# the basic profile; the rest are optional, 2.8).
UpdatedField = Literal[
    "monthly_net_income",
    "currency",
    "timezone",
    "household_size",
    "monthly_savings_target",
    "country",
    "income_regularity",
    "pay_frequency",
    "pay_days",
    "minimum_monthly_income",
    "regional_comparisons",
    "setup_answers",
]
IncomeRegularity = Literal["regular", "variable"]
PayFrequency = Literal[
    "monthly", "twice_monthly", "every_two_weeks", "weekly", "irregular"
]


class KnownProfileOut(_Out):
    monthly_net_income: Optional[Money] = Field(
        description="Monthly net income the user stated. Null when not stated.",
        pattern=MONEY_PATTERN,
    )
    currency: Optional[str] = Field(
        description="ISO 4217 code of the user's MITA currency. Null when not stated."
    )
    timezone: Optional[str] = Field(
        description="IANA timezone MITA uses for 'today'. Null when not stated."
    )
    household_size: Optional[int] = Field(
        description="People whose spending this budget covers. Null when not stated."
    )
    monthly_savings_target: Optional[Money] = Field(
        description="Amount the user wants to save each month. Null when not stated.",
        pattern=MONEY_PATTERN,
    )
    country: Optional[str] = Field(
        default=None,
        description=(
            "ISO 3166-1 alpha-2 code of the country where the user said they "
            "usually live and spend money. Null until the user confirms one."
        ),
    )
    income_regularity: Optional[IncomeRegularity] = Field(
        default=None,
        description="regular: about the same every month; variable: it changes. Null when not stated.",
    )
    pay_frequency: Optional[PayFrequency] = Field(
        default=None, description="How often income arrives. Null when not stated."
    )
    pay_days: List[int] = Field(
        default_factory=list,
        description="Days of the month income usually arrives on, as stated (31 = last day).",
    )
    minimum_monthly_income: Optional[Money] = Field(
        default=None,
        description=(
            "For variable income: the least the user said they receive in a "
            "month. Null when not stated."
        ),
        pattern=MONEY_PATTERN,
    )


NextStep = Literal[
    "complete_profile",
    "ask_about_obligations",
    "describe_spending",
    "build_budget",
    "record_expenses",
    "ready",
]
NEXT_STEP_DESCRIPTION = (
    "complete_profile: ask for missing_fields. ask_about_obligations: before a "
    "first budget, ask once whether the user has regular payments such as rent, "
    "utilities, loans or subscriptions and save them with add_recurring_expense; "
    "a budget previewed without them assumes there are none. describe_spending: "
    "before a first budget, ask in one short message what they spend on each month "
    "(their own amounts) and how often they buy (groceries every Wednesday, coffee "
    "whenever); save it with save_spending_patterns — optional, never mandatory. "
    "build_budget: offer preview_monthly_budget. record_expenses / ready: nothing "
    "to set up."
)


OnboardingStage = Literal[
    "not_started",
    "in_progress",
    "basic_profile_completed",
    "spending_partially_known",
    "ready_for_preliminary_budget",
    "ready_for_personalized_budget",
    "optional_questions_skipped",
    "established",
]
BudgetReadiness = Literal["not_ready", "preliminary", "personalized"]
SetupTopic = Literal[
    "profile",
    "region",
    "income_schedule",
    "regular_payments",
    "everyday_spending",
    "irregular_expenses",
]
TopicState = Literal[
    "answered", "none", "described", "partially_known", "skipped", "unknown"
]
STAGE_DESCRIPTION = (
    "Where setup stands, derived from what is saved (so it survives "
    "reconnecting): not_started; in_progress (basic profile incomplete); "
    "basic_profile_completed (regular payments not asked yet); "
    "spending_partially_known; ready_for_preliminary_budget; "
    "ready_for_personalized_budget; optional_questions_skipped (the user chose "
    "to skip — a budget is preliminary); established (a returning user with a "
    "saved plan: never make them repeat setup)."
)
READINESS_DESCRIPTION = (
    "not_ready: income, currency or timezone missing. preliminary: a budget "
    "can be previewed, but MITA does not know the user's regular payments or "
    "everyday spending, so it suggests its default lines — say so. "
    "personalized: the user answered both; MITA budgets only the lines they "
    "confirmed."
)
TOPIC_STATE_DESCRIPTION = (
    "answered (saved facts, e.g. payments saved or a country confirmed), none "
    "(the user said they have none), described, partially_known, skipped (the "
    "user chose not to answer — do not ask again unless they bring it up), "
    "unknown (never asked — not the same as none)."
)


class SetupTopicOut(_Out):
    topic: SetupTopic
    state: TopicState = Field(description=TOPIC_STATE_DESCRIPTION)
    needed_for_personalized_budget: bool = Field(
        description="True for regular_payments and everyday_spending."
    )


class OnboardingOut(_Out):
    stage: OnboardingStage = Field(description=STAGE_DESCRIPTION)
    budget_readiness: BudgetReadiness = Field(description=READINESS_DESCRIPTION)
    topics: List[SetupTopicOut]
    next_questions: List[SetupTopic] = Field(
        description=(
            "Topics to ask about now, in this order, combined into as few short "
            "messages as possible. Empty for a returning user."
        )
    )
    optional_questions: List[SetupTopic] = Field(
        description=(
            "For a returning user: topics never answered. Ask only if the user "
            "wants to update how MITA plans; never block anything on them."
        )
    )


class CountrySuggestionOut(_Out):
    country: str = Field(description="ISO 3166-1 alpha-2 code.")
    country_name: str
    source: Literal["chatgpt_approximate_location"] = Field(
        description=(
            "The country of ChatGPT's approximate location for this "
            "conversation — where the user is now, not necessarily where they "
            "live. A suggestion to ask about, never a fact."
        )
    )


class RegionOut(_Out):
    country: Optional[str] = Field(
        description="The country the user confirmed (ISO 3166-1 alpha-2); null until then."
    )
    country_name: Optional[str]
    source: Optional[Literal["stated", "chatgpt_location_confirmed"]] = Field(
        description=(
            "stated: the user named it; chatgpt_location_confirmed: the user "
            "confirmed the country of ChatGPT's approximate location."
        )
    )
    regional_context: bool = Field(
        description="The user's switch for regional statistics (true unless they turned it off)."
    )
    suggestion: Optional[CountrySuggestionOut] = Field(
        description=(
            "Only while no country is confirmed: ask, e.g. 'Do you normally "
            "live and spend money in Bulgaria, or should MITA use another "
            "country?' Save only the user's answer."
        )
    )


LineStatus = Literal["user_confirmed", "mita_suggested"]
LINE_STATUS_DESCRIPTION = (
    "user_confirmed: the user named this line or said they have this spending "
    "(a stated pattern); mita_suggested: one of MITA's default lines the user "
    "has not confirmed — say it is MITA's suggestion and ask whether it applies."
)


class SpendingLineOut(_Out):
    category: str = Field(
        description="The line's code ('my:<label>' for the user's own lines)."
    )
    category_label: str = category_label_field()
    source: Literal["set_by_you", "calculated_by_mita"] = Field(
        description="set_by_you: the user's own line; calculated_by_mita: MITA's suggestion."
    )
    line_status: LineStatus = Field(
        default="mita_suggested", description=LINE_STATUS_DESCRIPTION
    )
    monthly_amount: Optional[Money] = Field(
        description="In the current month's saved plan; null when the month has no plan.",
        pattern=MONEY_PATTERN,
    )
    pattern_stated: bool = Field(
        description="True when the user said how they buy for this line."
    )
    spending_type: Literal["planned", "flexible"] = Field(
        description="planned: on known days; flexible: no purchase dates (also when not stated)."
    )
    pattern: str = Field(description="How the user buys for it, in plain words.")


class SpendingProfileOut(_Out):
    lines: List[SpendingLineOut] = Field(
        description=(
            "The current month's spending lines (not bills, not savings) and any "
            "line the user described."
        )
    )
    lines_without_pattern: List[str] = Field(
        description=(
            "Lines whose purchase pattern is not known: MITA plans them as flexible "
            "budgets with no purchase dates. Ask about them only if the user wants "
            "a day-by-day plan; never guess."
        )
    )
    not_applicable: List[str] = Field(
        description="MITA's lines the user said they do not have (left out of the plan)."
    )


class SetupStatusOut(_Out):
    profile_complete: bool = Field(
        description="True when income, currency and timezone are known — enough to build a budget."
    )
    income_set: bool
    currency_set: bool
    timezone_set: bool
    household_size_set: bool
    savings_preference_set: bool
    monthly_plan_exists: bool = Field(
        description="True when MITA has a saved budget plan for the current month."
    )
    current_month: str = Field(
        description="The user's current month, YYYY-MM.", pattern=r"^\d{4}-\d{2}$"
    )
    transaction_count: int = Field(description="Recorded expenses, all time.")
    recurring_expense_count: int
    savings_goal_count: int = Field(description="Active savings goals.")
    months_of_history: int = Field(
        description="Calendar months that contain at least one recorded expense."
    )
    missing_fields: List[ProfileField] = Field(
        description="Profile fields MITA does not know yet. Ask only for these."
    )
    suggested_next_step: NextStep = Field(description=NEXT_STEP_DESCRIPTION)
    known: KnownProfileOut = Field(
        description="Values MITA already has. Do not ask the user for these again."
    )
    spending: SpendingProfileOut = Field(
        description=(
            "How the user spends, line by line, as far as they told MITA. Never "
            "re-ask what is stated here."
        )
    )
    onboarding: OnboardingOut
    region: RegionOut
    notes: List[str]


class SpendingPatternSavedOut(_Out):
    category: str
    category_label: str = category_label_field()
    kind: Literal["planned", "flexible", "not_applicable"]
    pattern: str = Field(description="What MITA saved, in plain words.")
    next_purchases: List[dt.date] = Field(
        description="For planned lines: the next purchase dates from today (up to 4)."
    )
    purchase_dates_stated: Optional[bool] = Field(
        description="False when MITA spaced a number of purchases a month evenly (say so)."
    )
    typical_amount: Optional[Money] = Field(pattern=MONEY_PATTERN)


class SpendingPatternsOut(_Out):
    status: Literal["saved", "unchanged"]
    saved: List[SpendingPatternSavedOut]
    plans_to_review: List[str] = Field(
        description=(
            "Saved monthly plans (YYYY-MM) that still use the earlier way of "
            "spending: they change only when the user previews that month "
            "(preview_monthly_budget) and saves it."
        )
    )
    notes: List[str]


class ProfileUpdateOut(_Out):
    status: Literal["updated", "unchanged"]
    updated_fields: List[UpdatedField]
    profile: KnownProfileOut
    profile_complete: bool
    missing_fields: List[ProfileField]
    suggested_next_step: NextStep = Field(description=NEXT_STEP_DESCRIPTION)
    onboarding: OnboardingOut
    region: RegionOut
    notes: List[str]


# --- add_transaction(s) / update_transaction / delete_transaction ----------


class PaidObligationOut(_Out):
    obligation_ref: str = Field(
        description="The saved regular payment this expense paid (its obligation_ref)."
    )
    name: str = Field(description="Name the user saved for the payment.")
    due_date: dt.date = Field(description="The due date this expense paid.")


class RecordedTransactionOut(_Out):
    ref: str = Field(description=REF_DESCRIPTION)
    date: dt.date = Field(description="Local calendar day of the expense.")
    amount: Money = money_field("Amount recorded.")
    currency: str
    category: str
    category_label: str = category_label_field()
    merchant: Optional[str] = Field(description="Merchant exactly as recorded.")
    paid_obligation: Optional[PaidObligationOut] = Field(
        default=None,
        description=(
            "The saved regular payment and due date the user said this expense "
            "paid; null for every other expense (spending in a bill's category "
            "does not pay the bill)."
        ),
    )


class TransactionsRecordedOut(_Out):
    status: Literal["recorded", "already_recorded"] = Field(
        description=(
            "'already_recorded': this exact request (same idempotency_key) was "
            "recorded before; nothing new was written."
        )
    )
    currency: str
    transactions: List[RecordedTransactionOut]
    count: int
    total: Money = money_field("Sum of the expenses in this response.")
    month_to_date_spent: Money = money_field(
        "All recorded spending this month so far, after this write."
    )
    notes: List[str]


TransactionField = Literal["amount", "category", "date", "merchant", "paid_obligation"]


class TransactionChangeOut(_Out):
    status: Literal["updated", "unchanged", "deleted", "already_deleted"]
    changed_fields: List[TransactionField]
    transaction: RecordedTransactionOut = Field(
        description="The expense after the change (for a deletion: as it was)."
    )
    month_to_date_spent: Money = money_field(
        "All recorded spending this month so far, after this change."
    )
    notes: List[str]


# --- add_recurring_expense / create_savings_goal ---------------------------


class RecurringCreatedOut(_Out):
    status: Literal["created", "already_created"] = Field(
        description="'already_created': this exact request (same idempotency_key) was saved before."
    )
    name: str = Field(description="The name exactly as the user gave it.")
    category: str
    category_label: str = category_label_field()
    amount: Money = money_field("Amount each time it is due.")
    currency: str
    recurrence: Literal["monthly", "weekly"]
    next_due_date: dt.date = Field(
        description="The next due date MITA computed from what the user said."
    )
    notes: List[str]


class GoalCreatedOut(_Out):
    status: Literal["created", "already_created"]
    title: str = Field(description="The title exactly as the user gave it.")
    category: str
    category_label: str = category_label_field()
    currency: str
    target_amount: Money = money_field("Goal target.")
    saved_amount: Money = money_field("Already saved, as the user stated.")
    progress_percent: str = Field(pattern=r"^\d+\.\d$")
    target_date: Optional[dt.date]
    required_monthly_contribution: Optional[Money] = Field(
        description=(
            "Arithmetic only: (target − saved) ÷ months until the target date "
            "(30.44-day months, at least one). Null without a target date."
        ),
        pattern=MONEY_PATTERN,
    )
    reserved_in_budget_plan: bool = Field(
        description=(
            "True when MITA set aside the daily amounts for this goal in the "
            "current month's plan. Always false for a goal without a target date: "
            "only a target date makes MITA reserve a monthly amount, and a goal "
            "cannot be given one (or a contribution) after it is created."
        )
    )
    notes: List[str]


# --- preview_monthly_budget / save_monthly_budget -------------------------


class ObligationOut(_Out):
    name: Optional[str] = Field(description="Name the user gave the obligation.")
    line: str = Field(
        description=(
            "The plan line holding this payment's money (its own line, 'bill:…'; "
            "the same code in get_budget_status and the calendar)."
        )
    )
    category: str
    category_label: str = category_label_field()
    amount: Money = money_field("Amount counted in this month.")
    basis: str = Field(
        description="How it was counted, e.g. 'monthly', 'weekly × 4 Mondays', 'one-time on 2026-10-20'."
    )
    due_dates: List[dt.date] = Field(
        description=(
            "The dates it is due on this month. The plan holds its full amount on "
            "each of these dates and nowhere else."
        )
    )


class PlannedPurchaseOut(_Out):
    date: dt.date = Field(
        description="A real date of the month the purchase is planned on."
    )
    amount: Money = money_field(
        "Money planned for that purchase (an allocation, not a transaction)."
    )
    proposed: bool = Field(
        description="True when MITA proposed the date (the user named no day): say so."
    )


SpendingType = Literal["planned", "flexible"]
PatternSource = Literal["user_confirmed", "mita_default"]


class RegionalComparisonOut(_Out):
    """An official national figure next to a budget line — for comparison
    only: it never set or changes the line's amount (2.8 M4)."""

    category: str = Field(
        description="The statistic's category: food, transport, restaurants…"
    )
    category_label: str = Field(description="The category as the provider names it.")
    display: str = Field(
        description="The figure with its unit, e.g. '6.0 % over 12 months'."
    )
    period: str
    stale: bool = Field(
        description="True when too old to call current: give its period."
    )
    estimated: bool = Field(
        description="True when the provider marks it estimated or provisional."
    )
    geographic_scope: str = Field(
        description="Always a whole country, never a city or shop."
    )
    source: str = Field(description="Attribution to show with it.")
    limitation: str = Field(description="What the figure is not.")


class RegionalSummaryOut(_Out):
    country: str
    country_name: str
    statistics_shown: int = Field(
        description="How many lines carry a regional_comparison."
    )
    note: str


class AllocationOut(_Out):
    category: str = Field(
        description=(
            "Line code: MITA's plan category as the engine names it, or "
            "'my:<label>' for a budget line the user set (its stable id: pass it "
            "as budget_line when recording an expense for it)."
        )
    )
    category_label: str = category_label_field()
    amount: Money = money_field("Monthly allocation.")
    source: LineSource = Field(description=SOURCE_DESCRIPTION)
    replaces: List[str] = Field(
        description=(
            "For a line the user set: MITA's own lines it takes the place of "
            "(those are not in the plan). Empty otherwise."
        )
    )
    spending_type: SpendingType = Field(
        description=(
            "planned: the monthly amount is split exactly over the purchase dates in "
            "purchases; flexible: a monthly limit with no purchase dates (per_day is "
            "guidance, not a purchase)."
        )
    )
    pattern: str = Field(
        description="How the user buys for this line, in plain words (e.g. 'every Wednesday')."
    )
    pattern_source: PatternSource = Field(
        description=(
            "user_confirmed: the user stated the pattern; mita_default: nothing was "
            "stated, so the line is flexible and MITA invented no purchase dates."
        )
    )
    purchases: List[PlannedPurchaseOut] = Field(
        description="Planned purchases on their real dates; empty for a flexible line."
    )
    purchase_dates_stated: Optional[bool] = Field(
        description=(
            "For planned lines: true when the user named the days, false when they "
            "gave only a number of purchases a month and MITA spaced them evenly "
            "(say so to the user). Null for flexible lines."
        )
    )
    per_day: Optional[Money] = Field(
        description="For flexible lines: the monthly amount ÷ the days of the month, exact.",
        pattern=MONEY_PATTERN,
    )
    per_day_rounded: Optional[str] = Field(
        description="per_day to whole currency units, for a short summary ('about €7 a day').",
        pattern=r"^\d+$",
    )
    typical_amount: Optional[Money] = Field(
        description="What one purchase usually costs, as the user said; null when not said.",
        pattern=MONEY_PATTERN,
    )
    line_status: LineStatus = Field(
        default="mita_suggested", description=LINE_STATUS_DESCRIPTION
    )
    recorded_average: Optional[Money] = Field(
        default=None,
        description=(
            "What the user's recorded expenses on this line averaged per month "
            "over history.months_used complete months; null without history. A "
            "fact to compare with (calculated from recorded history): to use it, "
            "the user sets it as their amount (budget_lines). MITA never does."
        ),
        pattern=MONEY_PATTERN,
    )
    regional_comparison: Optional[RegionalComparisonOut] = Field(
        default=None,
        description=(
            "The official national price change for this kind of spending in the "
            "user's confirmed country, from MITA's copy of official statistics. "
            "Comparison only: say so, give source and period; never use it to "
            "change an amount."
        ),
    )


class NotIncludedLineOut(_Out):
    category: str
    category_label: str = category_label_field()
    would_suggest: Money = money_field(
        "What MITA's rules would give this line if the user says they have this "
        "spending (MITA's suggestion, not the user's amount)."
    )


class PersonalizationOut(_Out):
    level: Literal["preliminary", "personalized"] = Field(
        description=(
            "personalized: the user answered the regular-payments question and "
            "described their everyday spending, so only lines they confirmed are "
            "budgeted. preliminary: something is still unknown — present the "
            "plan as a first draft with MITA's suggestions."
        )
    )
    regular_payments: TopicState = Field(description=TOPIC_STATE_DESCRIPTION)
    everyday_spending: TopicState = Field(description=TOPIC_STATE_DESCRIPTION)


class VariableIncomeOut(_Out):
    planned_on: Money = money_field(
        "The monthly net income the plan uses: the figure the user stated."
    )
    minimum_monthly_income: Optional[Money] = Field(
        description="The least the user said they receive in a month; null when not stated.",
        pattern=MONEY_PATTERN,
    )
    committed: Money = money_field(
        "Bills and fixed payments, savings and the user's own lines: what the "
        "plan cannot lower by itself."
    )
    shortfall_at_minimum: Optional[Money] = Field(
        description=(
            "How much the whole plan (plan_total) exceeds a month at the minimum "
            "income (0.00 when it fits); null without a minimum."
        ),
        pattern=MONEY_PATTERN,
    )
    committed_exceeds_minimum: Optional[bool] = Field(
        description=(
            "True when even the committed part is more than a minimum month; "
            "null without a minimum."
        )
    )


class ExcludedLineOut(_Out):
    category: str
    category_label: str = category_label_field()
    amount_freed: Optional[Money] = Field(
        default=None,
        description="What MITA's rules would have given this line if it applied.",
        pattern=MONEY_PATTERN,
    )


class FreedLineOut(_Out):
    category: str
    category_label: str = category_label_field()
    amount: Money = money_field("What this line gained from the freed money.")


class FreedMoneyOut(_Out):
    total: Money = money_field(
        "What the lines the user said do not apply would have had."
    )
    to_other_lines: List[FreedLineOut] = Field(
        description=(
            "Where MITA's usual shares put it: its other lines, before the user "
            "chooses. To give it to particular lines instead (more for groceries), "
            "set those lines' amounts in budget_lines — kept exactly."
        )
    )
    unallocated: Money = money_field("What stayed unassigned to any line.")


class UnconfirmedMoneyOut(_Out):
    total: Money = money_field("What MITA would have suggested for not_included.")
    to_other_lines: List[FreedLineOut] = Field(
        description=(
            "What lines of this plan gained instead, by MITA's usual shares "
            "(only when they had been scaled down)."
        )
    )
    unallocated: Money = money_field(
        "What stayed unallocated: still free to spend and inside the daily figure."
    )


class PlanChangeOut(_Out):
    category: str
    category_label: str = category_label_field()
    before: Optional[Money] = Field(
        description="Monthly amount in the saved plan; null for a new line.",
        pattern=MONEY_PATTERN,
    )
    after: Optional[Money] = Field(
        description="Monthly amount after saving; null for a line that leaves the plan.",
        pattern=MONEY_PATTERN,
    )
    source: LineSource = Field(description=SOURCE_DESCRIPTION)


class DataSourceOut(_Out):
    input: str
    source: str


class HistoryUsedOut(_Out):
    months_used: int = Field(
        description="Complete months of recorded expenses compared (0-3)."
    )
    period_start: Optional[dt.date]
    period_end: Optional[dt.date]
    average_monthly_spending: Optional[Money] = Field(pattern=MONEY_PATTERN)


class BudgetPreviewOut(_Out):
    status: Literal["preview"] = Field(
        description="Nothing is saved yet. Show the user this plan; save it only with save_monthly_budget after they confirm."
    )
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    currency: str
    existing_plan: bool = Field(
        description="True when the month already has a saved plan; saving this one replaces it."
    )
    stated_monthly_income: Money = money_field("Monthly net income the user stated.")
    fixed_obligations: List[ObligationOut]
    fixed_obligations_total: Money = money_field("Sum of fixed_obligations.")
    savings_allocation: Money = money_field(
        "Set aside for savings this month (the user's target, reduced only if it does not fit)."
    )
    category_allocations: List[AllocationOut] = Field(
        description=(
            "Spending lines: the user's own budget lines first (source "
            "set_by_you, exactly as they set them), then MITA's suggested "
            "allocation of the money left (calculated_by_mita), largest first."
        )
    )
    not_applicable_lines: List[ExcludedLineOut] = Field(
        description=(
            "MITA's lines the user said they do not have (spending pattern "
            "not_applicable): left out of the plan."
        )
    )
    freed_money: Optional[FreedMoneyOut] = Field(
        default=None,
        description=(
            "Where the money of not_applicable_lines went (compared with the same "
            "plan keeping them). Show it to the user; nothing moves without a save."
        ),
    )
    not_included: List[NotIncludedLineOut] = Field(
        default_factory=list,
        description=(
            "MITA's lines the user never mentioned, left out because they said "
            "the spending they described is what they regularly spend on. Not "
            "budgeted, not zero: ask once whether any applies; if one does, "
            "save its pattern (save_spending_patterns) or their amount "
            "(budget_lines) and preview again."
        ),
    )
    not_included_money: Optional[UnconfirmedMoneyOut] = Field(
        default=None,
        description="Where the money of not_included went (compared with keeping them).",
    )
    personalization: PersonalizationOut
    variable_income: Optional[VariableIncomeOut] = Field(
        default=None,
        description=(
            "Only when the user said their income varies: what the plan means "
            "in a month at their minimum. MITA still plans on the stated "
            "monthly figure; never pick another basis yourself."
        ),
    )
    regional: Optional[RegionalSummaryOut] = Field(
        default=None,
        description=(
            "When the user confirmed a country and kept regional statistics on: "
            "which lines carry an official comparison. None otherwise."
        ),
    )
    user_set_total: Money = money_field(
        "Sum of the user's own budget lines (source set_by_you)."
    )
    unallocated: Money = money_field(
        "Money MITA's rules leave unassigned to any line (free to spend)."
    )
    flexible_total: Money = money_field(
        "Income minus fixed obligations, savings and the user's own lines: "
        "MITA's lines plus unallocated."
    )
    plan_total: Money = money_field(
        "Everything the saved plan lays out over the month's days."
    )
    daily_flexible_average: Money = money_field(
        "flexible_total plus user_set_total, divided by the days in the month."
    )
    changes: List[PlanChangeOut] = Field(
        description=(
            "When a plan for the month is already saved: every line whose amount "
            "differs, before and after. Empty otherwise."
        )
    )
    days_in_month: int
    days_remaining: Optional[int] = Field(
        description="For the current month: days left including today."
    )
    recurring_included: bool = Field(
        description="True when saved repeating obligations are part of this plan."
    )
    history: HistoryUsedOut
    assumptions: List[str]
    warnings: List[str]
    data_sources: List[DataSourceOut]
    draft_token: str = Field(
        description=(
            "Pass exactly this to save_monthly_budget after the user confirms. It "
            "only saves this exact plan, expires after 2 hours, and stops working "
            "if the user's income, savings target or obligations change."
        )
    )
    expires_at: dt.datetime


class AmountSetOut(_Out):
    category: str = Field(description="The line's stable id ('my:<label>').")
    category_label: str = category_label_field()
    amount: Money = money_field("The monthly amount the user set, saved exactly.")


class BudgetSavedOut(_Out):
    status: Literal["saved", "replaced", "already_saved"] = Field(
        description="'replaced': an earlier plan for this month was replaced. 'already_saved': this exact plan was already in place."
    )
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    currency: str
    plan_total: Money = money_field("Total laid out over the month.")
    category_count: int
    set_by_you: List[AmountSetOut] = Field(
        description=(
            "The user's own budget lines, saved exactly as set. Only these may be "
            "described as kept from what the user said."
        )
    )
    notes: List[str]


# --- get_spending_history / get_financial_climate ---------------------------

MonthStatus = Literal["before_tracking", "recorded", "in_progress"]


class CategoryAmountOut(_Out):
    category: str = Field(description="MITA category code, as recorded.")
    category_label: str = category_label_field()
    total: Money = money_field("Recorded spending in this category.")
    transaction_count: int


class HistoryMonthOut(_Out):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    status: MonthStatus = Field(
        description=(
            "before_tracking: before the user's first recorded expense — MITA has "
            "no data, which is NOT zero spending. recorded: a complete month "
            "(0 transactions = nothing was recorded, not necessarily nothing spent). "
            "in_progress: the current month so far."
        )
    )
    transaction_count: int
    total_spent: Money = money_field("Recorded spending in the month.")
    categories: List[CategoryAmountOut] = Field(description="Largest first.")


class TrendOut(_Out):
    status: Literal["ok", "insufficient_data"] = Field(
        description="insufficient_data when fewer than 3 complete months are recorded."
    )
    latest_month: Optional[str] = None
    latest_total: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    earlier_average: Optional[Money] = Field(
        default=None,
        pattern=MONEY_PATTERN,
        description="Average of the earlier complete months in the window.",
    )
    change_percent: Optional[str] = Field(
        default=None, description="(latest − earlier_average) ÷ earlier_average × 100."
    )
    direction: Optional[Literal["up", "down", "unchanged"]] = None


class CategoryTrendOut(_Out):
    category: str
    category_label: str = category_label_field()
    trend: TrendOut


class SpendingHistoryOut(_Out):
    period_start: dt.date
    period_end: dt.date
    currency: str
    timezone: str
    category: Optional[str] = Field(description="The category filter, if any.")
    category_label: Optional[str] = Field(
        description="Display name of the category filter, if any."
    )
    months_requested: int
    months_with_data: int = Field(
        description="Months with at least one recorded expense."
    )
    complete_months: int = Field(
        description="Complete months since tracking began (used for averages)."
    )
    months: List[HistoryMonthOut] = Field(description="Oldest first.")
    average_monthly_spending: Optional[Money] = Field(
        description="Mean over complete months. Null when there are none.",
        pattern=MONEY_PATTERN,
    )
    median_monthly_spending: Optional[Money] = Field(pattern=MONEY_PATTERN)
    current_month_to_date: Optional[Money] = Field(pattern=MONEY_PATTERN)
    largest_category: Optional[CategoryAmountOut] = Field(
        description="Largest category over the whole window."
    )
    trend: TrendOut = Field(
        description="Latest complete month vs the average of the earlier complete months."
    )
    category_trends: List[CategoryTrendOut] = Field(
        description="Same rule per category, for the largest categories (empty with a category filter)."
    )
    notes: List[str]


class PaceOut(_Out):
    day_of_month: int
    spent_to_date: Money = money_field("Recorded this month up to today.")
    prior_average_to_same_day: Optional[Money] = Field(
        description="Average spent by the same day in the complete months of the window.",
        pattern=MONEY_PATTERN,
    )
    months_compared: int


class AdherenceOut(_Out):
    months_with_plan: int = Field(
        description="Complete months that had a saved budget plan."
    )
    months_within_plan: int = Field(
        description="Recorded spending ≤ the month's plan total."
    )
    months_over_plan: int


class ClimateGoalsOut(_Out):
    active_count: int
    total_target: Money = money_field("Sum of active goal targets.")
    total_saved: Money = money_field("Sum saved towards them.")


class ClimateObligationsOut(_Out):
    count: int = Field(description="Saved obligations that fall in the current month.")
    current_month_total: Money = money_field("What they add up to this month.")


class CompletenessOut(_Out):
    complete_months: int
    months_before_tracking: int
    in_progress_month: bool


class FinancialClimateOut(_Out):
    period_start: dt.date
    period_end: dt.date
    currency: str
    months_with_data: int
    total_transactions: int
    average_monthly_spending: Optional[Money] = Field(pattern=MONEY_PATTERN)
    median_monthly_spending: Optional[Money] = Field(pattern=MONEY_PATTERN)
    category_averages: List[CategoryAmountOut] = Field(
        description="Average per complete month for the largest categories (transaction_count = total in those months)."
    )
    current_month_pace: Optional[PaceOut]
    plan_adherence: AdherenceOut
    late_month_spending_share: Optional[str] = Field(
        description=(
            "Average share (%) of each complete month's spending recorded in its "
            "last 7 days. Null with fewer than 3 complete months that have spending."
        )
    )
    recurring_obligations: ClimateObligationsOut
    savings_goals: ClimateGoalsOut
    data_completeness: CompletenessOut
    notes: List[str]


# --- submit_feedback / set_usage_analytics ----------------------------------


class FeedbackSentOut(_Out):
    status: Literal["sent", "already_sent"]
    type: Literal["feature_request", "bug_report", "confusing", "praise", "other"]
    feature_area: Literal[
        "transactions", "budget", "history", "goals", "recurring", "setup", "other"
    ]
    rating: Optional[int]
    notes: List[str]


class UsageAnalyticsOut(_Out):
    usage_analytics_enabled: bool
    linked_data_deleted: bool = Field(
        description="True when turning it off deleted the usage records already linked to the user."
    )
    what_is_recorded: str


# --- get_calendar_month / show_financial_calendar ----------------------------

CalendarGroup = Literal["commitment", "set_aside", "everyday"]
DayKind = Literal["past", "today", "future"]
DayState = Literal["over", "within", "unplanned", "quiet", "planned", "free"]
BillState = Literal["paid", "overdue", "due_today", "upcoming", "later"]


class CalendarSummaryOut(_Out):
    stated_monthly_income: Optional[Money] = Field(
        description="Monthly income the user entered (self-reported); null when not stated.",
        pattern=MONEY_PATTERN,
    )
    total_planned: Optional[Money] = Field(
        description="The month's whole plan (get_budget_status total_planned). Null when MITA has no plan for the month.",
        pattern=MONEY_PATTERN,
    )
    commitments_planned: Optional[Money] = Field(
        description="Planned on bill lines: rent, mortgage and utilities, and the categories of the user's saved regular payments that belong to the month (counted as the reviewed budget counts obligations) — the lines whose unpaid part commitments_reserved holds.",
        pattern=MONEY_PATTERN,
    )
    set_aside_planned: Optional[Money] = Field(
        description="Planned for savings, savings goals and investments: never spendable.",
        pattern=MONEY_PATTERN,
    )
    everyday_planned: Optional[Money] = Field(
        description="Planned for everyday spending: total_planned minus commitments_planned minus set_aside_planned.",
        pattern=MONEY_PATTERN,
    )
    total_spent: Money = money_field("All recorded spending in the month.")
    commitments_spent: Money = money_field("Recorded spending on commitment lines.")
    everyday_spent: Money = money_field(
        "Recorded spending on every other line, including spending with no plan behind it."
    )
    total_remaining: Optional[Money] = Field(
        description="total_planned minus total_spent (the whole plan, money set aside included).",
        pattern=MONEY_PATTERN,
    )
    savings_set_aside: Optional[Money] = Field(
        description="get_budget_forecast savings_set_aside: money the plan still sets aside; not spendable.",
        pattern=MONEY_PATTERN,
    )
    left_to_spend: Optional[Money] = Field(
        description="total_remaining minus savings_set_aside minus commitments_reserved.",
        pattern=MONEY_PATTERN,
    )
    average_per_day: Optional[Money] = Field(
        description=(
            "get_budget_forecast safe_daily_limit: left_to_spend divided by days_remaining — one "
            "AVERAGE for each remaining day, not a budget for any particular date (each date's "
            "plan is in days[].planned). Null for a past month or without a plan."
        ),
        pattern=MONEY_PATTERN,
    )
    days_elapsed: int = Field(description="Days of the month begun (today counts).")
    days_remaining: int = Field(description="Days of the month after today.")
    commitments_reserved: Optional[Money] = Field(
        description=(
            "get_budget_forecast commitments_reserved: what the month's bills still need (each "
            "saved payment's due dates this month minus what the expenses linked to them paid; "
            "a rent / utilities line without a saved payment minus what is recorded on it). "
            "Kept out of left_to_spend and average_per_day until the bills are paid."
        ),
        pattern=MONEY_PATTERN,
    )
    planned_after_today: Optional[Money] = Field(
        description=(
            "The plan on the dates after today (every line except money set aside), as MITA's "
            "automatic rebalancing left it. It can be lower than left_to_spend: rebalancing takes "
            "money from later dates to cover a day that went over, while money left unspent on a "
            "past date stays on that date."
        ),
        pattern=MONEY_PATTERN,
    )
    flexible_left: Optional[Money] = Field(
        description="What the month's flexible budgets still hold (each line never below 0).",
        pattern=MONEY_PATTERN,
    )
    flexible_per_day: Optional[Money] = Field(
        description=(
            "The flexible budgets' guidance for each day left, today included (the sum "
            "of each flexible line's left_per_day), never more than average_per_day "
            "(never below 0): when spending elsewhere used money the envelopes still "
            "show, the safe average is the guide. Guidance for flexible spending, not "
            "cash on hand; null for a month without flexible budgets or one that ended."
        ),
        pattern=MONEY_PATTERN,
    )
    flexible_per_day_rounded: Optional[str] = Field(
        description="flexible_per_day in whole currency units, for a short summary.",
        pattern=r"^\d+$",
    )
    bills_due_after_today: Money = money_field(
        "Saved regular payments that fall due after today in this month, as scheduled (a bill already paid early is still counted here; see bills[].state)."
    )


class CalendarPurchaseOut(_Out):
    category: str = Field(description="The planned line's code.")
    date: dt.date = Field(description="The purchase date the plan holds money on.")
    planned: Money = money_field(
        "Money planned for the purchase (an allocation, not a transaction)."
    )
    spent: Money = money_field("Recorded on that line on that date.")
    proposed: bool = Field(
        description=(
            "True when MITA proposed this date (the user gave a frequency, e.g. "
            "'about once a week', but no day): say it is a proposed date, not one "
            "the user chose."
        )
    )


PaceStatus = Literal["not_started", "on_pace", "faster_than_pace", "over_limit"]

CalendarSpendingType = Literal[
    "obligation", "planned", "flexible", "set_aside", "legacy"
]


class CalendarLineOut(_Out):
    category: str = Field(
        description="Stored code of the budget line (as in get_budget_status)."
    )
    category_label: str = category_label_field()
    category_codes: List[str]
    group: CalendarGroup = Field(
        description="commitment, set_aside or everyday: every line is in exactly one group, so the groups add up to total_planned."
    )
    planned: Money = money_field("Planned for this line in the month.")
    spent: Money = money_field("Recorded on this line in the month.")
    remaining: Money = money_field("planned minus spent; negative means over.")
    source: Optional[LineSource] = Field(
        description=SOURCE_DESCRIPTION + " Null when nothing was planned on the line."
    )
    replaces: List[str] = Field(
        description="For a line the user set: MITA's own lines it takes the place of, as saved. Empty otherwise."
    )
    spending_type: CalendarSpendingType = Field(
        description=(
            "obligation: a saved regular payment, on its due dates; planned: "
            "purchases on known dates (purchases); flexible: a monthly limit with no "
            "purchase dates — its daily share is guidance, never a purchase; "
            "set_aside: savings; legacy: a month saved before MITA knew how the user "
            "buys (laid out by MITA's old pattern), or spending with no plan."
        )
    )
    pattern: Optional[str] = Field(
        description="For planned lines: how the user buys, in words, when it matches this month's dates."
    )
    purchases: List[CalendarPurchaseOut] = Field(
        description="For planned lines: every planned purchase of the month."
    )
    next_purchase: Optional[CalendarPurchaseOut] = Field(
        description="For planned lines: the first planned purchase from today on."
    )
    left_per_day: Optional[Money] = Field(
        description=(
            "For flexible lines of a month not ended: what is left on the line ÷ the "
            "days left (today included) — exact guidance, not a purchase."
        ),
        pattern=MONEY_PATTERN,
    )
    left_per_day_rounded: Optional[str] = Field(
        description="left_per_day in whole currency units, for a short summary ('about €4 a day').",
        pattern=r"^\d+$",
    )
    left_per_week: Optional[Money] = Field(
        description="For flexible lines: left_per_day × 7 (all that is left when under a week remains).",
        pattern=MONEY_PATTERN,
    )
    purchase_dates_stated: Optional[bool] = Field(
        description="For planned lines: false when MITA proposed the dates (no day named)."
    )
    pace_per_day: Optional[Money] = Field(
        description=(
            "For flexible lines: spent so far ÷ days elapsed (the forecast engine's "
            "pace). Compare with planned_per_day: the recommended pace, not a limit."
        ),
        pattern=MONEY_PATTERN,
    )
    planned_per_day: Optional[Money] = Field(
        description="For flexible lines: the month's amount ÷ the days of the month (recommended pace).",
        pattern=MONEY_PATTERN,
    )
    pace_status: Optional[PaceStatus] = Field(
        description=(
            "For flexible lines: not_started; on_pace; faster_than_pace (spending at "
            "least 1.2× the recommended pace — the forecast's at-risk rule: still "
            "within the monthly limit, but it would run out early); over_limit "
            "(beyond the month's amount). Spending fast is not overspending."
        )
    )
    days_until_exhausted: Optional[int] = Field(
        description="For flexible lines: days the rest lasts at the current pace (0 = used up); null before any spending."
    )


class CalendarDayOut(_Out):
    date: dt.date = Field(description="Local day in the user's timezone.")
    day_kind: DayKind = Field(description="Relative to the user's today.")
    state: DayState = Field(
        description=(
            "Begun days: over (everyday spending above that date's everyday plan), within, "
            "unplanned (spending on a date with no everyday plan; no verdict), quiet (nothing "
            "planned or spent). Future dates: planned or free (no everyday plan). Never a forecast."
        )
    )
    planned: Money = money_field(
        "The date's spending plan: every line except money set aside."
    )
    planned_everyday: Money = money_field("The everyday part of planned.")
    set_aside: Money = money_field(
        "Savings and goal slices planned on this date (not spendable)."
    )
    spent: Optional[Money] = Field(
        description="Recorded spending on this date; null for future dates.",
        pattern=MONEY_PATTERN,
    )
    spent_everyday: Optional[Money] = Field(
        description="The everyday part of spent; null for future dates.",
        pattern=MONEY_PATTERN,
    )
    everyday_left: Optional[Money] = Field(
        description="planned_everyday minus spent_everyday for a begun date with an everyday plan; negative means over.",
        pattern=MONEY_PATTERN,
    )
    planned_scheduled: Money = money_field(
        "The part of planned that is planned purchases and bills due (what is "
        "actually scheduled for the date)."
    )
    planned_flexible: Money = money_field(
        "The part of planned that is flexible budgets' daily share: guidance, never "
        "a purchase on this date."
    )
    purchases: List[CalendarPurchaseOut] = Field(
        description="Planned purchases on this date."
    )


class CalendarBillOut(_Out):
    date: dt.date = Field(
        description="Due date. The plan holds the bill's full amount on this date and nowhere else (until it is paid on another date)."
    )
    name: Optional[str] = Field(
        description="Name the user saved for this payment, if any."
    )
    obligation_ref: Optional[str] = Field(
        description=(
            "Opaque reference of this saved regular payment: pass it as "
            "obligation_ref when recording (add_transaction) or correcting "
            "(update_transaction) the expense that paid this due date."
        )
    )
    category: str
    category_label: str = category_label_field()
    amount: Money = money_field("Amount the user saved for this payment.")
    recurrence: Optional[Literal["monthly", "weekly"]] = Field(
        description="Repeat rule the user saved; null for a one-time payment."
    )
    in_plan: bool = Field(
        description="True when the month's plan holds money on this payment's line."
    )
    state: BillState = Field(
        description=(
            "Relative to the user's today: paid (expenses the user linked to this due "
            "date cover it), overdue (due date passed, not paid in MITA — MITA cannot "
            "know whether it was paid outside MITA), due_today, upcoming (due within "
            "reminder_days) or later."
        )
    )
    days_until: int = Field(
        description="Days from the user's today to the due date; negative once it has passed."
    )
    paid: Money = money_field(
        "What the expenses the user linked to this due date paid (whenever recorded). "
        "Spending in the same category never counts: a car part is not the car loan."
    )
    outstanding: Money = money_field("amount minus paid, never below 0.")
    paid_dates: List[dt.date] = Field(
        description="Dates the linked expenses were recorded on (one before the due date = paid early, after = late)."
    )
    reminder_from: dt.date = Field(
        description="First day of the bill's reminder window (reminder_days before its due date). A reminder only: no money is planned on those days for the bill."
    )


class CalendarMonthOut(_Out):
    year: int
    month: int
    month_position: MonthPosition
    currency: str
    timezone: str = Field(description="IANA timezone the dates are in.")
    today: dt.date = Field(description="The user's local today.")
    plan_status: PlanStatus
    method: str
    summary: CalendarSummaryOut
    categories: List[CalendarLineOut] = Field(
        description="The month's budget lines, largest plan first."
    )
    days: List[CalendarDayOut] = Field(description="Every date of the month, in order.")
    bills: List[CalendarBillOut] = Field(
        description="Dates the user's saved payments fall on this month, with their state."
    )
    reminders: List[CalendarBillOut] = Field(
        description=(
            "Bills to remind the user of now: due within reminder_days of today (this "
            "month or early next month), due today, or — for the current month — past due "
            "and not paid. Ordered by due date."
        )
    )
    reminder_days: int = Field(
        description="How many days before its due date a bill is announced (a reminder, not an allocation)."
    )
    notes: List[str]


class CalendarViewOut(_Out):
    year: int
    month: int
    month_position: MonthPosition
    currency: str
    plan_status: PlanStatus
    focus_date: Optional[dt.date] = Field(
        description="Date the calendar opens on, when one was asked for."
    )
    category: Optional[str] = Field(
        description="Budget line the calendar is filtered to, when one was asked for and found."
    )
    summary: CalendarSummaryOut
    reminders: List[CalendarBillOut] = Field(
        description="get_calendar_month reminders: bills due soon, due today or past due and not paid."
    )
    shown: str = Field(
        description="What the user now sees. The figures on screen are MITA's, not the arguments'."
    )
    notes: List[str]


# --- get_regional_context (2.8, Milestone 2) -----------------------------------

RegionalIndicator = Literal[
    "consumer_price_inflation",
    "consumer_price_inflation_annual",
    "price_level_index",
    "household_spending_share",
]
RegionalCategory = Literal[
    "all_items",
    "food",
    "clothing",
    "housing",
    "transport",
    "recreation",
    "restaurants",
]


class RegionalStatisticOut(_Out):
    indicator: RegionalIndicator
    indicator_label: str = Field(
        description="What the figure measures, in plain words."
    )
    category: RegionalCategory
    category_label: str = Field(description="The category as the provider names it.")
    value: str = Field(
        description=(
            "The figure exactly as published (in unit, never money): e.g. 6.0 for "
            "a 6.0 % annual rise, 59.1 for a price level at 59.1 % of the EU "
            "average, 246 for 246 per mille of household spending."
        )
    )
    display: str = Field(description="A short rendering with its unit, for a summary.")
    unit_kind: Literal["percent_change", "index", "price_level_index", "per_mille"]
    unit: str
    base_period: Optional[str] = Field(
        description="For an index: what equals 100 (e.g. EU27_2020=100)."
    )
    period: str = Field(description="The reference period: YYYY-MM or YYYY.")
    stale: bool = Field(
        description=(
            "True when the figure is older than its usual publication cycle allows. "
            "Say how old it is; never present it as current."
        )
    )
    quality_flags: List[str] = Field(
        description=(
            "estimated / provisional (the provider's own flag), revised, "
            "break_suspected, extreme_value. Mention estimated or provisional."
        )
    )
    geographic_scope: str = Field(description="Always a whole country.")
    source: str = Field(description="Attribution to show with the figure.")
    provider: Literal["eurostat", "worldbank", "oecd"]
    dataset: str
    source_url: str = Field(description="The official request MITA's copy came from.")
    published_at: Optional[dt.datetime] = Field(
        description="When the provider last updated the dataset, if it says."
    )
    retrieved_at: dt.datetime = Field(description="When MITA last confirmed the value.")
    license: str
    limitation: str = Field(description="What this figure is not. Say it.")


class RegionalContextOut(_Out):
    status: Literal["available", "no_country", "turned_off", "unavailable"] = Field(
        description=(
            "no_country: the user has not confirmed a country (ask, then "
            "update_financial_profile country). turned_off: the user turned "
            "regional statistics off. unavailable: MITA has no figures for that "
            "country yet — say so; never estimate one."
        )
    )
    country: Optional[str]
    country_name: Optional[str]
    statistics: List[RegionalStatisticOut]
    notes: List[str]
