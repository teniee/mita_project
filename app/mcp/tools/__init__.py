"""MCP tool registration. One module per area."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.mcp.runtime import McpRuntime
from app.mcp.tools import budget, goals, profile, recurring, setup, transactions

READ_TOOLS = (
    "get_profile",
    "get_setup_status",
    "get_financial_summary",
    "list_transactions",
    "get_spending_breakdown",
    "get_budget_status",
    "get_budget_forecast",
    "get_recurring_expenses",
    "get_goals",
)

WRITE_TOOLS = (
    "update_financial_profile",
    "add_transaction",
    "add_transactions",
    "update_transaction",
    "delete_transaction",
)

PUBLISHED_TOOLS = READ_TOOLS + WRITE_TOOLS


def register_tools(server: MCPServer, runtime: McpRuntime) -> None:
    profile.register(server, runtime)
    setup.register(server, runtime)
    transactions.register(server, runtime)
    budget.register(server, runtime)
    recurring.register(server, runtime)
    goals.register(server, runtime)
