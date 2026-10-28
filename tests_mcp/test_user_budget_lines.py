"""F-11 in ChatGPT: budget lines the user names and sets themselves.

"Fuel €200", "Cigarettes €200", "Cat food €60": ChatGPT passes the user's own
name and amount; MITA keeps the amount exactly as a line of the user's
("my:<label>"), allocates only the money left to its own lines (minus the ones
the user's line replaces), and never needs a category list to know what the
words mean. Driven through the real tools, as a conversation would.
"""

import base64
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.financial_constants import FinancialConstants
from app.mcp.tools.inputs import EXPENSE_CATEGORIES
from app.mcp.writes.budget import CHANGED_DRAFT, INVALID_DRAFT
from app.services.monthly_plan_service import allocations_from_profile
from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)  # 12:00 in Sofia
D = Decimal


def new_key() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


async def seed_person(m, seed):
    """Income 2000, savings 500 and rent 340 stated in ChatGPT. MITA's own
    allocation for this profile has Fuel ('transport gas') at 90.00."""
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    structured(
        await m.call(
            token,
            "update_financial_profile",
            {
                "monthly_net_income": 2000,
                "currency": "EUR",
                "timezone": "Europe/Sofia",
                "monthly_savings_target": 500,
            },
        )
    )
    structured(
        await m.call(
            token,
            "add_recurring_expense",
            {
                "name": "Rent",
                "amount": 340,
                "category": "rent",
                "recurrence": "monthly",
                "day_of_month": 1,
                "idempotency_key": new_key(),
            },
        )
    )
    return user


@pytest.fixture
async def person(m, seed):
    return await seed_person(m, seed)


async def plan_totals(connection, user):
    rows = (
        await connection.execute(
            text(
                "SELECT category, planned_amount FROM daily_plan "
                "WHERE user_id = :u AND goal_id IS NULL"
            ),
            {"u": user.id},
        )
    ).all()
    totals = defaultdict(Decimal)
    for category, amount in rows:
        totals[category] += D(str(amount))
    return dict(totals)


async def stored_lines(connection, user):
    rows = (
        await connection.execute(
            text("SELECT line_key, replaces FROM mcp_budget_lines WHERE user_id = :u"),
            {"u": user.id},
        )
    ).all()
    return {key: list(replaces) for key, replaces in rows}


def by_source(preview, source):
    return {
        a["category"]: a["amount"]
        for a in preview["category_allocations"]
        if a["source"] == source
    }


def engine(lines, replaced=()):
    return allocations_from_profile(
        monthly_income=D("2000"),
        savings_goal=D("500"),
        region="ZZ",
        fixed_expenses={"rent": D("340")},
        manual_allocations=lines,
        replaced_buckets=replaced,
    )


async def preview(m, token, **arguments):
    return structured(await m.call(token, "preview_monthly_budget", arguments))


async def save(m, token, draft):
    return structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
        )
    )


FUEL = {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}


async def test_fuel_200_is_kept_exactly_and_takes_mitas_fuel_line(
    m, person, connection
):
    token = m.token(person)
    automatic = await preview(m, token)
    assert by_source(automatic, "calculated_by_mita")["transport gas"] == "90.00"

    draft = await preview(m, token, budget_lines=[FUEL])
    fuel = [a for a in draft["category_allocations"] if a["category"] == "my:Fuel"]
    assert fuel == [
        {
            "category": "my:Fuel",
            "category_label": "Fuel",
            "amount": "200.00",
            "layout": "spread",
            "source": "set_by_you",
            "replaces": ["transport gas"],
        }
    ]
    mita = by_source(draft, "calculated_by_mita")
    assert "transport gas" not in mita  # MITA's own Fuel is not budgeted twice
    expected = engine({"my:Fuel": D("200")}, {"transport gas"})
    assert {c: D(a) for c, a in mita.items()} == expected.discretionary
    assert draft["user_set_total"] == "200.00"
    assert await plan_totals(connection, person) == {}  # a preview writes nothing


async def test_cigarettes_need_no_category_of_their_own(m, person):
    draft = await preview(
        m, m.token(person), budget_lines=[{"label": "Cigarettes", "amount": 200}]
    )
    assert by_source(draft, "set_by_you") == {"my:Cigarettes": "200.00"}
    # Nothing was added to MITA's taxonomy for it.
    assert "tobacco" not in FinancialConstants.VALID_TRANSACTION_CATEGORIES
    assert "tobacco" not in EXPENSE_CATEGORIES
    # Nothing of MITA's is replaced; its own lines share what is left
    # (2000 - 340 - 500 - 200 = 960), scaled down only if they do not fit.
    mita = by_source(draft, "calculated_by_mita")
    assert "transport gas" in mita
    expected = engine({"my:Cigarettes": D("200")})
    assert {c: D(a) for c, a in mita.items()} == expected.discretionary
    assert sum(D(a) for a in mita.values()) <= D("960.00")


