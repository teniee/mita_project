"""One display name per MITA category, the same in every tool (backend F-2).

Real ChatGPT showed one stored category under several names ("Transport gas" /
"Fuel" / "Gas", "Insurance medical" / "Medical insurance"). Every result now
carries ``category_label`` from ``app/mcp/categories.py``, and budget status and
the forecast show an expense category together with the plan category it
spends from — as a presentation rule only: what is stored never changes.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.config.category_aliases import plan_categories_for
from app.core.financial_constants import FinancialConstants
from app.mcp import categories
from app.services.core.engine.calendar_engine import CATEGORY_BEHAVIOR
from tests_mcp.conftest import structured
from tests_mcp.test_budget_plan import NOW, seed_ana

ALL_CODES = sorted(set(categories.PLAN_LABELS) | set(categories.EXPENSE_LABELS))


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


@pytest.fixture
async def ana(m, seed):
    return await seed_ana(m, seed)


def key() -> str:
    return uuid.uuid4().hex


def test_every_stored_vocabulary_has_an_explicit_label():
    for code in CATEGORY_BEHAVIOR:
        assert code in categories.PLAN_LABELS, code
    for code in FinancialConstants.VALID_TRANSACTION_CATEGORIES:
        assert code in categories.EXPENSE_LABELS, code
    for code in FinancialConstants.VALID_GOAL_CATEGORIES:
        assert code in categories.GOAL_LABELS, code
    assert "goal_savings" in categories.PLAN_LABELS


def test_pairs_come_from_the_apis_own_alias_table():
    for expense, bucket in categories.PRIMARY_PLAN_BUCKET.items():
        assert expense in FinancialConstants.VALID_TRANSACTION_CATEGORIES, expense
        assert bucket in CATEGORY_BEHAVIOR, bucket
        assert bucket in plan_categories_for(expense), (expense, bucket)


def test_two_categories_share_a_label_exactly_when_they_share_a_line():
    buckets = set(categories.PLAN_LABELS)
    for a in ALL_CODES:
        for b in ALL_CODES:
            same_label = categories.label(a) == categories.label(b)
            same_line = categories.line_key(a, buckets) == categories.line_key(
                b, buckets
            )
            assert same_label == same_line, (a, b)


def test_labels_are_deterministic_for_unknown_codes():
    assert categories.label("transport gas") == "Fuel"
    assert categories.label("gas") == "Fuel"
    assert categories.label("insurance medical") == "Medical insurance"
    assert categories.label("out of pocket medical") == "Healthcare"
    assert categories.label("entertainment events") == "Entertainment"
    assert categories.label("car_payment") == "Car payment"
    assert categories.label(None) == "Uncategorized"
    assert categories.goal_label(None) == "Savings"


def test_a_pair_is_combined_only_when_the_plan_has_that_bucket():
    planned = {"gas": Decimal("0"), "groceries": Decimal("100")}
    spent = {"gas": Decimal("55"), "groceries": Decimal("10")}
    lines = {k: rest for k, *rest in categories.group_lines(planned, spent)}
    assert lines["gas"] == ["Fuel", ["gas"], Decimal("0"), Decimal("55")]
    planned["transport gas"] = Decimal("112.50")
    lines = {k: rest for k, *rest in categories.group_lines(planned, spent)}
    assert "gas" not in lines
    assert lines["transport gas"] == [
        "Fuel",
        ["gas", "transport gas"],
        Decimal("112.50"),
        Decimal("55"),
    ]


def test_colliding_unknown_names_stay_apart():
    planned = {"transport gas": Decimal("10"), "fuel": Decimal("5")}
    names = sorted(name for _, name, *_ in categories.group_lines(planned, {}))
    assert names == ["Fuel (fuel)", "Fuel (transport gas)"]


async def _owner_month(m, user):
    """The owner's real staging run: profile + rent, budget saved, then three
    expenses recorded in the expense vocabulary."""
    token = m.token(user)
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
    )
    for amount, category, merchant in (
        ("36.80", "groceries", "Lidl"),
        ("8.00", "dining", "Coffee"),
        ("55.00", "gas", None),
    ):
        args = {"amount": amount, "category": category, "idempotency_key": key()}
        if merchant:
            args["merchant"] = merchant
        structured(await m.call(token, "add_transaction", args))
    return token, preview


async def test_fuel_is_one_line_with_one_name_in_every_tool(m, ana, connection):
    token, preview = await _owner_month(m, ana)

    allocations = {a["category"]: a for a in preview["category_allocations"]}
    assert allocations["transport gas"]["category_label"] == "Fuel"
    assert allocations["insurance medical"]["category_label"] == "Medical insurance"
    assert allocations["out of pocket medical"]["category_label"] == "Healthcare"
    assert preview["fixed_obligations"][0]["category_label"] == "Rent"

    status = structured(await m.call(token, "get_budget_status", {}))
    lines = {c["category_label"]: c for c in status["categories"]}
    labels = [c["category_label"] for c in status["categories"]]
    assert len(labels) == len(set(labels))  # never two lines with one name
    assert "Transport gas" not in labels and "Gas" not in labels

    stored = await connection.execute(
        text(
            "SELECT category, sum(planned_amount) FROM daily_plan "
            "WHERE user_id = :u GROUP BY category"
        ),
        {"u": ana.id},
    )
    planned = {category: amount for category, amount in stored.all()}
    # Presentation only: both stored rows are still there, untouched.
    assert {"transport gas", "gas", "dining out", "dining"} <= set(planned)

    fuel = lines["Fuel"]
    assert fuel["category"] == "transport gas"
    assert fuel["category_codes"] == ["gas", "transport gas"]
    assert Decimal(fuel["planned"]) == planned["transport gas"] + planned["gas"]
    assert fuel["spent"] == "55.00"
    dining = lines["Dining out"]
    assert dining["category_codes"] == ["dining", "dining out"]
    assert Decimal(dining["planned"]) == planned["dining out"] + planned["dining"]
    assert dining["spent"] == "8.00"
    assert status["total_planned"] == "2325.00" and status["total_spent"] == "99.80"
    # MITA's redistribution moved money to cover today's spending: say so.
    assert any("automatic redistribution moved" in n for n in status["notes"])

    forecast = structured(await m.call(token, "get_budget_forecast", {}))
    risky = {c["category"] for c in forecast["categories_at_risk"]}
    assert not risky & {"gas", "dining"}  # no longer split into "unplanned" lines
    for item in forecast["categories_at_risk"]:
        assert item["category_label"] == categories.label(item["category"])

    listed = structured(await m.call(token, "list_transactions", {}))
    assert {(t["category"], t["category_label"]) for t in listed["transactions"]} == {
        ("groceries", "Groceries"),
        ("dining", "Dining out"),
        ("gas", "Fuel"),
    }
    summary = structured(await m.call(token, "get_financial_summary", {}))
    assert [c["category_label"] for c in summary["top_categories"]] == [
        "Fuel",
        "Groceries",
        "Dining out",
    ]
    breakdown = structured(await m.call(token, "get_spending_breakdown", {}))
    assert {c["category_label"] for c in breakdown["categories"]} == {
        "Fuel",
        "Groceries",
        "Dining out",
    }
    history = structured(
        await m.call(token, "get_spending_history", {"category": "gas"})
    )
    assert history["category_label"] == "Fuel"
    assert history["months"][-1]["categories"][0]["category_label"] == "Fuel"
