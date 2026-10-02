"""Query-layer dataclasses → tool output models.

The only place amounts are formatted. Every field a tool returns is listed
here explicitly; nothing is copied from an ORM object wholesale.
"""

from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional, Sequence

from app.mcp.queries.goals import GoalView
from app.mcp.queries.ledger import CategoryTotal, LedgerPage
from app.mcp.queries.periods import UserContext, days_elapsed, month_days
from app.mcp.queries.plan import BudgetStatus, MonthForecast
from app.mcp.queries.recurring import RecurringView
from app.mcp.schemas import (
    BudgetStatusOut,
    CategoryBudgetOut,
    CategoryRiskOut,
    CategorySpendOut,
    DayBudgetOut,
    FinancialSummaryOut,
    ForecastOut,
    GoalOut,
    GoalProjectionOut,
    GoalsOut,
    MarkedRecurringOut,
    ProfileOut,
    RecurringOut,
    ScheduledExpenseOut,
    SpendingBreakdownOut,
    TransactionOut,
    TransactionsOut,
)

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
ZERO = Decimal("0.00")
PROFILE_ID_NAMESPACE = "mita-profile-v1:"

NOTE_NO_CONVERSION = (
    "All totals are in {currency}. MITA does not convert currencies; "
    "transactions recorded in {others} are added at face value."
)
NOTE_PLAN_NOT_GENERATED = (
    "MITA has not generated a budget plan for this month yet. Plans are created "
    "in the MITA app (during onboarding, and for later months when the user "
    "opens the app). No budget figures are estimated here."
)
NOTE_NOT_ONBOARDED = (
    "This account has not completed MITA onboarding, so it has no budget plan."
)


