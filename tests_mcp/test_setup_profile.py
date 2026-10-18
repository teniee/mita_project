"""get_setup_status and update_financial_profile against the real database."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
async def newcomer(seed):
    """An account as the ChatGPT sign-up creates it: API defaults, nothing stated."""
    return await seed.user(income="0", onboarded=False, name=None)


async def _profile_row(connection, user):
    return (
        (
            await connection.execute(
                text("SELECT * FROM mcp_user_profiles WHERE user_id = :u"),
                {"u": user.id},
            )
        )
        .mappings()
        .first()
    )


async def _user_row(connection, user):
    return (
        (
            await connection.execute(
                text(
                    "SELECT monthly_income, savings_goal, currency, timezone, has_onboarded "
                    "FROM users WHERE id = :u"
                ),
                {"u": user.id},
            )
        )
        .mappings()
        .first()
    )


async def test_conversational_profile_is_saved_and_survives_a_new_session(
    mcp, newcomer, connection, analytics_sink
):
    token = mcp.token(newcomer)
    result = structured(
        await mcp.at(NOW).call(
            token,
            "update_financial_profile",
            {
                "monthly_net_income": 2500,
                "currency": "eur",
                "timezone": "Europe/Sofia",
                "household_size": 2,
                "monthly_savings_target": "400.00",
            },
        )
    )
    assert result["status"] == "updated"
    assert result["updated_fields"] == [
        "monthly_net_income",
        "currency",
        "timezone",
        "household_size",
        "monthly_savings_target",
    ]
    assert result["profile"] == {
        "monthly_net_income": "2500.00",
        "currency": "EUR",
        "timezone": "Europe/Sofia",
        "household_size": 2,
        "monthly_savings_target": "400.00",
    }
    assert result["profile_complete"] is True and result["missing_fields"] == []
    # Real ChatGPT built a final-looking budget before rent was known: the
    # result now says to ask about regular payments first (never mandatory).
    assert result["suggested_next_step"] == "ask_about_obligations"
    assert any("No regular payments are saved yet" in n for n in result["notes"])

    row = await _user_row(connection, newcomer)
    assert row["monthly_income"] == Decimal("2500.00")
    assert row["savings_goal"] == Decimal("400.00")
    assert (row["currency"], row["timezone"]) == ("EUR", "Europe/Sofia")
    profile = await _profile_row(connection, newcomer)
    assert profile["household_size"] == 2
    assert all(
        profile[f"{f}_confirmed_at"] is not None
        for f in ("income", "currency", "timezone", "savings")
    )

    # A different conversation = a new token, nothing carried in ChatGPT memory.
    fresh = mcp.token(newcomer)
    status = structured(await mcp.at(NOW).call(fresh, "get_setup_status"))
    assert status["profile_complete"] is True
    assert status["missing_fields"] == []
    assert status["known"]["monthly_net_income"] == "2500.00"
    assert status["suggested_next_step"] == "ask_about_obligations"
    created = [
        e for e in analytics_sink.events if e.event_name == "financial_profile_created"
    ]
    assert created and created[0].properties["fields"] == sorted(
        result["updated_fields"]
    )


async def test_partial_update_keeps_the_rest_and_resending_is_unchanged(mcp, newcomer):
    token = mcp.token(newcomer)
    await mcp.call(token, "update_financial_profile", {"monthly_net_income": "1800.50"})
    second = structured(
        await mcp.call(token, "update_financial_profile", {"household_size": 3})
    )
    assert second["profile"]["monthly_net_income"] == "1800.50"
    assert second["profile"]["household_size"] == 3
    assert second["missing_fields"] == [
        "currency",
        "timezone",
        "monthly_savings_target",
    ]
    again = structured(
        await mcp.call(token, "update_financial_profile", {"household_size": 3})
    )
    assert again["status"] == "unchanged" and again["updated_fields"] == []


async def test_confirming_a_value_equal_to_the_default_counts(mcp, newcomer):
    """A user who really is on UTC/USD must be able to say so."""
    result = structured(
        await mcp.call(
            mcp.token(newcomer),
            "update_financial_profile",
            {"currency": "USD", "timezone": "UTC"},
        )
    )
    assert result["status"] == "updated"
    assert set(result["updated_fields"]) == {"currency", "timezone"}
    assert "currency" not in result["missing_fields"]


@pytest.mark.parametrize(
    "args,message",
    [
        ({}, "at least one field"),
        ({"timezone": "Mars/Olympus"}, "IANA timezone"),
        (
            {"monthly_net_income": 1000, "monthly_savings_target": 1500},
            "cannot be more",
        ),
    ],
)
async def test_invalid_profile_updates_are_refused(
    mcp, newcomer, connection, args, message
):
    result = await mcp.call(mcp.token(newcomer), "update_financial_profile", args)
    assert result.is_error
    assert message in result.content[0].text
    assert await _profile_row(connection, newcomer) is None  # nothing written


@pytest.mark.parametrize(
    "args",
    [
        {"monthly_net_income": "12.345"},
        {"monthly_net_income": "NaN"},
        {"monthly_net_income": -5},
        {"monthly_net_income": True},
        {"currency": "EURO"},
        {"household_size": 0},
        {"household_size": 21},
        {"monthly_savings_target": "Infinity"},
    ],
)
async def test_malformed_values_fail_schema_validation(mcp, newcomer, args):
    result = await mcp.call(mcp.token(newcomer), "update_financial_profile", args)
    assert result.is_error


async def test_currency_cannot_change_once_expenses_exist(mcp, seed, connection):
    user = await seed.user(currency="EUR")
    await seed.txn(user, "10.00", "groceries", NOW)
    result = await mcp.call(
        mcp.token(user), "update_financial_profile", {"currency": "USD"}
    )
    assert result.is_error and "does not convert" in result.content[0].text
    assert (await _user_row(connection, user))["currency"] == "EUR"
    same = await mcp.call(
        mcp.token(user), "update_financial_profile", {"currency": "EUR"}
    )
    assert not same.is_error


async def test_app_onboarded_user_is_not_asked_again(mcp, seed):
    user = await seed.user(tz="Europe/Sofia", currency="EUR", income="4200.00")
    status = structured(await mcp.at(NOW).call(mcp.token(user), "get_setup_status"))
    assert status["income_set"] and status["currency_set"] and status["timezone_set"]
    assert status["known"]["monthly_net_income"] == "4200.00"
    assert status["missing_fields"] == ["household_size", "monthly_savings_target"]


async def test_setup_status_counts_real_records(mcp, seed):
    user = await seed.user(tz="Europe/Sofia")
    await seed.txn(
        user, "5.00", "groceries", datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
    )
    await seed.txn(
        user, "6.00", "groceries", datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
    )
    await seed.txn(user, "7.00", "groceries", NOW, deleted=True)
    await seed.scheduled(user, recurrence="monthly")
    await seed.scheduled(user, recurrence="once")
    await seed.goal(user)
    await seed.plan(user, date(2026, 10, 1), {"groceries": "300.00"})
    status = structured(await mcp.at(NOW).call(mcp.token(user), "get_setup_status"))
    assert status["transaction_count"] == 2  # the deleted one is not counted
    assert status["months_of_history"] == 2
    assert status["recurring_expense_count"] == 1  # "once" is not recurring
    assert status["savings_goal_count"] == 1
    assert status["monthly_plan_exists"] is True
    assert status["current_month"] == "2026-10"


async def test_profile_writes_are_isolated(mcp, seed, connection):
    alice = await seed.user(income="0", onboarded=False)
    bob = await seed.user(income="3333.00", currency="BGN")
    await mcp.call(
        mcp.token(alice), "update_financial_profile", {"monthly_net_income": 999}
    )
    bob_row = await _user_row(connection, bob)
    assert bob_row["monthly_income"] == Decimal("3333.00")
    assert bob_row["currency"] == "BGN"
    assert await _profile_row(connection, bob) is None


async def test_profile_update_needs_the_write_scope(mcp, newcomer):
    token = mcp.token(newcomer, scopes=["profile:read", "finance:read"])
    result = await mcp.call(token, "update_financial_profile", {"household_size": 2})
    assert result.is_error
    assert result.structured_content["error"]["category"] == "forbidden"
    challenge = result.meta["mcp/www_authenticate"][0]
    assert 'error="insufficient_scope"' in challenge and "finance:write" in challenge
