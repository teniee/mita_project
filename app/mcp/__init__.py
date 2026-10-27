"""MITA ChatGPT app (MCP server).

A separate deployable service (``python -m app.mcp``) that reuses the MITA
domain layer directly. See ``docs/adr/ADR-chatgpt-mcp-app.md``.
"""

MCP_SERVER_NAME = "mita-finance"
MCP_SERVER_VERSION = "2.3.0"
# serverInfo.description; equals the plugin listing's description (tested), so a
# client that shows server details describes the read/write app accurately.
MCP_SERVER_DESCRIPTION = (
    "Your MITA budget in ChatGPT: record and correct expenses, build a monthly "
    "budget, track recurring costs and savings goals, and see your spending "
    "history - kept in your MITA account."
)
