"""User A can never read User B — by token, by argument, or by guessing."""

from datetime import date, datetime, timezone

import pytest

from tests_mcp.conftest import structured

NOW = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
B_MARKERS = ("777.77", "B-ONLY-MERCHANT", "B secret goal", "888.88", "B-SCHEDULED")

ALL_CALLS = [
    ("get_profile", {}),
    ("get_financial_summary", {}),
    ("list_transactions", {"start_date": "2026-03-01", "end_date": "2026-03-31"}),
    ("get_spending_breakdown", {"start_date": "2026-03-01", "end_date": "2026-03-31"}),
    ("get_budget_status", {}),
    ("get_budget_forecast", {}),
    ("get_recurring_expenses", {}),
    ("get_goals", {"status": "all"}),
]


@pytest.fixture
async def two_users(seed):
    a = await seed.user(name="Alice")
    b = await seed.user(name="Bob-the-other-user")
    await seed.plan(a, date(2026, 3, 1), {"food": "100.00"})
    await seed.txn(
        a, "10.00", "food", datetime(2026, 3, 2, tzinfo=timezone.utc), merchant="A-shop"
    )
    await seed.plan(b, date(2026, 3, 1), {"food": "888.88"})
    await seed.txn(
        b,
        "777.77",
        "food",
        datetime(2026, 3, 2, tzinfo=timezone.utc),
        merchant="B-ONLY-MERCHANT",
    )
    await seed.goal(b, title="B secret goal", target_amount=5000)
    await seed.scheduled(b, merchant="B-SCHEDULED", scheduled_date=date(2026, 3, 20))
    return a, b


@pytest.mark.parametrize("tool,args", ALL_CALLS)
async def test_a_never_sees_b(mcp, two_users, tool, args):
    a, b = two_users
    text = (await mcp.at(NOW).call(mcp.token(a), tool, args)).content[0].text
    for marker in B_MARKERS + ("Bob-the-other-user", str(b.id), b.email):
        assert marker not in text, (tool, marker)


@pytest.mark.parametrize("tool,args", ALL_CALLS)
@pytest.mark.parametrize("field", ["user_id", "userId", "account_id", "email", "owner"])
async def test_smuggled_identity_argument_gives_nothing(
    mcp, two_users, tool, args, field
):
    a, b = two_users
    value = b.email if field == "email" else str(b.id)
    result = await mcp.at(NOW).call(mcp.token(a), tool, {**args, field: value})
    text = result.content[0].text
    for marker in B_MARKERS + (str(b.id), "Bob-the-other-user"):
        assert marker not in text, (tool, field, marker)


async def test_token_for_b_reads_b_only(mcp, two_users):
    a, b = two_users
    data = structured(await mcp.at(NOW).call(mcp.token(b), "get_budget_status"))
    assert data["total_planned"] == "888.88" and data["total_spent"] == "777.77"
    assert "A-shop" not in str(data)


async def test_forged_subject_without_signature_is_rejected(mcp, two_users):
    """Changing `sub` in A's token to B's id breaks the signature."""
    import base64
    import json

    a, b = two_users
    header, payload, sig = mcp.token(a).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["sub"] = str(b.id)
    tampered = (
        base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    )
    async with mcp.http(f"{header}.{tampered}.{sig}") as http:
        response = await http.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert response.status_code == 401
