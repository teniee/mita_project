from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult

from app.mcp.auth.scopes import PROFILE_READ
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import ProfileOut
from app.mcp.serializers import profile_out
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta

DESCRIPTION = (
    "Identify the MITA account connected to this chat: a stable, opaque profile id, "
    "the display name (when the user set one) and a masked e-mail address. Use it to "
    "confirm which account is connected. Returns no financial figures; every MITA "
    "result with amounts names their currency, and get_setup_status shows the "
    "currency and timezone the user stated. " + READ_ONLY_DISCLAIMER
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
    async def get_profile(ctx: Context) -> Annotated[CallToolResult, ProfileOut]:
        return await runtime.execute(
            "get_profile",
            PROFILE_READ,
            lambda session, user_ctx: profile_out(user_ctx),
            ctx=ctx,
            intent="account",
        )