def money(value: Decimal) -> str:
    return str(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def optional_money(value: Optional[Decimal]) -> Optional[str]:
    return None if value is None else money(value)


def percent(part: Decimal, whole: Decimal) -> str:
    return str(
        (Decimal(part) / Decimal(whole) * 100).quantize(TENTH, rounding=ROUND_HALF_UP)
    )


def profile_id(user_id) -> str:
    """Stable, opaque, never reassigned: a one-way digest of the account uuid."""
    digest = hashlib.sha256(f"{PROFILE_ID_NAMESPACE}{user_id}".encode()).hexdigest()
    return f"prf_{digest[:16]}"


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    if not domain:
        return "***"
    visible = local[:1] if len(local) <= 3 else local[:2]
    return f"{visible}***@{domain}"


def _currency_notes(ctx: UserContext, others: Sequence[str]) -> List[str]:
    if not others:
        return []
    return [NOTE_NO_CONVERSION.format(currency=ctx.currency, others=", ".join(others))]


def _plan_notes(ctx: UserContext, plan_generated: bool) -> List[str]:
    if plan_generated:
        return []
    return [NOTE_PLAN_NOT_GENERATED if ctx.has_onboarded else NOTE_NOT_ONBOARDED]


def profile_out(ctx: UserContext) -> ProfileOut:
    return ProfileOut(
        id=profile_id(ctx.user_id),
        name=ctx.name,
        nickname=mask_email(ctx.email),
        currency=ctx.currency,
        timezone=ctx.timezone,
        has_completed_onboarding=ctx.has_onboarded,
    )


def transactions_out(ctx: UserContext, start, end, page: LedgerPage) -> TransactionsOut:
    return TransactionsOut(
        start_date=start,
        end_date=end,
        currency=ctx.currency,
        transactions=[
            TransactionOut(
                date=e.day,
                amount=money(e.amount),
                currency=e.currency,
                category=e.category,
                merchant=e.merchant,
            )
            for e in page.entries
        ],
        returned_count=len(page.entries),
        matching_count=page.matching_count,
        matching_total=money(page.matching_total),
        has_more=page.has_more,
        notes=_currency_notes(ctx, page.other_currencies),
    )


def _category_spend(
    items: Sequence[CategoryTotal], grand_total: Decimal
) -> List[CategorySpendOut]:
    return [
        CategorySpendOut(
            category=item.category,
            total=money(item.total),
            transaction_count=item.count,
            share_percent=(
                percent(item.total, grand_total) if grand_total > 0 else "0.0"
            ),
        )
        for item in items
    ]


def spending_breakdown_out(
    ctx: UserContext, start, end, totals: Sequence[CategoryTotal], others: Sequence[str]
) -> SpendingBreakdownOut:
    grand_total = sum((t.total for t in totals), ZERO)
    return SpendingBreakdownOut(
        start_date=start,
        end_date=end,
        currency=ctx.currency,
        total_spent=money(grand_total),
        transaction_count=sum(t.count for t in totals),
        categories=_category_spend(totals, grand_total),
        notes=_currency_notes(ctx, others),
    )


def financial_summary_out(
    ctx: UserContext, status: BudgetStatus, totals: Sequence[CategoryTotal]
) -> FinancialSummaryOut:
    _, last = month_days(status.year, status.month)
    elapsed = days_elapsed(ctx, status.year, status.month)
    spent = sum((t.total for t in totals), ZERO)
    planned = status.total_planned if status.plan_generated else None
    return FinancialSummaryOut(
        year=status.year,
        month=status.month,
        month_position=status.position,  # type: ignore[arg-type]
        currency=ctx.currency,
        stated_monthly_income=optional_money(ctx.stated_monthly_income),
        plan_status="generated" if status.plan_generated else "not_generated",
        planned_total=optional_money(planned),
        spent_total=money(spent),
        remaining_total=optional_money(
            planned - spent if planned is not None else None
        ),
        transaction_count=sum(t.count for t in totals),
        top_categories=_category_spend(list(totals)[:3], spent),
        days_in_month=last.day,
        days_elapsed=elapsed,
        notes=_plan_notes(ctx, status.plan_generated)
        + _currency_notes(ctx, status.other_currencies),
    )


def _category_state(planned: Decimal, spent: Decimal) -> str:
    if planned > 0:
        return "over_budget" if spent > planned else "within_budget"
    return "unplanned_spending" if spent > 0 else "not_started"


def budget_status_out(ctx: UserContext, status: BudgetStatus) -> BudgetStatusOut:
    today = None
    if status.today is not None:
        today = DayBudgetOut(
            date=status.today.day,
            planned=money(status.today.planned),
            spent=money(status.today.spent),
            remaining=money(status.today.planned - status.today.spent),
        )
    return BudgetStatusOut(
        year=status.year,
        month=status.month,
        month_position=status.position,  # type: ignore[arg-type]
        currency=ctx.currency,
        plan_status="generated" if status.plan_generated else "not_generated",
        total_planned=money(status.total_planned),
        total_spent=money(status.total_spent),
        total_remaining=money(status.total_planned - status.total_spent),
        categories=[
            CategoryBudgetOut(
                category=c.category,
                planned=money(c.planned),
                spent=money(c.spent),
                remaining=money(c.remaining),
                percent_used=percent(c.spent, c.planned) if c.planned > 0 else None,
                state=_category_state(c.planned, c.spent),  # type: ignore[arg-type]
            )
            for c in status.categories
        ],
        today=today,
        notes=_plan_notes(ctx, status.plan_generated)
        + _currency_notes(ctx, status.other_currencies),
    )


FORECAST_METHOD = (
    "Linear projection from MITA's forecast engine: spent so far divided by days "
    "elapsed (in the user's timezone), extended over the rest of the month, compared "
    "with the month's plan. It does not include scheduled future expenses."
)


def forecast_out(
    ctx: UserContext, forecast: MonthForecast, others: Sequence[str]
) -> ForecastOut:
    _, last = month_days(forecast.year, forecast.month)
    result = forecast.result
    common = dict(
        year=forecast.year,
        month=forecast.month,
        month_position=forecast.position,
        currency=ctx.currency,
        method=FORECAST_METHOD,
        days_in_month=last.day,
    )
    if result is None:
        elapsed = days_elapsed(ctx, forecast.year, forecast.month)
        return ForecastOut(
            **common,
            plan_status="not_generated",
            status=None,
            days_elapsed=elapsed,
            # Same convention as compute_forecast: today counts as elapsed.
            days_remaining=last.day - elapsed,
            categories_at_risk=[],
            notes=_plan_notes(ctx, False) + _currency_notes(ctx, others),
        )
    return ForecastOut(
        **common,
        plan_status="generated",
        status=result.status,
        days_elapsed=result.days_elapsed,
        days_remaining=result.days_remaining,
        total_planned=money(result.total_planned),
        total_spent=money(result.total_spent),
        remaining_budget=money(result.remaining_budget),
        current_daily_pace=money(result.current_daily_pace),
        safe_daily_limit=money(result.safe_daily_limit),
        projected_month_end_spend=money(result.projected_month_end_spend),
        projected_month_end_balance=money(result.projected_month_end_balance),
        categories_at_risk=[
            CategoryRiskOut(
                category=c.category,
                monthly_planned=money(c.monthly_planned),
                monthly_spent=money(c.monthly_spent),
                daily_pace=money(c.daily_pace),
                planned_per_day=money(c.planned_per_day),
                pace_ratio=money(c.overspend_ratio),
                days_until_exhausted=c.days_until_exhausted,
            )
            for c in result.categories_at_risk
        ],
        notes=_currency_notes(ctx, others),
    )


def _goal_projection(goal: GoalView) -> Optional[GoalProjectionOut]:
    f = goal.forecast
    if f is None:
        return None
    if f.remaining <= 0:
        basis = "funded"
        on_track: Optional[bool] = True
    elif f.target_date is None:
        # The engine reports on_track=False here; with no deadline there is
        # nothing to be on or off track against.
        basis = "no_target_date"
        on_track = None
    elif f.months_remaining is not None and f.months_remaining <= 0:
        basis = "target_date_passed"
        on_track = False
    else:
        basis = "monthly_contribution"
        on_track = f.on_track
    return GoalProjectionOut(
        basis=basis,  # type: ignore[arg-type]
        on_track=on_track,
        months_remaining=(
            None if f.months_remaining is None else money(f.months_remaining)
        ),
        required_monthly_contribution=optional_money(f.required_monthly_contribution),
        projected_saved_by_target_date=optional_money(f.projected_saved),
        shortfall=optional_money(f.shortfall) if basis != "no_target_date" else None,
    )


def goals_out(ctx: UserContext, goals: Sequence[GoalView]) -> GoalsOut:
    items = []
    for g in goals:
        remaining = max(g.target_amount - g.saved_amount, ZERO)
        progress = (
            min(Decimal(g.saved_amount) / g.target_amount * 100, Decimal(100))
            if g.target_amount > 0
            else Decimal(0)
        )
        items.append(
            GoalOut(
                title=g.title,
                category=g.category,
                status=g.status,  # type: ignore[arg-type]
                priority=g.priority,
                target_amount=money(g.target_amount),
                saved_amount=money(g.saved_amount),
                remaining_amount=money(remaining),
                progress_percent=str(progress.quantize(TENTH, rounding=ROUND_HALF_UP)),
                monthly_contribution=optional_money(g.monthly_contribution),
                target_date=g.target_date,
                projection=_goal_projection(g),
            )
        )
    notes = []
    if any(
        g.status == "active" and g.monthly_contribution is None and g.target_date
        for g in goals
    ):
        notes.append(
            "Goals without a monthly contribution are projected with a contribution of 0."
        )
    return GoalsOut(currency=ctx.currency, goals=items, notes=notes)


def recurring_out(ctx: UserContext, view: RecurringView) -> RecurringOut:
    def scheduled(item) -> ScheduledExpenseOut:
        return ScheduledExpenseOut(
            category=item.category,
            amount=money(item.amount),
            merchant=item.merchant,
            due_date=item.next_date,
            recurrence=item.recurrence,
        )

    return RecurringOut(
        currency=ctx.currency,
        scheduled_recurring=[scheduled(i) for i in view.scheduled_recurring],
        upcoming_one_time=[scheduled(i) for i in view.upcoming_one_time],
        marked_recurring=[
            MarkedRecurringOut(
                label=m.label,
                category=m.category,
                last_amount=money(m.last_amount),
                last_date=m.last_date,
                occurrences_in_lookback=m.occurrences,
            )
            for m in view.marked_recurring
        ],
        lookback_start_date=view.lookback_start,
        inferred=[],
        notes=[
            "Only expenses the user scheduled or marked as recurring are listed. "
            "MITA does not detect subscriptions automatically."
        ],
    )
