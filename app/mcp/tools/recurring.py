from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.queries.recurring import recurring_expenses
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import RecurringOut
from app.mcp.serializers import recurring_out
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

DESCRIPTION = (
    "List recurring and upcoming expenses the user has confirmed in MITA: repeating "
    "expenses they scheduled (with the repeat rule and next due date), one-time "
    "expenses scheduled for the next 60 days, and transactions from the last 180 days "
    "that the user marked as recurring, grouped by merchant or category. MITA does not "
    "detect subscriptions automatically, so nothing here is guessed from merchant "
    "names. " + READ_ONLY_DISCLAIMER
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_recurring_expenses",
        title="Get recurring expenses",
        description=DESCRIPTION,
        annotations=read_only_annotations("Get recurring expenses"),
        meta=tool_meta(
            FINANCE_READ,
            "Reading your recurring expenses…",
            "Read your recurring expenses",
        ),
    )
    async def get_recurring_expenses() -> Annotated[CallToolResult, RecurringOut]:
        return await runtime.execute(
            "get_recurring_expenses",
            FINANCE_READ,
            lambda session, ctx: recurring_out(ctx, recurring_expenses(session, ctx)),
        )
