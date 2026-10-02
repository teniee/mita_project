from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.queries.goals import list_goals
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import GoalsOut
from app.mcp.serializers import goals_out
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

DESCRIPTION = (
    "List the user's MITA savings goals with target, amount saved, remaining amount, "
    "progress and target date. For active goals it adds a deterministic projection: "
    "whether saved + monthly contribution × months left reaches the target by the "
    "target date, the monthly amount that would be required, and any shortfall. Goals "
    "without a target date get no on-track verdict. By default only active goals are "
    "returned. " + READ_ONLY_DISCLAIMER
)

STATUS_SETS = {
    "active": ("active",),
    "all": ("active", "paused", "completed", "cancelled"),
    "completed": ("completed",),
}


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_goals",
        title="Get savings goals",
        description=DESCRIPTION,
        annotations=read_only_annotations("Get savings goals"),
        meta=tool_meta(FINANCE_READ, "Reading your goals…", "Read your goals"),
    )
    async def get_goals(
        status: Annotated[
            Literal["active", "completed", "all"],
            Field(description="Which goals to return. Default: active."),
        ] = "active",
    ) -> Annotated[CallToolResult, GoalsOut]:
        def body(session, ctx):
            return goals_out(ctx, list_goals(session, ctx, STATUS_SETS[status]))

        return await runtime.execute("get_goals", FINANCE_READ, body)