async def test_any_name_the_user_uses_is_a_line(m, person):
    draft = await preview(
        m,
        m.token(person),
        budget_lines=[
            {"label": "Food for my cat", "amount": "60"},
            {"label": "Cosmetologist", "amount": "80.50"},
            {"label": "Steam games", "amount": 50},
        ],
    )
    assert by_source(draft, "set_by_you") == {
        "my:Cosmetologist": "80.50",
        "my:Food for my cat": "60.00",
        "my:Steam games": "50.00",
    }
    labels = {a["category"]: a["category_label"] for a in draft["category_allocations"]}
    assert labels["my:Food for my cat"] == "Food for my cat"


async def test_mixed_user_lines_exact_and_mita_uses_the_rest(m, person):
    lines = [
        FUEL,
        {"label": "Cigarettes", "amount": 200},
        {"label": "Groceries", "amount": 50, "replaces": ["groceries"]},
    ]
    draft = await preview(m, m.token(person), budget_lines=lines)
    assert by_source(draft, "set_by_you") == {
        "my:Fuel": "200.00",
        "my:Cigarettes": "200.00",
        "my:Groceries": "50.00",
    }
    # 2000 - 340 rent - 500 savings - 450 of the user's = 710 for MITA's lines.
    assert draft["flexible_total"] == "710.00"
    expected = engine(
        {"my:Fuel": D(200), "my:Cigarettes": D(200), "my:Groceries": D(50)},
        {"transport gas", "groceries"},
    )
    mita = by_source(draft, "calculated_by_mita")
    assert {c: D(a) for c, a in mita.items()} == expected.discretionary
    # Savings count once: the parts add up to the income, to the cent.
    parts = (
        D(draft["fixed_obligations_total"])
        + D(draft["savings_allocation"])
        + sum(D(a["amount"]) for a in draft["category_allocations"])
        + D(draft["unallocated"])
    )
    assert parts == D("2000.00")


async def test_saved_lines_persist_into_a_new_conversation(m, mcp, person, connection):
    token = m.token(person)
    draft = await preview(
        m, token, budget_lines=[FUEL, {"label": "Cigarettes", "amount": 200}]
    )
    saved = await save(m, token, draft)
    assert saved["status"] == "saved"
    assert saved["set_by_you"] == [
        {
            "category": "my:Cigarettes",
            "category_label": "Cigarettes",
            "amount": "200.00",
        },
        {"category": "my:Fuel", "category_label": "Fuel", "amount": "200.00"},
    ]
    totals = await plan_totals(connection, person)
    assert totals["my:Fuel"] == D("200.00") and totals["my:Cigarettes"] == D("200.00")
    assert "transport gas" not in totals
    assert await stored_lines(connection, person) == {
        "my:Fuel": ["transport gas"],
        "my:Cigarettes": [],
    }

    later = mcp.at(datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc))
    fresh = later.token(person)
    status = structured(await later.call(fresh, "get_budget_status", {}))
    lines = {c["category"]: c for c in status["categories"]}
    assert lines["my:Fuel"]["planned"] == "200.00"
    assert lines["my:Fuel"]["source"] == "set_by_you"
    assert lines["my:Cigarettes"]["category_label"] == "Cigarettes"
    assert lines["dining out"]["source"] == "calculated_by_mita"
    # Building the month again keeps the user's lines and what they replace.
    again = await preview(later, fresh)
    assert by_source(again, "set_by_you") == {
        "my:Fuel": "200.00",
        "my:Cigarettes": "200.00",
    }
    assert "transport gas" not in by_source(again, "calculated_by_mita")
    assert again["changes"] == []


async def test_make_fuel_250_previews_and_saves_exactly(m, person, connection):
    token = m.token(person)
    await save(m, token, await preview(m, token, budget_lines=[FUEL]))
    change = await preview(m, token, budget_lines=[{"label": "fuel", "amount": 250}])
    assert change["changes"] == [
        {
            "category": "my:Fuel",
            "category_label": "Fuel",
            "before": "200.00",
            "after": "250.00",
            "source": "set_by_you",
        }
    ]
    # "fuel" is the user's existing line (any letter case); its replaces kept.
    assert "transport gas" not in by_source(change, "calculated_by_mita")
    await save(m, token, change)
    assert (await plan_totals(connection, person))["my:Fuel"] == D("250.00")


