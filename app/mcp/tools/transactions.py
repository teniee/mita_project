from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.queries import ledger
from app.mcp.queries.periods import resolve_date_range
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import SpendingBreakdownOut, TransactionsOut
from app.mcp.serializers import spending_breakdown_out, transactions_out
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

StartDate = Annotated[
    Optional[date],
    Field(
        description="First local day to include (YYYY-MM-DD). Defaults to 29 days before end_date."
    ),
]
EndDate = Annotated[
    Optional[date],
    Field(
        description="Last local day to include (YYYY-MM-DD). Defaults to today in the user's timezone."
    ),
]

LIST_DESCRIPTION = (
    "List the user's recorded expenses in MITA for a date range, newest first. Each "
    "item has the local date, amount, currency, category and merchant (when the user "
    "recorded one); free-text notes, receipts and locations are never returned. "
    "Optional filters: category (exact, e.g. 'groceries') and merchant (case-insensitive "
    "contains). Dates are calendar days in the user's timezone; the range may span at "
    "most 366 days. Returns at most `limit` items plus the count and total of ALL "
    "matching expenses, so totals stay correct when has_more is true. Deleted "
    "transactions are excluded. MITA records expenses only (no income or account "
    "balances). " + READ_ONLY_DISCLAIMER
)

BREAKDOWN_DESCRIPTION = (
    "Total the user's recorded MITA expenses by category for a date range: per-category "
    "total, transaction count and share of all spending, largest first, plus the overall "
    "total. Use it for 'where did my money go' questions. Dates are calendar days in the "
    "user's timezone (default: the last 30 days, at most 366). Deleted transactions are "
    "excluded. It reports what was spent, not what was budgeted — use get_budget_status "
    "for the plan. " + READ_ONLY_DISCLAIMER
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="list_transactions",
        title="List MITA transactions",
        description=LIST_DESCRIPTION,
        annotations=read_only_annotations("List MITA transactions"),
        meta=tool_meta(
            FINANCE_READ, "Reading your transactions…", "Read your transactions"
        ),
    )
    async def list_transactions(
        start_date: StartDate = None,
        end_date: EndDate = None,
        category: Annotated[
            Optional[str],
            Field(
                description="Only this MITA category, e.g. 'groceries', 'dining', 'rent', 'transportation'.",
                min_length=1,
                max_length=50,
                pattern=r"^[A-Za-z][A-Za-z_ &-]*$",
            ),
        ] = None,
        merchant: Annotated[
            Optional[str],
            Field(
                description="Only merchants whose name contains this text (case-insensitive).",
                min_length=1,
                max_length=100,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum transactions to return (1-200).", ge=1, le=200),
        ] = 50,
    ) -> Annotated[CallToolResult, TransactionsOut]:
        def body(session, ctx):
            start, end = resolve_date_range(ctx, start_date, end_date)
            page = ledger.list_entries(
                session,
                ctx,
                start,
                end,
                category=category.strip().lower() if category else None,
                merchant=merchant.strip() if merchant else None,
                limit=limit,
            )
            return transactions_out(ctx, start, end, page)

        return await runtime.execute("list_transactions", FINANCE_READ, body)

    @server.tool(
        name="get_spending_breakdown",
        title="Get spending by category",
        description=BREAKDOWN_DESCRIPTION,
        annotations=read_only_annotations("Get spending by category"),
        meta=tool_meta(
            FINANCE_READ, "Totalling your spending…", "Totalled your spending"
        ),
    )
    async def get_spending_breakdown(
        start_date: StartDate = None,
        end_date: EndDate = None,
    ) -> Annotated[CallToolResult, SpendingBreakdownOut]:
        def body(session, ctx):
            start, end = resolve_date_range(ctx, start_date, end_date)
            totals = ledger.totals_by_category(session, ctx, start, end)
            others = ledger.other_currencies_in_range(session, ctx, start, end)
            return spending_breakdown_out(ctx, start, end, totals, others)

        return await runtime.execute("get_spending_breakdown", FINANCE_READ, body)
