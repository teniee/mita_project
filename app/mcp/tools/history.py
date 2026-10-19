"""Six-month spending history and the financial climate (read-only)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, List, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.categories import label as category_label
from app.mcp.errors import ValidationError
from app.mcp.queries import budget_draft, history
from app.mcp.queries.periods import month_days
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import (
    AdherenceOut,
    CategoryAmountOut,
    CategoryTrendOut,
    ClimateGoalsOut,
    ClimateObligationsOut,
    CompletenessOut,
    FinancialClimateOut,
    HistoryMonthOut,
    PaceOut,
    SpendingHistoryOut,
    TrendOut,
)
from app.mcp.serializers import money, optional_money
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

DEFAULT_MONTHS = 6
ZERO = Decimal("0.00")

NOTE_ZERO_MONTH = (
    "A month with 0 transactions means nothing was recorded in MITA that month, "
    "not necessarily that nothing was spent."
)
NOTE_BEFORE_TRACKING = (
    "Months marked before_tracking come before the user's first recorded expense; "
    "MITA has no data for them."
)

HISTORY_DESCRIPTION = (
    "Spending history by calendar month from the user's persisted MITA records — "
    "for 'how has my spending changed', 'compare this month with last month' or "
    "'how have my grocery costs changed over six months'. Default: the last 6 "
    "months including the current one (up to 12). Each month has its total, count "
    "and per-category totals (or only the requested category) and a status that "
    "separates 'no data yet' from 'nothing recorded'. Adds averages and medians "
    "over complete months, the largest category, and a trend (latest complete "
    "month vs the earlier ones) only when at least 3 complete months exist — "
    "otherwise insufficient_data. Months follow the user's timezone. "
    + READ_ONLY_DISCLAIMER
)

CLIMATE_DESCRIPTION = (
    "A compact, factual picture of the user's last months in MITA (default 6): "
    "average and median monthly spending, the largest categories' monthly "
    "averages, this month's spending so far versus earlier months by the same "
    "day, how many months stayed within a saved plan, the share of spending in "
    "the last 7 days of a month, this month's recurring obligations and savings "
    "goal totals, with data completeness. Use it for 'how am I doing overall' or "
    "a big-picture overview; for month-by-month figures use get_spending_history. "
    "It states numbers, not judgments. " + READ_ONLY_DISCLAIMER
)


def _end_month(ctx, end_month: Optional[str]):
    current = (ctx.today.year, ctx.today.month)
    if end_month is None:
        return current
    try:
        key = tuple(int(part) for part in end_month.split("-"))
        date(key[0], key[1], 1)
    except (ValueError, IndexError):
        raise ValidationError("end_month must be written YYYY-MM.") from None
    if key > current:
        raise ValidationError("end_month cannot be in the future.")
    if key < (2000, 1):
        raise ValidationError("end_month is too far in the past.")
    return key


def _categories_out(categories) -> List[CategoryAmountOut]:
    ordered = sorted(categories.items(), key=lambda kv: (-kv[1][0], kv[0]))
    return [
        CategoryAmountOut(
            category=name,
            category_label=category_label(name),
            total=money(total),
            transaction_count=count,
        )
        for name, (total, count) in ordered
    ]


def _trend_out(trend: history.Trend) -> TrendOut:
    if trend.status != "ok":
        return TrendOut(status="insufficient_data")
    return TrendOut(
        status="ok",
        latest_month=trend.latest_month,
        latest_total=money(trend.latest_total),
        earlier_average=money(trend.earlier_average),
        change_percent=(
            None if trend.change_percent is None else str(trend.change_percent)
        ),
        direction=trend.direction,
    )


def history_out(ctx, record: history.History) -> SpendingHistoryOut:
    months = record.months
    totals = record.category_totals()
    largest = None
    if totals:
        name, total = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        count = sum(m.categories.get(name, (ZERO, 0))[1] for m in months)
        largest = CategoryAmountOut(
            category=name,
            category_label=category_label(name),
            total=money(total),
            transaction_count=count,
        )
    category_trends: List[CategoryTrendOut] = []
    if record.category is None:
        for name, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[
            : history.TOP_CATEGORY_TRENDS
        ]:
            category_trends.append(
                CategoryTrendOut(
                    category=name,
                    category_label=category_label(name),
                    trend=_trend_out(record.trend(name)),
                )
            )
    notes: List[str] = []
    if any(m.status == "recorded" and m.transaction_count == 0 for m in months):
        notes.append(NOTE_ZERO_MONTH)
    if any(m.status == "before_tracking" for m in months):
        notes.append(NOTE_BEFORE_TRACKING)
    if record.first_recorded is None:
        notes.append("No expenses are recorded in MITA yet.")
    current = record.in_progress
    first_day = date(*months[0].key, 1)
    last_day = ctx.today if current is not None else month_days(*months[-1].key)[1]
    return SpendingHistoryOut(
        period_start=first_day,
        period_end=last_day,
        currency=ctx.currency,
        timezone=ctx.timezone,
        category=record.category,
        category_label=(
            category_label(record.category) if record.category is not None else None
        ),
        months_requested=len(months),
        months_with_data=record.months_with_data,
        complete_months=len(record.complete),
        months=[
            HistoryMonthOut(
                month=m.label,
                status=m.status,
                transaction_count=m.transaction_count,
                total_spent=money(m.total),
                categories=_categories_out(m.categories),
            )
            for m in months
        ],
        average_monthly_spending=optional_money(record.average()),
        median_monthly_spending=optional_money(record.median()),
        current_month_to_date=money(current.total) if current else None,
        largest_category=largest,
        trend=_trend_out(record.trend(record.category)),
        category_trends=category_trends,
        notes=notes,
    )


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_spending_history",
        title="Get spending history",
        description=HISTORY_DESCRIPTION,
        annotations=read_only_annotations("Get spending history"),
        meta=tool_meta(
            FINANCE_READ, "Reading your spending history…", "Read your spending history"
        ),
    )
    async def get_spending_history(
        ctx: Context,
        months: Annotated[
            int,
            Field(
                ge=1,
                le=12,
                description="How many months, ending with end_month (default 6).",
            ),
        ] = DEFAULT_MONTHS,
        category: Annotated[
            Optional[str],
            Field(
                min_length=1,
                max_length=50,
                pattern=r"^[A-Za-z][A-Za-z_ &-]*$",
                description="Only this MITA category, e.g. 'groceries'.",
            ),
        ] = None,
        end_month: Annotated[
            Optional[str],
            Field(
                pattern=r"^\d{4}-\d{2}$",
                description="Last month of the window, YYYY-MM (default: this month).",
            ),
        ] = None,
    ) -> Annotated[CallToolResult, SpendingHistoryOut]:
        def body(session, user_ctx):
            keys = history.window(user_ctx, months, _end_month(user_ctx, end_month))
            cat = category.strip().lower() if category else None
            return history_out(
                user_ctx,
                history.spending_history(session, user_ctx, keys, category=cat),
            )

        if category:
            intent = "category_trend"
        elif months <= 2:
            intent = "compare_periods"
        else:
            intent = "six_month_overview"
        return await runtime.execute(
            "get_spending_history", FINANCE_READ, body, ctx=ctx, intent=intent
        )

    @server.tool(
        name="get_financial_climate",
        title="Get financial overview",
        description=CLIMATE_DESCRIPTION,
        annotations=read_only_annotations("Get financial overview"),
        meta=tool_meta(
            FINANCE_READ, "Reviewing your recent months…", "Reviewed your recent months"
        ),
    )
    async def get_financial_climate(
        ctx: Context,
        months: Annotated[
            int,
            Field(
                ge=3,
                le=12,
                description="How many months including this one (default 6).",
            ),
        ] = DEFAULT_MONTHS,
    ) -> Annotated[CallToolResult, FinancialClimateOut]:
        def body(session, user_ctx):
            keys = history.window(user_ctx, months)
            obligations = budget_draft.obligations_for_month(
                session, user_ctx, user_ctx.today.year, user_ctx.today.month
            )
            result = history.climate(
                session,
                user_ctx,
                keys,
                (len(obligations), sum((o.amount for o in obligations), ZERO)),
            )
            return climate_out(user_ctx, result)

        return await runtime.execute(
            "get_financial_climate",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="six_month_overview",
        )


def climate_out(ctx, result: history.Climate) -> FinancialClimateOut:
    record = result.history
    complete = record.complete
    averages: List[CategoryAmountOut] = []
    if complete:
        sums = {}
        for month in complete:
            for name, (total, count) in month.categories.items():
                prev_total, prev_count = sums.get(name, (ZERO, 0))
                sums[name] = (prev_total + total, prev_count + count)
        for name, (total, count) in sorted(
            sums.items(), key=lambda kv: (-kv[1][0], kv[0])
        )[: history.TOP_CATEGORY_TRENDS]:
            averages.append(
                CategoryAmountOut(
                    category=name,
                    category_label=category_label(name),
                    total=money(total / len(complete)),
                    transaction_count=count,
                )
            )
    pace = None
    if result.pace is not None:
        pace = PaceOut(
            day_of_month=result.pace.day_of_month,
            spent_to_date=money(result.pace.spent_to_date),
            prior_average_to_same_day=optional_money(
                result.pace.prior_average_to_same_day
            ),
            months_compared=result.pace.months_compared,
        )
    notes: List[str] = []
    if record.first_recorded is None:
        notes.append(
            "No expenses are recorded in MITA yet, so there is no history to describe."
        )
    elif len(complete) < history.MIN_MONTHS_FOR_TREND:
        notes.append(
            f"Only {len(complete)} complete month(s) are recorded; patterns that need "
            f"{history.MIN_MONTHS_FOR_TREND} are reported as unavailable."
        )
    months = record.months
    return FinancialClimateOut(
        period_start=date(*months[0].key, 1),
        period_end=ctx.today,
        currency=ctx.currency,
        months_with_data=record.months_with_data,
        total_transactions=sum(m.transaction_count for m in months),
        average_monthly_spending=optional_money(record.average()),
        median_monthly_spending=optional_money(record.median()),
        category_averages=averages,
        current_month_pace=pace,
        plan_adherence=AdherenceOut(
            months_with_plan=result.adherence.months_with_plan,
            months_within_plan=result.adherence.months_within_plan,
            months_over_plan=result.adherence.months_over_plan,
        ),
        late_month_spending_share=(
            None if result.late_month_share is None else str(result.late_month_share)
        ),
        recurring_obligations=ClimateObligationsOut(
            count=result.obligations_count,
            current_month_total=money(result.obligations_total),
        ),
        savings_goals=ClimateGoalsOut(
            active_count=result.goals.active_count,
            total_target=money(result.goals.total_target),
            total_saved=money(result.goals.total_saved),
        ),
        data_completeness=CompletenessOut(
            complete_months=len(complete),
            months_before_tracking=sum(
                1 for m in months if m.status == "before_tracking"
            ),
            in_progress_month=record.in_progress is not None,
        ),
        notes=notes,
    )
