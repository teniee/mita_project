"""Read-only enforcement, public endpoints, and what the logs may contain."""

import json
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.models import Transaction
from app.mcp.observability import JsonFormatter
from tests_mcp.conftest import make_settings, structured


async def test_tool_session_refuses_writes(scopes, seed):
    """The scope every tool runs in cannot write, whatever the tool does."""
    read_scope, _ = scopes
    user = await seed.user()
    async with read_scope() as session:
        session.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=user.id,
                amount=Decimal("1.00"),
                category="food",
                spent_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(DBAPIError, match="read-only transaction"):
            await session.flush()


async def test_production_read_only_session_is_read_only(monkeypatch):
    """The real factory used in production, not the test double."""
    from app.mcp import db

    async with db.read_only_session() as session:
        mode = await session.scalar(text("SHOW transaction_read_only"))
        timeout = await session.scalar(text("SHOW statement_timeout"))
    assert mode == "on" and timeout == "5s"


async def test_reads_do_not_materialize_a_month(mcp, seed, connection):
    user = await seed.user()
    before = await connection.scalar(text("SELECT count(*) FROM daily_plan"))
    for tool in ("get_budget_status", "get_budget_forecast", "get_financial_summary"):
        assert not (await mcp.call(mcp.token(user), tool)).is_error
    assert await connection.scalar(text("SELECT count(*) FROM daily_plan")) == before


async def test_health(mcp):
    async with mcp.http() as http:
        response = await http.get("/health")
    assert response.status_code == 200 and response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


async def test_health_reports_unavailable_when_not_ready(make_service):
    from tests_mcp.conftest import http_client, started

    async def not_ready():
        return False

    from app.mcp.server import build_service

    service = make_service()
    service = build_service(
        make_settings(),
        session_scope=service.runtime.session_scope,
        readiness_check=not_ready,
    )
    async with started(service):
        async with http_client(service) as http:
            assert (await http.get("/health")).status_code == 503


async def test_openai_domain_challenge_returns_only_the_token(mcp):
    async with mcp.http() as http:
        response = await http.get("/.well-known/openai-apps-challenge")
    assert response.status_code == 200
    assert response.text == "challenge-token-123"
    assert response.headers["content-type"].startswith("text/plain")


async def test_domain_challenge_absent_until_configured(make_service):
    from tests_mcp.conftest import Harness

    harness = Harness(make_service, make_settings(apps_challenge_token=""))
    async with harness.http() as http:
        assert (await http.get("/.well-known/openai-apps-challenge")).status_code == 404


async def test_metrics_require_token_and_carry_no_identifiers(mcp, seed):
    user = await seed.user()
    await mcp.call(mcp.token(user), "get_profile")
    async with mcp.http() as http:
        assert (await http.get("/metrics")).status_code == 401
        response = await http.get(
            "/metrics", headers={"Authorization": "Bearer metrics-secret"}
        )
    assert response.status_code == 200
    assert 'mita_mcp_tool_calls_total{tool="get_profile",outcome="ok"}' in response.text
    assert str(user.id) not in response.text and user.email not in response.text


async def test_dns_rebinding_host_is_rejected(mcp, seed):
    user = await seed.user()
    async with mcp.http(mcp.token(user)) as http:
        response = await http.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={
                "Host": "attacker.example",
                "Accept": "application/json, text/event-stream",
            },
        )
    assert response.status_code in (400, 421)


async def test_logs_never_contain_tokens_amounts_or_pii(mcp, seed, caplog):
    user = await seed.user(name="Private Name")
    await seed.plan(user, date(2026, 3, 1), {"food": "123.45"})
    await seed.txn(
        user,
        "987.65",
        "food",
        datetime(2026, 3, 2, tzinfo=timezone.utc),
        merchant="Secret Merchant",
    )
    token = mcp.token(user)
    caplog.set_level(logging.DEBUG)
    m = mcp.at(datetime(2026, 3, 15, tzinfo=timezone.utc))
    for tool in (
        "list_transactions",
        "get_budget_status",
        "get_budget_forecast",
        "get_profile",
    ):
        await m.call(token, tool)
    await m.call(
        token,
        "list_transactions",
        {"start_date": "2026-03-10", "end_date": "2026-03-01"},
    )
    formatter = JsonFormatter()
    rendered = "\n".join(formatter.format(r) for r in caplog.records)
    for secret in (
        token,
        token.split(".")[1],
        user.email,
        "Private Name",
        "987.65",
        "123.45",
        "Secret Merchant",
        str(user.id),
    ):
        assert secret not in rendered, secret
    tool_lines = [
        json.loads(formatter.format(r))
        for r in caplog.records
        if r.getMessage() == "tool_call"
    ]
    assert {line["tool"] for line in tool_lines} >= {
        "list_transactions",
        "get_budget_status",
        "get_profile",
    }
    assert all(
        line["subject_hash"] and len(line["subject_hash"]) == 12 for line in tool_lines
    )
    assert any(line["outcome"] == "validation" for line in tool_lines)


async def test_internal_error_is_classified_and_not_echoed(mcp, seed, monkeypatch):
    from app.mcp.queries import ledger

    def boom(*args, **kwargs):
        raise RuntimeError("SELECT secret FROM users WHERE password='hunter2'")

    monkeypatch.setattr(ledger, "list_entries", boom)
    user = await seed.user()
    result = await mcp.call(mcp.token(user), "list_transactions")
    assert result.is_error
    assert result.structured_content["error"]["category"] == "internal"
    assert (
        "hunter2" not in result.content[0].text
        and "SELECT" not in result.content[0].text
    )


async def test_database_outage_is_unavailable_not_empty(mcp, seed, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.mcp.queries import plan

    def down(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(plan, "budget_status", down)
    user = await seed.user()
    result = await mcp.call(mcp.token(user), "get_budget_status")
    assert (
        result.is_error
        and result.structured_content["error"]["category"] == "unavailable"
    )


async def test_rate_limit_per_user(make_service, seed):
    from tests_mcp.conftest import Harness

    harness = Harness(make_service, make_settings(tool_calls_per_minute=2))
    user = await seed.user()
    token = harness.token(user)
    service = harness._build()
    from tests_mcp.conftest import mcp_client, started

    async with started(service):
        async with mcp_client(service, token) as client:
            assert not (await client.call_tool("get_profile", {})).is_error
            assert not (await client.call_tool("get_profile", {})).is_error
            third = await client.call_tool("get_profile", {})
    assert (
        third.is_error
        and third.structured_content["error"]["category"] == "rate_limited"
    )


async def test_structured_and_text_content_agree(mcp, seed):
    user = await seed.user()
    result = await mcp.call(mcp.token(user), "get_profile")
    assert json.loads(result.content[0].text) == structured(result)
