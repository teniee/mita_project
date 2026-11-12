"""add_recurring_expense and create_savings_goal against the real database."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db.models import Goal
from app.mcp.idempotency import KEY_REUSED_MESSAGE
from app.services.core.engine.goal_budget_sync import (
    calculate_required_monthly_contribution,
)
from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)  # Sunday, 12:00 in Sofia


def new_key() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


@pytest.fixture
async def sofia(seed):
    return await seed.user(tz="Europe/Sofia", currency="EUR", name="Ana")


@pytest.fixture
async def bob(seed):
    return await seed.user(tz="UTC", currency="USD", name="Bob-the-other-user")


async def recur(m, token, **args):
    args.setdefault("idempotency_key", new_key())
    return await m.call(token, "add_recurring_expense", args)


async def goal(m, token, **args):
    args.setdefault("idempotency_key", new_key())
    return await m.call(token, "create_savings_goal", args)


async def scheduled_rows(connection, user):
    return (
        (
            await connection.execute(
                text(
                    "SELECT category, amount, merchant, recurrence, scheduled_date, status "
                    "FROM scheduled_expenses WHERE user_id = :u AND deleted_at IS NULL "
                    "ORDER BY created_at"
                ),
                {"u": user.id},
            )
        )
        .mappings()
        .all()
    )


async def goal_rows(connection, user):
    return (
        (
            await connection.execute(
                text(
                    "SELECT id, title, category, target_amount, saved_amount, target_date, "
                    "status, progress FROM goals WHERE user_id = :u ORDER BY created_at"
                ),
                {"u": user.id},
            )
        )
        .mappings()
        .all()
    )


# --- add_recurring_expense -------------------------------------------------------


async def test_rent_on_the_first_is_scheduled_for_the_next_first(m, sofia, connection):
    token = m.token(sofia)
    result = structured(
        await recur(
            m,
            token,
            name="Rent",
            amount=700,
            category="rent",
            recurrence="monthly",
            day_of_month=1,
        )
    )
    assert result == {
        "status": "created",
        "name": "Rent",
        "category": "rent",
        "category_label": "Rent",
        "amount": "700.00",
        "currency": "EUR",
        "recurrence": "monthly",
        "next_due_date": "2026-11-01",
        "notes": [],
    }
    (row,) = await scheduled_rows(connection, sofia)
    assert dict(row) == {
        "category": "rent",
        "amount": Decimal("700.00"),
        "merchant": "Rent",
        "recurrence": "monthly",
        "scheduled_date": date(2026, 11, 1),
        "status": "pending",
    }
    listed = structured(await m.call(token, "get_recurring_expenses", {}))
    assert [
        (s["merchant"], s["amount"], s["due_date"], s["recurrence"])
        for s in listed["scheduled_recurring"]
    ] == [("Rent", "700.00", "2026-11-01", "monthly")]
    assert listed["inferred"] == []  # confirmed by the user, nothing guessed
    status = structured(await m.call(token, "get_setup_status", {}))
    assert status["recurring_expense_count"] == 1


async def test_due_today_stays_today(m, sofia):
    result = structured(
        await recur(
            m,
            m.token(sofia),
            name="Phone",
            amount="19.99",
            category="utilities",
            recurrence="monthly",
            day_of_month=11,
        )
    )
    assert result["next_due_date"] == "2026-10-11"


async def test_day_31_in_a_short_month_uses_the_last_day(mcp, sofia):
    november = mcp.at(datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc))
    result = structured(
        await recur(
            november,
            november.token(sofia),
            name="Insurance",
            amount=40,
            category="insurance",
            recurrence="monthly",
            day_of_month=31,
        )
    )
    assert result["next_due_date"] == "2026-11-30"
    assert "no day 31" in result["notes"][0]


async def test_weekly_uses_the_next_named_weekday(m, sofia):
    result = structured(
        await recur(
            m,
            m.token(sofia),
            name="Gym",
            amount=25,
            category="other",
            recurrence="weekly",
            weekday="monday",
        )
    )
    today = date(2026, 10, 11)
    expected = today + timedelta(days=(0 - today.weekday()) % 7)
    assert expected.weekday() == 0
    assert result["next_due_date"] == expected.isoformat()


async def test_an_explicit_next_due_date_is_used_as_given(m, sofia):
    result = structured(
        await recur(
            m,
            m.token(sofia),
            name="Car loan",
            amount="250.00",
            category="other",
            recurrence="monthly",
            first_date="2026-10-20",
        )
    )
    assert result["next_due_date"] == "2026-10-20"


@pytest.mark.parametrize(
    "args,message",
    [
        ({"recurrence": "monthly"}, "does not guess due dates"),
        ({"recurrence": "weekly"}, "does not guess due dates"),
        (
            {"recurrence": "monthly", "first_date": "2026-10-01"},
            "cannot be in the past",
        ),
        ({"recurrence": "monthly", "first_date": "2028-01-01"}, "within the next year"),
        (
            {"recurrence": "monthly", "day_of_month": 1, "name": "   "},
            "must not be empty",
        ),
    ],
)
async def test_missing_or_invalid_due_information_is_refused(
    m, sofia, connection, args, message
):
    base = {"name": "Rent", "amount": 700, "category": "rent"}
    result = await recur(m, m.token(sofia), **{**base, **args})
    assert result.is_error and message in result.content[0].text
    assert await scheduled_rows(connection, sofia) == []


@pytest.mark.parametrize(
    "args",
    [
        {"amount": "100000.01"},
        {"amount": 0},
        {"category": "housing"},
        {"recurrence": "daily"},
        {"day_of_month": 32},
        {"weekday": "funday"},
        {"user_id": "x"},
    ],
)
async def test_schema_refuses_bad_values(m, sofia, connection, args):
    base = {
        "name": "Rent",
        "amount": 700,
        "category": "rent",
        "recurrence": "monthly",
        "day_of_month": 1,
    }
    result = await recur(m, m.token(sofia), **{**base, **args})
    assert result.is_error
    assert await scheduled_rows(connection, sofia) == []


async def test_recurring_retry_is_saved_once_and_key_reuse_is_refused(
    m, sofia, connection
):
    token = m.token(sofia)
    args = dict(
        name="Rent",
        amount=700,
        category="rent",
        recurrence="monthly",
        day_of_month=1,
        idempotency_key=new_key(),
    )
    first = structured(await recur(m, token, **args))
    again = structured(await recur(m, token, **args))
    assert (first["status"], again["status"]) == ("created", "already_created")
    assert len(await scheduled_rows(connection, sofia)) == 1
    other = await recur(m, token, **{**args, "amount": 701})
    assert other.is_error and KEY_REUSED_MESSAGE in other.content[0].text
    assert len(await scheduled_rows(connection, sofia)) == 1


async def test_a_similar_existing_obligation_is_reported_not_merged(
    m, sofia, connection
):
    token = m.token(sofia)
    args = dict(
        name="Rent", amount=700, category="rent", recurrence="monthly", day_of_month=1
    )
    await recur(m, token, **args)
    second = structured(await recur(m, token, **{**args, "name": "Rent (flat 2)"}))
    assert second["status"] == "created"
    assert "both are kept" in second["notes"][0]
    assert len(await scheduled_rows(connection, sofia)) == 2


async def test_recurring_name_is_kept_exactly(m, sofia, connection):
    result = structured(
        await recur(
            m,
            m.token(sofia),
            name="Наем — ап. 5 ☀",
            amount=700,
            category="rent",
            recurrence="monthly",
            day_of_month=1,
        )
    )
    assert result["name"] == "Наем — ап. 5 ☀"
    (row,) = await scheduled_rows(connection, sofia)
    assert row["merchant"] == "Наем — ап. 5 ☀"


async def test_due_date_follows_the_users_local_day(mcp, sofia):
    late = mcp.at(datetime(2026, 10, 31, 22, 30, tzinfo=timezone.utc))  # 1 Nov in Sofia
    result = structured(
        await recur(
            late,
            late.token(sofia),
            name="Rent",
            amount=700,
            category="rent",
            recurrence="monthly",
            day_of_month=1,
        )
    )
    assert result["next_due_date"] == "2026-11-01"


async def test_recurring_writes_are_isolated(m, sofia, bob, connection):
    await recur(
        m,
        m.token(sofia),
        name="Rent",
        amount=700,
        category="rent",
        recurrence="monthly",
        day_of_month=1,
    )
    assert await scheduled_rows(connection, bob) == []
    listed = structured(await m.call(m.token(bob), "get_recurring_expenses", {}))
    assert listed["scheduled_recurring"] == []


# --- create_savings_goal -----------------------------------------------------------


async def test_goal_is_created_with_exact_title_and_canonical_arithmetic(
    m, sofia, connection
):
    token = m.token(sofia)
    result = structured(
        await goal(
            m,
            token,
            title="Trip to Japan",
            target_amount=5000,
            target_date="2027-06-30",
        )
    )
    assert result["status"] == "created"
    assert (result["title"], result["target_amount"], result["saved_amount"]) == (
        "Trip to Japan",
        "5000.00",
        "0.00",
    )
    assert result["target_date"] == "2027-06-30" and result["category"] == "savings"
    expected = calculate_required_monthly_contribution(
        Goal(
            target_amount=Decimal("5000"),
            saved_amount=Decimal("0"),
            target_date=date(2027, 6, 30),
            status="active",
        ),
        date(2026, 10, 11),
    )
    assert result["required_monthly_contribution"] == str(expected)
    assert result["reserved_in_budget_plan"] is True

    (row,) = await goal_rows(connection, sofia)
    assert row["title"] == "Trip to Japan" and row["status"] == "active"
    assert row["target_amount"] == Decimal("5000.00") and row["saved_amount"] == 0
    reserved_days = (
        await connection.execute(
            text("SELECT count(*) FROM daily_plan WHERE goal_id = :g"), {"g": row["id"]}
        )
    ).scalar_one()
    assert reserved_days == 21  # 11..31 October

    listed = structured(await m.call(token, "get_goals", {}))
    assert [g["title"] for g in listed["goals"]] == ["Trip to Japan"]


@pytest.mark.parametrize("title", ["Отпуск в Гърция ✈️", "  New car  ", "x" * 200])
async def test_goal_title_is_kept_as_written(m, sofia, connection, title):
    result = structured(await goal(m, m.token(sofia), title=title, target_amount=100))
    assert result["title"] == title.strip()
    (row,) = await goal_rows(connection, sofia)
    assert row["title"] == title.strip()


async def test_goal_without_a_date_has_no_verdict_and_no_reservation(
    m, sofia, connection
):
    result = structured(
        await goal(
            m,
            m.token(sofia),
            title="Rainy day",
            target_amount="1500.00",
            already_saved=300,
        )
    )
    assert result["required_monthly_contribution"] is None
    assert result["reserved_in_budget_plan"] is False
    assert result["progress_percent"] == "20.0"
    (row,) = await goal_rows(connection, sofia)
    reserved = (
        await connection.execute(
            text("SELECT count(*) FROM daily_plan WHERE goal_id = :g"), {"g": row["id"]}
        )
    ).scalar_one()
    assert reserved == 0


async def test_a_second_dated_goal_is_saved_even_when_its_reservation_cannot_be(
    m, sofia, connection
):
    """Backend finding F-1: the API answers 500 after committing; here the goal
    is saved and the result says the reservation was not made."""
    token = m.token(sofia)
    first = structured(
        await goal(m, token, title="Car", target_amount=6000, target_date="2027-12-31")
    )
    second = structured(
        await goal(
            m, token, title="Laptop", target_amount=2000, target_date="2027-03-31"
        )
    )
    assert first["reserved_in_budget_plan"] is True
    assert second["status"] == "created" and second["reserved_in_budget_plan"] is False
    assert "could not set aside" in second["notes"][0]
    titles = [r["title"] for r in await goal_rows(connection, sofia)]
    assert titles == ["Car", "Laptop"]
    first_id = (await goal_rows(connection, sofia))[0]["id"]
    kept = (
        await connection.execute(
            text("SELECT count(*) FROM daily_plan WHERE goal_id = :g"), {"g": first_id}
        )
    ).scalar_one()
    assert kept == 21  # the first goal's reservation is untouched


@pytest.mark.parametrize(
    "args,message",
    [
        ({"target_date": "2026-10-11"}, "after today"),
        ({"already_saved": 600}, "cannot be more than"),
        ({"title": "Bad\x07title"}, "control characters"),
    ],
)
async def test_invalid_goal_requests_are_refused(m, sofia, connection, args, message):
    base = {"title": "Trip", "target_amount": 500}
    result = await goal(m, m.token(sofia), **{**base, **args})
    assert result.is_error and message in result.content[0].text
    assert await goal_rows(connection, sofia) == []


@pytest.mark.parametrize(
    "args",
    [
        {"target_amount": "0.99"},
        {"target_amount": "100000000.00"},
        {"category": "yacht"},
    ],
)
async def test_goal_schema_refuses_bad_values(m, sofia, connection, args):
    result = await goal(
        m, m.token(sofia), **{"title": "Trip", "target_amount": 500, **args}
    )
    assert result.is_error
    assert await goal_rows(connection, sofia) == []


async def test_goal_retry_is_created_once(m, sofia, connection):
    token = m.token(sofia)
    args = dict(
        title="Trip",
        target_amount=500,
        target_date="2027-01-31",
        idempotency_key=new_key(),
    )
    first = structured(await goal(m, token, **args))
    again = structured(await goal(m, token, **args))
    assert (first["status"], again["status"]) == ("created", "already_created")
    assert again["reserved_in_budget_plan"] is first["reserved_in_budget_plan"] is True
    assert len(await goal_rows(connection, sofia)) == 1


async def test_needed_amount_above_the_savings_target_is_stated_as_arithmetic(
    m, sofia, seed
):
    await seed.profile(sofia, savings_confirmed_at=NOW)
    await seed.connection.execute(
        text("UPDATE users SET savings_goal = 100 WHERE id = :u"), {"u": sofia.id}
    )
    result = structured(
        await goal(
            m,
            m.token(sofia),
            title="House",
            target_amount=20000,
            target_date="2027-10-31",
        )
    )
    assert result["notes"] and result["notes"][-1].startswith("Arithmetic:")
    assert "100.00" in result["notes"][-1]


async def test_goals_are_free_and_isolated(m, sofia, bob, analytics_sink):
    assert sofia.is_premium in (None, False)
    structured(await goal(m, m.token(sofia), title="Trip", target_amount=500))
    assert structured(await m.call(m.token(bob), "get_goals", {}))["goals"] == []
    created = [
        e for e in analytics_sink.events if e.event_name == "savings_goal_created"
    ]
    assert created and created[0].properties == {"has_target_date": False}
