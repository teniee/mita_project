from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp_types import CallToolResult

from app.mcp.auth.scopes import PROFILE_READ
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import ProfileOut
from app.mcp.serializers import profile_out
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

DESCRIPTION = (
    "Identify the MITA account connected to this chat: a stable profile id, display "
    "name, masked e-mail, the currency MITA uses for this user's amounts, and the "
    "timezone MITA uses for days and months. Use it to confirm which account is "
    "connected or to learn the currency/timezone before interpreting other results. "
    "Returns no financial figures. " + READ_ONLY_DISCLAIMER
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_profile",
        title="Get MITA profile",
        description=DESCRIPTION,
        annotations=read_only_annotations("Get MITA profile"),
        meta=tool_meta(
            PROFILE_READ,
            "Checking your MITA account…",
            "Checked your MITA account",
            **{"openai/profile": True},
        ),
    )
    async def get_profile() -> Annotated[CallToolResult, ProfileOut]:
        return await runtime.execute(
            "get_profile", PROFILE_READ, lambda session, ctx: profile_out(ctx)
        )
