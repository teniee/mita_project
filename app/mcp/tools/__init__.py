"""MCP tool registration. One module per area."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.mcp.runtime import McpRuntime
from app.mcp.tools import (
    budget,
    feedback,
    goals,
    history,
    profile,
    recurring,
    setup,
    transactions,
)

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
    "get_spending_history",
    "get_financial_climate",
    "preview_monthly_budget",
)

WRITE_TOOLS = (
    "update_financial_profile",
    "add_transaction",
    "add_transactions",
    "update_transaction",
    "delete_transaction",
    "add_recurring_expense",
    "create_savings_goal",
    "save_monthly_budget",
    "submit_feedback",
    "set_usage_analytics",
)

PUBLISHED_TOOLS = READ_TOOLS + WRITE_TOOLS


def register_tools(server: MCPServer, runtime: McpRuntime) -> None:
    profile.register(server, runtime)
    setup.register(server, runtime)
    transactions.register(server, runtime)
    budget.register(server, runtime)
    recurring.register(server, runtime)
    goals.register(server, runtime)
    history.register(server, runtime)
    feedback.register(server, runtime)
