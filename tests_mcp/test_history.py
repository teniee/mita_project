"""get_spending_history and get_financial_climate: exact figures, explicit completeness.

Ledger (Europe/Sofia, today 2026-10-11):
  Jun: groceries 300 (5th), dining 50 (28th)       → 350
  Jul: groceries 320 (10th)                         → 320
  Aug: nothing recorded                             →   0
  Sep: groceries 360 (3rd), dining 40 (27th)        → 400   (+ a deleted 999)
  Oct: groceries 100 (2nd)                          → 100 so far
First recorded expense: June → May is before tracking.
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import pytest

from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)


def at(y, mo, d, h=12):
    return datetime(y, mo, d, h, tzinfo=timezone.utc)


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


@pytest.fixture
async def ana(seed):
    user = await seed.user(tz="Europe/Sofia", currency="EUR")
    await seed.txn(user, "300.00", "groceries", at(2026, 6, 5))
    await seed.txn(user, "50.00", "dining", at(2026, 6, 28))
    await seed.txn(user, "320.00", "groceries", at(2026, 7, 10))
    await seed.txn(user, "360.00", "groceries", at(2026, 9, 3))
    await seed.txn(user, "40.00", "dining", at(2026, 9, 27))
    await seed.txn(user, "999.00", "groceries", at(2026, 9, 15), deleted=True)
    await seed.txn(user, "100.00", "groceries", at(2026, 10, 2))
    return user


def pct(latest: Decimal, earlier: Decimal) -> str:
    return str(
        ((latest - earlier) / earlier * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    )


async def test_six_month_history_with_explicit_completeness(m, ana):
    data = structured(await m.call(m.token(ana), "get_spending_history", {}))
    assert (data["period_start"], data["period_end"]) == ("2026-05-01", "2026-10-11")
    assert data["currency"] == "EUR" and data["timezone"] == "Europe/Sofia"
    assert [
        (x["month"], x["status"], x["transaction_count"], x["total_spent"])
        for x in data["months"]
    ] == [
        ("2026-05", "before_tracking", 0, "0.00"),
        ("2026-06", "recorded", 2, "350.00"),
        ("2026-07", "recorded", 1, "320.00"),
        ("2026-08", "recorded", 0, "0.00"),
        ("2026-09", "recorded", 2, "400.00"),
        ("2026-10", "in_progress", 1, "100.00"),
    ]
    june = data["months"][1]["categories"]
    assert june == [
        {"category": "groceries", "total": "300.00", "transaction_count": 1},
        {"category": "dining", "total": "50.00", "transaction_count": 1},
    ]
    assert data["months_with_data"] == 4 and data["complete_months"] == 4
    assert data["average_monthly_spending"] == "267.50"  # (350+320+0+400)/4
    assert data["median_monthly_spending"] == "335.00"  # (320+350)/2
    assert data["current_month_to_date"] == "100.00"
    assert data["largest_category"] == {
        "category": "groceries",
        "total": "1080.00",
        "transaction_count": 4,
    }
    earlier = (Decimal("350") + Decimal("320") + Decimal("0")) / 3
    assert data["trend"] == {
        "status": "ok",
        "latest_month": "2026-09",
        "latest_total": "400.00",
        "earlier_average": "223.33",
        "change_percent": pct(
            Decimal("400"), earlier.quantize(Decimal("0.01"), ROUND_HALF_UP)
        ),
        "direction": "up",
    }
    groceries = next(t for t in data["category_trends"] if t["category"] == "groceries")
    assert groceries["trend"]["latest_total"] == "360.00"
    assert groceries["trend"]["earlier_average"] == "206.67"  # (300+320+0)/3
    assert any("not necessarily that nothing was spent" in n for n in data["notes"])
    assert any("before_tracking" in n for n in data["notes"])
    assert "999" not in str(data)  # deleted expense excluded
    for month in data["months"]:  # compact: no raw transactions
        assert set(month) == {
            "month",
            "status",
            "transaction_count",
            "total_spent",
            "categories",
        }


async def test_category_filter_answers_the_grocery_question(m, ana):
    data = structured(
        await m.call(m.token(ana), "get_spending_history", {"category": "Groceries"})
    )
    assert data["category"] == "groceries"
    assert [x["total_spent"] for x in data["months"]] == [
        "0.00",
        "300.00",
        "320.00",
        "0.00",
        "360.00",
        "100.00",
    ]
    assert data["category_trends"] == []
    assert data["trend"]["latest_total"] == "360.00"
    assert data["trend"]["earlier_average"] == "206.67"


async def test_trends_need_three_complete_months(m, seed):
    user = await seed.user(tz="UTC")
    await seed.txn(user, "10.00", "dining", at(2026, 8, 10))
    await seed.txn(user, "20.00", "dining", at(2026, 9, 10))
    data = structured(await m.call(m.token(user), "get_spending_history", {}))
    assert data["complete_months"] == 2
    assert data["trend"] == {
        "status": "insufficient_data",
        "latest_month": None,
        "latest_total": None,
        "earlier_average": None,
        "change_percent": None,
        "direction": None,
    }


async def test_a_new_account_has_no_history_and_says_so(m, seed):
    user = await seed.user(tz="UTC")
    data = structured(await m.call(m.token(user), "get_spending_history", {}))
    assert [x["status"] for x in data["months"]] == ["before_tracking"] * 5 + [
        "in_progress"
    ]
    assert data["months_with_data"] == 0 and data["complete_months"] == 0
    assert data["average_monthly_spending"] is None and data["largest_category"] is None
    assert data["trend"]["status"] == "insufficient_data"
    assert "No expenses are recorded in MITA yet." in data["notes"]
    climate = structured(await m.call(m.token(user), "get_financial_climate", {}))
    assert climate["average_monthly_spending"] is None
    assert climate["current_month_pace"]["prior_average_to_same_day"] is None
    assert climate["late_month_spending_share"] is None
    assert any("no history to describe" in n for n in climate["notes"])


async def test_months_follow_the_users_timezone(m, seed):
    user = await seed.user(tz="Europe/Sofia")
    await seed.txn(
        user, "15.00", "dining", datetime(2026, 8, 31, 22, 30, tzinfo=timezone.utc)
    )
    data = structured(
        await m.call(m.token(user), "get_spending_history", {"months": 3})
    )
    totals = {x["month"]: x["total_spent"] for x in data["months"]}
    assert totals == {"2026-08": "0.00", "2026-09": "15.00", "2026-10": "0.00"}


async def test_end_month_moves_the_window_but_not_into_the_future(m, ana):
    token = m.token(ana)
    data = structured(
        await m.call(
            token, "get_spending_history", {"months": 3, "end_month": "2026-08"}
        )
    )
    assert [x["month"] for x in data["months"]] == ["2026-06", "2026-07", "2026-08"]
    assert data["period_end"] == "2026-08-31" and data["current_month_to_date"] is None
    for bad in (
        {"end_month": "2026-11"},
        {"months": 13},
        {"months": 0},
        {"end_month": "10/2026"},
    ):
        assert (await m.call(token, "get_spending_history", bad)).is_error, bad


async def test_history_survives_a_new_session_and_is_isolated(m, ana, seed):
    first = structured(await m.call(m.token(ana), "get_spending_history", {}))
    fresh_token = m.token(ana)  # a new ChatGPT conversation: new token, same account
    again = structured(await m.call(fresh_token, "get_spending_history", {}))
    assert again == first
    bob = await seed.user(tz="UTC")
    bob_view = structured(await m.call(m.token(bob), "get_spending_history", {}))
    assert bob_view["months_with_data"] == 0 and "1080.00" not in str(bob_view)


async def test_financial_climate_states_exact_facts(m, ana, seed):
    await seed.plan(ana, date(2026, 7, 1), {"groceries": "500.00"})
    await seed.plan(ana, date(2026, 9, 1), {"groceries": "300.00"})
    await seed.goal(ana)  # target 1000, saved 250
    await seed.scheduled(ana)  # rent 1200 monthly, due in 5 days
    data = structured(await m.call(m.token(ana), "get_financial_climate", {}))
    assert (data["period_start"], data["period_end"]) == ("2026-05-01", "2026-10-11")
    assert data["months_with_data"] == 4 and data["total_transactions"] == 6
    assert data["average_monthly_spending"] == "267.50"
    assert data["median_monthly_spending"] == "335.00"
    assert data["category_averages"] == [
        {"category": "groceries", "total": "245.00", "transaction_count": 3},
        {"category": "dining", "total": "22.50", "transaction_count": 2},
    ]
    assert data["current_month_pace"] == {
        "day_of_month": 11,
        "spent_to_date": "100.00",
        "prior_average_to_same_day": "245.00",  # (300+320+0+360)/4
        "months_compared": 4,
    }
    assert data["plan_adherence"] == {
        "months_with_plan": 2,
        "months_within_plan": 1,  # July: 320 <= 500
        "months_over_plan": 1,  # September: 400 > 300
    }
    # June 50/350, July 0/320, September 40/400 → (14.29 + 0 + 10)/3
    assert data["late_month_spending_share"] == "8.1"
    assert data["recurring_obligations"] == {
        "count": 1,
        "current_month_total": "1200.00",
    }
    assert data["savings_goals"] == {
        "active_count": 1,
        "total_target": "1000.00",
        "total_saved": "250.00",
    }
    assert data["data_completeness"] == {
        "complete_months": 4,
        "months_before_tracking": 1,
        "in_progress_month": True,
    }
    text = str(data).lower()
    for label in ("good", "bad", "irresponsible", "poor", "rich", "middle class"):
        assert label not in text  # numbers, not judgments
