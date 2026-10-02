"""Exact figures, through the real tools, from a hand-built ledger and plan.

Fixture (user in UTC, "now" = 2026-03-15 12:00 UTC, March has 31 days):

    plan      rent      1200.00 on Mar 1
              food        10.00 every day Mar 1..31            = 310.00
              total                                            = 1510.00
              (every plan row carries a WRONG spent_amount cache of 999.99)

    ledger    Mar 1  rent      1200.00  "Landlord LLC"
              Mar 2  food        12.50  "Lidl"
              Mar 2  food         7.50  "Bakery"
              Mar 10 food        40.00  "LIDL Varna"
              Mar 11 food       500.00  (soft-deleted)
              Mar 14 shopping    30.00  (no plan → unplanned)
              Feb 28 food        99.99  (previous month)

    March spent = 1200 + 12.50 + 7.50 + 40 + 30 = 1290.00, 5 transactions.
"""

from datetime import date, datetime, timezone

import pytest

from tests_mcp.conftest import structured

NOW = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)


def at(day, hour=10, minute=0):
    return datetime(2026, 3, day, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
async def ledger_user(seed):
    user = await seed.user(income="5000.00")
    await seed.plan(user, date(2026, 3, 1), {"rent": "1200.00", "food": "10.00"})
    for d in range(2, 32):
        await seed.plan(user, date(2026, 3, d), {"food": "10.00"})
    await seed.txn(user, "1200.00", "rent", at(1), merchant="Landlord LLC")
    await seed.txn(
        user,
        "12.50",
        "food",
        at(2, 9),
        merchant="Lidl",
        description="weekly shop with Anna",
    )
    await seed.txn(user, "7.50", "food", at(2, 18), merchant="Bakery")
    await seed.txn(user, "40.00", "food", at(10), merchant="LIDL Varna")
    await seed.txn(
        user, "500.00", "food", at(11), merchant="Deleted Store", deleted=True
    )
    await seed.txn(user, "30.00", "shopping", at(14))
    await seed.txn(
        user, "99.99", "food", datetime(2026, 2, 28, 12, tzinfo=timezone.utc)
    )
    return user


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


async def test_financial_summary_exact(m, ledger_user):
    data = structured(await m.call(m.token(ledger_user), "get_financial_summary"))
    assert (data["year"], data["month"], data["month_position"]) == (2026, 3, "current")
    assert data["stated_monthly_income"] == "5000.00"
    assert data["plan_status"] == "generated"
    assert data["planned_total"] == "1510.00"
    assert data["spent_total"] == "1290.00"
    assert data["remaining_total"] == "220.00"
    assert data["transaction_count"] == 5
    assert data["days_in_month"] == 31 and data["days_elapsed"] == 15
    assert [
        (c["category"], c["total"], c["share_percent"]) for c in data["top_categories"]
    ] == [
        ("rent", "1200.00", "93.0"),
        ("food", "60.00", "4.7"),
        ("shopping", "30.00", "2.3"),
    ]


async def test_budget_status_exact_and_ignores_stale_plan_cache(m, ledger_user):
    data = structured(await m.call(m.token(ledger_user), "get_budget_status"))
    assert data["plan_status"] == "generated"
    assert data["total_planned"] == "1510.00"
    assert data["total_spent"] == "1290.00"  # not 32 × 999.99 from the cache column
    assert data["total_remaining"] == "220.00"
    rows = {c["category"]: c for c in data["categories"]}
    assert rows["rent"] == {
        "category": "rent",
        "planned": "1200.00",
        "spent": "1200.00",
        "remaining": "0.00",
        "percent_used": "100.0",
        "state": "within_budget",
    }
    assert rows["food"] == {
        "category": "food",
        "planned": "310.00",
        "spent": "60.00",
        "remaining": "250.00",
        "percent_used": "19.4",
        "state": "within_budget",
    }
    assert rows["shopping"] == {
        "category": "shopping",
        "planned": "0.00",
        "spent": "30.00",
        "remaining": "-30.00",
        "percent_used": None,
        "state": "unplanned_spending",
    }
    assert data["today"] == {
        "date": "2026-03-15",
        "planned": "10.00",
        "spent": "0.00",
        "remaining": "10.00",
    }


async def test_forecast_exact(m, ledger_user):
    data = structured(await m.call(m.token(ledger_user), "get_budget_forecast"))
    assert data["plan_status"] == "generated"
    assert (data["days_elapsed"], data["days_remaining"]) == (15, 16)
    assert data["total_planned"] == "1510.00"
    assert data["total_spent"] == "1290.00"
    assert data["remaining_budget"] == "220.00"
    assert data["current_daily_pace"] == "86.00"  # 1290 / 15
    assert data["safe_daily_limit"] == "13.75"  # 220 / 16
    assert data["projected_month_end_spend"] == "2666.00"  # 1290 + 86 × 16
    assert data["projected_month_end_balance"] == "-1156.00"
    assert data["status"] == "danger"  # overspend 1156 ≥ 10 % of 1510
    risk = [
        (c["category"], c["pace_ratio"], c["days_until_exhausted"])
        for c in data["categories_at_risk"]
    ]
    assert risk == [("shopping", "9.99", 0), ("rent", "2.07", 0)]


async def test_spending_breakdown_exact(m, ledger_user):
    data = structured(
        await m.call(
            m.token(ledger_user),
            "get_spending_breakdown",
            {"start_date": "2026-03-01", "end_date": "2026-03-31"},
        )
    )
    assert data["total_spent"] == "1290.00"
    assert data["transaction_count"] == 5
    assert [
        (c["category"], c["total"], c["transaction_count"]) for c in data["categories"]
    ] == [
        ("rent", "1200.00", 1),
        ("food", "60.00", 3),
        ("shopping", "30.00", 1),
    ]


async def test_spending_breakdown_defaults_to_last_30_local_days(m, ledger_user):
    data = structured(await m.call(m.token(ledger_user), "get_spending_breakdown"))
    assert (data["start_date"], data["end_date"]) == ("2026-02-14", "2026-03-15")
    assert data["total_spent"] == "1389.99"  # includes the Feb 28 purchase


async def test_list_transactions_fields_order_and_totals(m, ledger_user):
    data = structured(
        await m.call(
            m.token(ledger_user),
            "list_transactions",
            {"start_date": "2026-03-01", "end_date": "2026-03-15"},
        )
    )
    assert data["matching_count"] == 5 and data["returned_count"] == 5
    assert data["matching_total"] == "1290.00" and data["has_more"] is False
    assert [
        (t["date"], t["amount"], t["category"], t["merchant"])
        for t in data["transactions"]
    ] == [
        ("2026-03-14", "30.00", "shopping", None),
        ("2026-03-10", "40.00", "food", "LIDL Varna"),
        ("2026-03-02", "7.50", "food", "Bakery"),
        ("2026-03-02", "12.50", "food", "Lidl"),
        ("2026-03-01", "1200.00", "rent", "Landlord LLC"),
    ]
    for item in data["transactions"]:
        assert set(item) == {"date", "amount", "currency", "category", "merchant"}


async def test_list_transactions_filters(m, ledger_user):
    token = m.token(ledger_user)
    window = {"start_date": "2026-03-01", "end_date": "2026-03-31"}
    food = structured(
        await m.call(token, "list_transactions", {**window, "category": "FOOD"})
    )
    assert (food["matching_count"], food["matching_total"]) == (3, "60.00")
    lidl = structured(
        await m.call(token, "list_transactions", {**window, "merchant": "lidl"})
    )
    assert sorted(t["amount"] for t in lidl["transactions"]) == ["12.50", "40.00"]
    assert lidl["matching_total"] == "52.50"
    page = structured(await m.call(token, "list_transactions", {**window, "limit": 2}))
    assert page["returned_count"] == 2 and page["has_more"] is True
    assert page["matching_count"] == 5 and page["matching_total"] == "1290.00"


async def test_like_wildcards_in_merchant_filter_are_literal(m, ledger_user):
    data = structured(
        await m.call(
            m.token(ledger_user),
            "list_transactions",
            {"start_date": "2026-03-01", "end_date": "2026-03-31", "merchant": "%"},
        )
    )
    assert data["matching_count"] == 0


async def test_soft_deleted_transaction_reaches_no_tool(m, ledger_user):
    token = m.token(ledger_user)
    for tool, args in [
        ("list_transactions", {"start_date": "2026-03-01", "end_date": "2026-03-31"}),
        (
            "get_spending_breakdown",
            {"start_date": "2026-03-01", "end_date": "2026-03-31"},
        ),
        ("get_financial_summary", {}),
        ("get_budget_status", {}),
        ("get_budget_forecast", {}),
    ]:
        result = await m.call(token, tool, args)
        text = result.content[0].text
        assert "500.00" not in text and "Deleted Store" not in text, tool
        assert "560.00" not in text, tool  # 60 + the deleted 500


async def test_previous_month_is_its_own_month(m, ledger_user):
    data = structured(
        await m.call(
            m.token(ledger_user), "get_financial_summary", {"year": 2026, "month": 2}
        )
    )
    assert data["month_position"] == "past"
    assert data["spent_total"] == "99.99" and data["transaction_count"] == 1
    assert data["plan_status"] == "not_generated"
    assert data["planned_total"] is None and data["remaining_total"] is None
    assert data["days_elapsed"] == 28


async def test_private_fields_never_returned(m, ledger_user):
    token = m.token(ledger_user)
    for tool, args in [
        ("list_transactions", {"start_date": "2026-03-01", "end_date": "2026-03-31"}),
        ("get_spending_breakdown", {}),
        ("get_financial_summary", {}),
        ("get_budget_status", {}),
        ("get_profile", {}),
    ]:
        text = (await m.call(token, tool, args)).content[0].text
        for secret in (
            "weekly shop with Anna",
            "Secret Street",
            "private note",
            "receipts.example.test",
            str(ledger_user.id),
            ledger_user.email,
        ):
            assert secret not in text, (tool, secret)


async def test_profile(m, seed):
    user = await seed.user(tz="Europe/Sofia", currency="EUR", name="Ivan")
    data = structured(await m.call(m.token(user), "get_profile"))
    assert (
        data["name"] == "Ivan"
        and data["currency"] == "EUR"
        and data["timezone"] == "Europe/Sofia"
    )
    assert data["has_completed_onboarding"] is True
    assert data["nickname"].endswith("@example.test") and "***" in data["nickname"]
    assert data["id"].startswith("prf_") and str(user.id) not in data["id"]
    again = structured(await m.call(m.token(user), "get_profile"))
    assert again["id"] == data["id"], "profile id must be stable"


async def test_mixed_currency_is_disclosed_not_converted(m, seed):
    user = await seed.user(currency="EUR")
    await seed.txn(user, "10.00", "food", at(3))
    await seed.txn(user, "20.00", "food", at(4), currency="USD")
    data = structured(
        await m.call(
            m.token(user),
            "get_spending_breakdown",
            {"start_date": "2026-03-01", "end_date": "2026-03-31"},
        )
    )
    assert data["currency"] == "EUR" and data["total_spent"] == "30.00"
    assert any("USD" in note and "does not convert" in note for note in data["notes"])


async def test_date_range_validation(m, ledger_user):
    token = m.token(ledger_user)
    bad = await m.call(
        token,
        "list_transactions",
        {"start_date": "2026-03-10", "end_date": "2026-03-01"},
    )
    assert bad.is_error and bad.structured_content["error"]["category"] == "validation"
    wide = await m.call(
        token,
        "get_spending_breakdown",
        {"start_date": "2024-01-01", "end_date": "2026-03-01"},
    )
    assert wide.is_error and "366" in wide.content[0].text
    half = await m.call(token, "get_budget_status", {"year": 2026})
    assert (
        half.is_error and half.structured_content["error"]["category"] == "validation"
    )


async def test_schema_rejects_out_of_range_arguments(m, ledger_user):
    token = m.token(ledger_user)
    for args in (
        {"limit": 0},
        {"limit": 1000},
        {"category": "food; drop table"},
        {"start_date": "yesterday"},
    ):
        result = await m.call(token, "list_transactions", args)
        assert result.is_error, args


async def test_goals_projection(m, seed):
    user = await seed.user()
    await seed.goal(
        user,
        title="Car",
        target_amount=1000,
        saved_amount=250,
        monthly_contribution=100,
        target_date=date(2026, 9, 15),
    )
    await seed.goal(
        user, title="Someday", target_amount=500, saved_amount=100, target_date=None
    )
    await seed.goal(
        user, title="Done", target_amount=200, saved_amount=200, status="completed"
    )
    await seed.goal(
        user, title="Gone", target_amount=300, saved_amount=0, deleted_at=NOW
    )
    data = structured(await m.call(m.token(user), "get_goals"))
    goals = {g["title"]: g for g in data["goals"]}
    assert set(goals) == {"Car", "Someday"}
    car = goals["Car"]
    assert (
        car["target_amount"],
        car["saved_amount"],
        car["remaining_amount"],
        car["progress_percent"],
    ) == ("1000.00", "250.00", "750.00", "25.0")
    # 184 days / 30.44 = 6.04 months; 250 + 100 × 6.04 = 854.00 < 1000 → not on track.
    assert car["projection"] == {
        "basis": "monthly_contribution",
        "on_track": False,
        "months_remaining": "6.04",
        "required_monthly_contribution": "124.17",
        "projected_saved_by_target_date": "854.00",
        "shortfall": "146.00",
    }
    # No deadline: nothing to be on/off track against — not "false".
    assert goals["Someday"]["projection"]["basis"] == "no_target_date"
    assert goals["Someday"]["projection"]["on_track"] is None
    every = structured(await m.call(m.token(user), "get_goals", {"status": "all"}))
    assert {g["title"] for g in every["goals"]} == {"Car", "Someday", "Done"}


async def test_recurring_only_confirmed_items(m, seed):
    user = await seed.user()
    await seed.scheduled(
        user,
        category="rent",
        amount=1200,
        recurrence="monthly",
        scheduled_date=date(2026, 4, 1),
    )
    await seed.scheduled(
        user,
        category="insurance",
        amount=300,
        recurrence=None,
        scheduled_date=date(2026, 4, 10),
    )
    await seed.scheduled(
        user,
        category="travel",
        amount=900,
        recurrence=None,
        scheduled_date=date(2026, 8, 1),
    )  # beyond 60 days
    await seed.scheduled(user, category="gym", amount=40, status="cancelled")
    await seed.txn(
        user, "15.99", "subscriptions", at(5), merchant="Netflix", recurring=True
    )
    await seed.txn(
        user,
        "15.99",
        "subscriptions",
        datetime(2026, 2, 5, tzinfo=timezone.utc),
        merchant="netflix",
        recurring=True,
    )
    # Same merchant, NOT marked recurring by the user → must not be listed.
    await seed.txn(user, "11.99", "subscriptions", at(6), merchant="Spotify")
    data = structured(await m.call(m.token(user), "get_recurring_expenses"))
    assert [
        (i["category"], i["amount"], i["recurrence"], i["due_date"])
        for i in data["scheduled_recurring"]
    ] == [("rent", "1200.00", "monthly", "2026-04-01")]
    assert [(i["category"], i["due_date"]) for i in data["upcoming_one_time"]] == [
        ("insurance", "2026-04-10")
    ]
    assert [
        (i["label"], i["last_amount"], i["last_date"], i["occurrences_in_lookback"])
        for i in data["marked_recurring"]
    ] == [("Netflix", "15.99", "2026-03-05", 2)]
    assert data["inferred"] == []
    assert "Spotify" not in str(data)
