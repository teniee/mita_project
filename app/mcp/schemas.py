"""Tool output models — published to ChatGPT as each tool's ``outputSchema``.

Money is a decimal string with exactly two fractional digits (``"1234.50"``),
never a float. Every response carries the currency the amounts are in. No
model contains an internal id, a timestamp of when the response was produced,
an email address or a free-text description the user typed.
"""

from __future__ import annotations

import datetime as dt
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Money = str  # validated by MONEY_PATTERN in tests_mcp; kept a plain alias for schema clarity
MONEY_PATTERN = r"^-?\d+\.\d{2}$"

PlanStatus = Literal["generated", "not_generated"]
MonthPosition = Literal["past", "current", "future"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


def money_field(description: str) -> object:
    return Field(description=description, pattern=MONEY_PATTERN)


# --- get_profile -----------------------------------------------------------


class ProfileOut(_Out):
    id: str = Field(
        description="Stable, opaque identifier of this MITA profile (not the account's database id)."
    )
    name: Optional[str] = Field(
        description="Display name the user set in MITA, if any."
    )
    nickname: str = Field(description="Masked e-mail address, to tell accounts apart.")
    currency: str = Field(
        description="ISO 4217 code MITA uses for this user's amounts."
    )
    timezone: str = Field(
        description="IANA timezone MITA uses for this user's days and months."
    )
    has_completed_onboarding: bool


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
            "MITA's category name, as recorded (for example 'subscriptions'). Report "
            "it under this name; do not rename it or merge it with other categories."
        )
    )
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
    category: str
    planned: Money = money_field("Budget allocated to this category for the month.")
    spent: Money = money_field("Recorded spending in this category this month.")
    remaining: Money = money_field("planned minus spent; negative means over budget.")
    percent_used: Optional[str] = Field(
        description="spent / planned × 100, one decimal place. Null when nothing was planned.",
        pattern=r"^\d+\.\d$",
    )
    state: Literal["within_budget", "over_budget", "unplanned_spending", "not_started"]


class DayBudgetOut(_Out):
    date: dt.date
    planned: Money = money_field("Sum of today's category allocations.")
    spent: Money = money_field("Recorded spending today.")
    remaining: Money = money_field("planned minus spent for today.")


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
    category: str
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
        description="on_track: projected balance ≥ 0; warning: projected overspend under 10% of plan; danger: 10% or more; no_data: month not started or nothing planned. Null without a plan."
    )
    method: str
    days_in_month: int
    days_elapsed: int
    days_remaining: int
    total_planned: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    total_spent: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    remaining_budget: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    current_daily_pace: Optional[Money] = Field(default=None, pattern=MONEY_PATTERN)
    safe_daily_limit: Optional[Money] = Field(
        default=None,
        description="remaining_budget / days_remaining. Negative when the month's plan is already exceeded.",
        pattern=MONEY_PATTERN,
    )
    projected_month_end_spend: Optional[Money] = Field(
        default=None, pattern=MONEY_PATTERN
    )
    projected_month_end_balance: Optional[Money] = Field(
        default=None, pattern=MONEY_PATTERN
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


class ScheduledExpenseOut(_Out):
    category: str
    amount: Money = money_field("Scheduled amount.")
    merchant: Optional[str]
    due_date: dt.date = Field(
        description="Next date the user scheduled this expense for."
    )
    recurrence: Optional[str] = Field(
        description="Repeat rule the user set, e.g. 'monthly'; null for one-time."
    )


class MarkedRecurringOut(_Out):
    label: str = Field(description="Merchant if recorded, otherwise the category.")
    category: str
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
    suggested_next_step: Literal[
        "complete_profile", "build_budget", "record_expenses", "ready"
    ]
    known: KnownProfileOut = Field(
        description="Values MITA already has. Do not ask the user for these again."
    )
    notes: List[str]


class ProfileUpdateOut(_Out):
    status: Literal["updated", "unchanged"]
    updated_fields: List[ProfileField]
    profile: KnownProfileOut
    profile_complete: bool
    missing_fields: List[ProfileField]
    notes: List[str]


# --- add_transaction(s) / update_transaction / delete_transaction ----------


class RecordedTransactionOut(_Out):
    ref: str = Field(description=REF_DESCRIPTION)
    date: dt.date = Field(description="Local calendar day of the expense.")
    amount: Money = money_field("Amount recorded.")
    currency: str
    category: str
    merchant: Optional[str] = Field(description="Merchant exactly as recorded.")


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


TransactionField = Literal["amount", "category", "date", "merchant"]


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
            "current month's plan."
        )
    )
    notes: List[str]
