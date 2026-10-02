from __future__ import annotations

from typing import Annotated, Optional

from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.queries import ledger, plan
from app.mcp.queries.periods import month_days, resolve_month
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import BudgetStatusOut, FinancialSummaryOut, ForecastOut
from app.mcp.serializers import budget_status_out, financial_summary_out, forecast_out
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

Year = Annotated[
    Optional[int],
    Field(
        description="Calendar year. Give with month; omit both for the current month.",
        ge=2000,
        le=2100,
    ),
]
Month = Annotated[
    Optional[int],
    Field(
        description="Calendar month 1-12. Give with year; omit both for the current month.",
        ge=1,
        le=12,
    ),
]

PLAN_NOTE = (
    "If MITA has not generated a plan for the month, plan_status is 'not_generated' and "
    "no budget figure is estimated."
)

SUMMARY_DESCRIPTION = (
    "One-month overview of the user's MITA finances: the monthly income the user "
    "entered (self-reported, may be null), the month's total budget plan, total "
    "recorded spending, what remains of the plan, the transaction count and the top "
    "three spending categories. Months follow the user's timezone; default is the "
    "current month. " + PLAN_NOTE + " " + READ_ONLY_DISCLAIMER
)

STATUS_DESCRIPTION = (
    "Budget vs. actual for one month, per category: planned amount, spent, remaining, "
    "percent used and a state (within_budget, over_budget, unplanned_spending, "
    "not_started), plus today's planned/spent/remaining for the current month. "
    "Allocations are MITA's persisted daily plan (including any automatic "
    "redistribution MITA already applied); spending is the user's recorded expenses. "
    + PLAN_NOTE
    + " "
    + READ_ONLY_DISCLAIMER
)

FORECAST_DESCRIPTION = (
    "Project where the user's budget lands at month end at the current pace, using "
    "MITA's forecast engine: daily pace so far, safe daily amount for the remaining "
    "days, projected month-end spend and balance, a status (on_track / warning / "
    "danger / no_data) and the categories spending 1.2× faster than planned. It is a "
    "linear projection, not a prediction of specific purchases, and does not include "
    "scheduled future expenses. " + PLAN_NOTE + " " + READ_ONLY_DISCLAIMER
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_financial_summary",
        title="Get monthly financial summary",
        description=SUMMARY_DESCRIPTION,
        annotations=read_only_annotations("Get monthly financial summary"),
        meta=tool_meta(
            FINANCE_READ, "Summarizing your month…", "Summarized your month"
        ),
    )
    async def get_financial_summary(
        year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, FinancialSummaryOut]:
        def body(session, ctx):
            y, m = resolve_month(ctx, year, month)
            status = plan.budget_status(session, ctx, y, m)
            first, last = month_days(y, m)
            totals = ledger.totals_by_category(session, ctx, first, last)
            return financial_summary_out(ctx, status, totals)

        return await runtime.execute("get_financial_summary", FINANCE_READ, body)

    @server.tool(
        name="get_budget_status",
        title="Get budget status",
        description=STATUS_DESCRIPTION,
        annotations=read_only_annotations("Get budget status"),
        meta=tool_meta(FINANCE_READ, "Checking your budget…", "Checked your budget"),
    )
    async def get_budget_status(
        year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, BudgetStatusOut]:
        def body(session, ctx):
            y, m = resolve_month(ctx, year, month)
            return budget_status_out(ctx, plan.budget_status(session, ctx, y, m))

        return await runtime.execute("get_budget_status", FINANCE_READ, body)

    @server.tool(
        name="get_budget_forecast",
        title="Get month-end budget forecast",
        description=FORECAST_DESCRIPTION,
        annotations=read_only_annotations("Get month-end budget forecast"),
        meta=tool_meta(FINANCE_READ, "Projecting your month…", "Projected your month"),
    )
    async def get_budget_forecast(
        year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, ForecastOut]:
        def body(session, ctx):
            y, m = resolve_month(ctx, year, month)
            forecast = plan.month_forecast(session, ctx, y, m)
            first, last = month_days(y, m)
            others = ledger.other_currencies_in_range(session, ctx, first, last)
            return forecast_out(ctx, forecast, others)

        return await runtime.execute("get_budget_forecast", FINANCE_READ, body)