async def test_a_plan_over_the_income_is_refused_not_shrunk(m, person, connection):
    result = await m.call(
        m.token(person),
        "preview_monthly_budget",
        {
            "budget_lines": [
                {"label": "Cigarettes", "amount": 900},
                {"label": "Fuel", "amount": 400, "replaces": ["transport gas"]},
            ]
        },
    )
    assert result.is_error
    error = result.structured_content["error"]
    assert "never lower their amounts yourself" in error["message"]
    assert error["details"] == {
        "reason": "plan_exceeds_income",
        "currency": "EUR",
        "stated_monthly_income": "2000.00",
        "bills_and_fixed_payments": "340.00",
        "savings_target": "500.00",
        "amounts_set_by_user": "1300.00",
        "exceeds_income_by": "140.00",
    }
    assert await plan_totals(connection, person) == {}


async def test_an_expense_is_recorded_against_the_users_line(m, person, connection):
    token = m.token(person)
    await save(
        m,
        token,
        await preview(m, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]),
    )
    recorded = structured(
        await m.call(
            token,
            "add_transaction",
            {"amount": 7, "budget_line": "cigarettes", "idempotency_key": new_key()},
        )
    )
    assert recorded["transactions"][0]["category"] == "my:Cigarettes"
    assert recorded["transactions"][0]["category_label"] == "Cigarettes"
    status = structured(await m.call(token, "get_budget_status", {}))
    line = {c["category"]: c for c in status["categories"]}["my:Cigarettes"]
    assert (line["planned"], line["spent"], line["source"]) == (
        "200.00",
        "7.00",
        "set_by_you",
    )
    # A standard category still works, and the result names the user's lines.
    other = structured(
        await m.call(
            token,
            "add_transaction",
            {"amount": 3, "category": "groceries", "idempotency_key": new_key()},
        )
    )
    assert any("Cigarettes (my:Cigarettes)" in note for note in other["notes"])
    # A batch item can target the line too.
    batch = structured(
        await m.call(
            token,
            "add_transactions",
            {
                "expenses": [
                    {"amount": 6, "budget_line": "my:Cigarettes"},
                    {"amount": 2, "category": "dining"},
                ],
                "idempotency_key": new_key(),
            },
        )
    )
    assert [t["category"] for t in batch["transactions"]] == ["my:Cigarettes", "dining"]


async def test_expense_targets_are_checked(m, person):
    token = m.token(person)
    for arguments in (
        {"amount": 7, "budget_line": "Cigarettes"},  # no such line yet
        {"amount": 7},  # neither
        {"amount": 7, "category": "other", "budget_line": "Cigarettes"},  # both
    ):
        result = await m.call(
            token, "add_transaction", {**arguments, "idempotency_key": new_key()}
        )
        assert result.is_error, arguments


async def test_moving_an_expense_onto_the_users_line(m, person):
    token = m.token(person)
    await save(
        m,
        token,
        await preview(m, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]),
    )
    recorded = structured(
        await m.call(
            token,
            "add_transaction",
            {"amount": 7, "category": "other", "idempotency_key": new_key()},
        )
    )
    moved = structured(
        await m.call(
            token,
            "update_transaction",
            {"ref": recorded["transactions"][0]["ref"], "budget_line": "Cigarettes"},
        )
    )
    assert moved["status"] == "updated"
    assert moved["transaction"]["category"] == "my:Cigarettes"


async def test_a_user_line_is_never_held_as_a_bill(m, person):
    token = m.token(person)
    await save(
        m,
        token,
        await preview(m, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]),
    )
    forecast = structured(await m.call(token, "get_budget_forecast", {}))
    assert forecast["commitments_reserved"] == "340.00"  # the rent payment only
    calendar = structured(await m.call(token, "get_calendar_month", {}))
    groups = {line["category"]: line["group"] for line in calendar["categories"]}
    assert groups["my:Cigarettes"] == "everyday"
    assert groups["rent"] == "commitment"
    # One safe daily figure, from the persisted plan.
    assert calendar["summary"]["average_per_day"] == forecast["safe_daily_limit"]
    assert calendar["summary"]["commitments_reserved"] == "340.00"


async def test_redistribution_never_changes_the_users_amount(m, person, connection):
    token = m.token(person)
    await save(
        m,
        token,
        await preview(m, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]),
    )
    before = await plan_totals(connection, person)
    for arguments in (
        {"amount": 60, "budget_line": "Cigarettes"},  # far over today's slice
        {"amount": 150, "category": "groceries"},  # MITA covers this from its own
    ):
        structured(
            await m.call(
                token, "add_transaction", {**arguments, "idempotency_key": new_key()}
            )
        )
    after = await plan_totals(connection, person)
    assert after["my:Cigarettes"] == D("200.00")
    assert sum(after.values()) == sum(before.values())


