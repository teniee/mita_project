"""The service is ready only when every table it needs exists AND is granted.

``/health`` answers 503 until ``database_ready()`` is true, and Railway's
healthcheck is ``/health``: a deployment that reaches a database without its
migrations or its grants never becomes healthy, so the previous deployment
keeps serving (owner brief 2026-11-04: never run code whose migrations or
grants are missing). Connected as ``mita_mcp``, ``information_schema.tables``
lists only the tables the role holds a privilege on, so a missing grant
fails the same check (verified against a local server connected as
``mita_mcp``: revoking the ``spending_patterns`` grant turns ``/health`` 503).
"""

import re
from pathlib import Path

from app.mcp.__main__ import REQUIRED_TABLES

ROOT = Path(__file__).resolve().parents[1]


def granted_tables() -> set:
    sql = (ROOT / "scripts/mcp/mcp_service_role.sql").read_text()
    sql = re.sub(r"--[^\n]*", "", sql)
    tables = set()
    for match in re.finditer(r"GRANT\s+[^;]*?\s+ON\s+([^;]*?)\s+TO\s+mita_mcp", sql):
        target = " ".join(match.group(1).split())
        if target.upper().startswith(("SCHEMA ", "DATABASE ", "ALL ")):
            continue
        tables |= {name.strip() for name in target.split(",")}
    return tables


def test_the_2_7_tables_are_required():
    assert {
        "mcp_budget_lines",  # 0040
        "obligation_payments",  # 0041
        "spending_patterns",  # 0042
    } <= set(REQUIRED_TABLES)


def test_the_2_8_table_and_column_grants_are_required():
    """0043: setup answers are required; the confirmed country is written to
    ``users.country`` (and an app region of another country cleared), so the
    service role needs those two column grants — a missing one would surface
    only when a user confirms a country."""
    assert "mcp_setup_answers" in set(REQUIRED_TABLES)
    assert "mcp_setup_answers" in granted_tables()
    sql = re.sub(
        r"--[^\n]*", "", (ROOT / "scripts/mcp/mcp_service_role.sql").read_text()
    )
    update = re.search(r"GRANT UPDATE \(([^)]*)\)\s+ON users TO mita_mcp", sql)
    columns = {c.strip() for c in update.group(1).split(",")}
    assert {"country", "region"} <= columns


def test_every_required_table_is_granted_to_the_service_role():
    granted = granted_tables()
    assert "obligation_payments" in granted and "spending_patterns" in granted
    assert set(REQUIRED_TABLES) <= granted, set(REQUIRED_TABLES) - granted