async def test_removing_a_line_brings_mitas_line_back(m, person, connection):
    token = m.token(person)
    await save(m, token, await preview(m, token, budget_lines=[FUEL]))
    removed = await preview(m, token, remove_lines=["Fuel"])
    assert "my:Fuel" not in by_source(removed, "set_by_you")
    assert by_source(removed, "calculated_by_mita")["transport gas"] == "90.00"
    assert {(c["category"], c["after"]) for c in removed["changes"]} >= {
        ("my:Fuel", None),
        ("transport gas", "90.00"),
    }
    await save(m, token, removed)
    totals = await plan_totals(connection, person)
    assert "my:Fuel" not in totals and totals["transport gas"] == D("90.00")


async def test_same_name_as_mitas_line_is_pointed_out(m, person):
    draft = await preview(
        m, m.token(person), budget_lines=[{"label": "Fuel", "amount": 200}]
    )
    assert any("same name as MITA's 'Fuel' line" in w for w in draft["warnings"])


async def test_requests_are_checked(m, person):
    token = m.token(person)
    for arguments in (
        {
            "budget_lines": [
                {"label": "Fuel", "amount": 1},
                {"label": "fuel", "amount": 2},
            ]
        },
        {"budget_lines": [{"label": " ", "amount": 1}]},
        {"budget_lines": [{"label": "x" * 41, "amount": 1}]},
        {"budget_lines": [{"label": "Fuel", "amount": 0}]},
        {"budget_lines": [{"label": "Fuel", "amount": "1.234"}]},
        {"budget_lines": [{"label": "Fuel", "amount": 1, "replaces": ["tobacco"]}]},
        {"budget_lines": [{"label": "Fuel", "amount": 1, "user_id": "x"}]},
        {"remove_lines": ["Never set"]},
    ):
        result = await m.call(token, "preview_monthly_budget", arguments)
        assert result.is_error, arguments


async def test_the_draft_hides_the_lines_and_binds_them_to_the_user(
    m, seed, person, connection
):
    other = await seed_person(m, seed)
    token = m.token(person)
    draft = await preview(
        m, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]
    )
    value = draft["draft_token"]
    assert value.startswith("bd2_")
    raw = base64.urlsafe_b64decode(value[4:] + "=" * (-len(value[4:]) % 4))
    assert b"Cigarettes" not in raw and b"200" not in raw
    tampered = bytearray(raw)
    tampered[-1] ^= 0x01
    forged = "bd2_" + base64.urlsafe_b64encode(bytes(tampered)).decode().rstrip("=")
    for bogus, who in ((forged, token), (value, m.token(other))):
        result = await m.call(who, "save_monthly_budget", {"draft_token": bogus})
        assert result.is_error and INVALID_DRAFT in result.content[0].text
    assert await plan_totals(connection, person) == {}


async def test_a_changed_plan_invalidates_the_reviewed_one(m, person, connection):
    token = m.token(person)
    first = await preview(
        m, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]
    )
    second = await preview(m, token, budget_lines=[{"label": "Coffee", "amount": 30}])
    await save(m, token, second)
    stale = await m.call(
        token, "save_monthly_budget", {"draft_token": first["draft_token"]}
    )
    assert stale.is_error and CHANGED_DRAFT in stale.content[0].text
    totals = await plan_totals(connection, person)
    assert "my:Cigarettes" not in totals and totals["my:Coffee"] == D("30.00")


async def test_next_month_continues_the_users_lines(m, person):
    token = m.token(person)
    await save(m, token, await preview(m, token, budget_lines=[FUEL]))
    november = await preview(m, token, month="2026-11")
    assert by_source(november, "set_by_you") == {"my:Fuel": "200.00"}
    assert "transport gas" not in by_source(november, "calculated_by_mita")
    assert any("continue in this month" in w for w in november["warnings"])


async def test_automatic_budget_is_unchanged(m, person):
    draft = await preview(m, m.token(person))
    assert draft["draft_token"].startswith("bd1_")
    assert by_source(draft, "set_by_you") == {}
    assert draft["user_set_total"] == "0.00"
    assert draft["changes"] == []
    expected = engine({})
    mita = by_source(draft, "calculated_by_mita")
    assert {c: D(a) for c, a in mita.items()} == expected.discretionary


async def test_tool_text_states_the_rule(m, person):
    tools = {t.name: t for t in await m.list_tools(m.token(person))}
    preview_tool = tools["preview_monthly_budget"]
    props = preview_tool.input_schema["properties"]
    assert "budget_lines" in props and "remove_lines" in props
    text_ = preview_tool.description
    assert "keeps it exactly as a line of the user's" in text_
    assert "allocates only the money left" in text_
    assert "never call an amount the user's unless its source is set_by_you" in text_
    assert "never recompute, split or edit the numbers yourself" in text_
    assert "budget_line" in tools["add_transaction"].input_schema["properties"]
    assert "budget_line" in tools["update_transaction"].input_schema["properties"]
