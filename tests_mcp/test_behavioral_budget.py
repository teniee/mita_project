"""Planned purchases, flexible budgets and conversational onboarding.

The owner's brief of 2026-11-03 (docs/chatgpt-app/behavioral-budget.md),
acceptance tests 3-10, through the real MCP tools on PostgreSQL: a monthly
amount is laid out by HOW the user buys — exact purchase dates for planned
purchases, an envelope with daily guidance for flexible spending — and the
user's own amounts are never changed. November 2026 (Europe/Sofia, EUR) has
four Wednesdays (4, 11, 18, 25) and five Mondays (2, 9, 16, 23, 30).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from tests_mcp.conftest import structured
from tests_mcp.test_money_consistency import look

D = Decimal
TZ = "Europe/Sofia"


def at(day: int, month: int = 11) -> datetime:
    """Noon in Sofia on that date of 2026."""
    return datetime(2026, month, day, 10, 0, tzinfo=timezone.utc)


def key() -> str:
    return uuid.uuid4().hex


async def call(m, token, tool, arguments=None):
    return structured(await m.call(token, tool, arguments or {}))


async def person(mcp, seed, *, day: int = 2, income=2000, savings=500):
    m = mcp.at(at(day))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": income,
            "currency": "EUR",
            "timezone": TZ,
            "household_size": 1,
            "monthly_savings_target": savings,
        },
    )
    return user, token


WEDNESDAYS = [
    {
        "line": "Groceries",
        "kind": "planned",
        "frequency": "weekly",
        "weekdays": ["wednesday"],
    }
]


async def preview(m, token, **arguments):
    arguments.setdefault("month", "2026-11")
    return await call(m, token, "preview_monthly_budget", arguments)


async def save(m, token, draft):
    return await call(
        m, token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
    )


def line(draft, code):
    return next(a for a in draft["category_allocations"] if a["category"] == code)


async def rows_of(connection, user, category):
    result = await connection.execute(
        text(
            "SELECT date, planned_amount, plan_json FROM daily_plan "
            "WHERE user_id = :u AND category = :c AND date >= '2026-11-01' "
            "AND date < '2026-12-01' ORDER BY date"
        ),
        {"u": user.id, "c": category},
    )
    return {
        r["date"].day: (D(str(r["planned_amount"])), r["plan_json"] or {})
        for r in result.mappings()
    }


# --- Test 3 and Test 4 --------------------------------------------------------------


async def test_weekly_groceries_on_wednesdays(mcp, seed, connection):
    user, token = await person(mcp, seed)
    m = mcp.at(at(2))
    draft = await preview(
        m,
        token,
        budget_lines=[{"label": "Groceries", "amount": 200, "replaces": ["groceries"]}],
        spending_patterns=WEDNESDAYS,
    )
    groceries = line(draft, "my:Groceries")
    assert groceries["spending_type"] == "planned"
    assert groceries["pattern"] == "every Wednesday"
    assert groceries["pattern_source"] == "user_confirmed"
    assert [(p["date"], p["amount"]) for p in groceries["purchases"]] == [
        ("2026-11-04", "50.00"),
        ("2026-11-11", "50.00"),
        ("2026-11-18", "50.00"),
        ("2026-11-25", "50.00"),
    ]
    assert groceries["per_day"] is None  # not a daily budget
    await save(m, token, draft)
    rows = await rows_of(connection, user, "my:Groceries")
    assert {d: p for d, (p, _m) in rows.items()} == {
        4: D("50.00"),
        11: D("50.00"),
        18: D("50.00"),
        25: D("50.00"),
    }
    assert all(
        meta.get("_mita_line_kind_v1") == "planned" for _p, meta in rows.values()
    )


async def test_five_mondays_split_exactly(mcp, seed):
    _user, token = await person(mcp, seed)
    draft = await preview(
        mcp.at(at(2)),
        token,
        budget_lines=[{"label": "Groceries", "amount": 200, "replaces": ["groceries"]}],
        spending_patterns=[
            {
                "line": "Groceries",
                "kind": "planned",
                "frequency": "weekly",
                "weekdays": ["monday"],
            }
        ],
    )
    purchases = line(draft, "my:Groceries")["purchases"]
    assert [p["date"][-2:] for p in purchases] == ["02", "09", "16", "23", "30"]
    assert [p["amount"] for p in purchases] == ["40.00"] * 5
    assert sum(D(p["amount"]) for p in purchases) == D("200.00")  # no 4-week month


async def test_twice_a_month_and_a_february(mcp, seed):
    """Spacing by MITA is said so; month lengths come from the calendar."""
    from app.services.core.engine.spending_schedule import (
        SpendingPattern,
        lay_out_line,
        purchase_dates,
    )

    twice = SpendingPattern("planned", "times_per_month", times_per_month=2)
    assert purchase_dates(twice, 2026, 11) == [date(2026, 11, 8), date(2026, 11, 23)]
    assert purchase_dates(twice, 2027, 2) == [date(2027, 2, 8), date(2027, 2, 22)]
    last = SpendingPattern("planned", "monthly", days_of_month=(31,))
    assert purchase_dates(last, 2028, 2) == [date(2028, 2, 29)]  # leap year
    assert purchase_dates(last, 2027, 2) == [date(2027, 2, 28)]
    odd = lay_out_line(
        D("100.00"),
        SpendingPattern("planned", "dates", days_of_month=(1, 11, 21)),
        2026,
        11,
    )
    assert list(odd.by_date.values()) == [D("33.34"), D("33.33"), D("33.33")]
    biweekly = SpendingPattern("planned", "biweekly", anchor_date=date(2026, 11, 6))
    assert purchase_dates(biweekly, 2026, 12) == [date(2026, 12, 4), date(2026, 12, 18)]

    _user, token = await person(mcp, seed)
    draft = await preview(
        mcp.at(at(2)),
        token,
        budget_lines=[{"label": "Big shop", "amount": 300}],
        spending_patterns=[
            {
                "line": "Big shop",
                "kind": "planned",
                "frequency": "times_per_month",
                "times_per_month": 2,
            }
        ],
    )
    big = line(draft, "my:Big shop")
    assert [(p["date"], p["amount"]) for p in big["purchases"]] == [
        ("2026-11-08", "150.00"),
        ("2026-11-23", "150.00"),
    ]
    assert big["purchase_dates_stated"] is False  # MITA spaced them: say so


# --- Test 5: a flexible budget is an envelope ----------------------------------------


async def test_cigarettes_are_a_flexible_limit_not_daily_purchases(
    mcp, seed, connection
):
    user, token = await person(mcp, seed)
    m2 = mcp.at(at(2))
    draft = await preview(
        m2, token, budget_lines=[{"label": "Cigarettes", "amount": 200}]
    )
    cigarettes = line(draft, "my:Cigarettes")
    assert cigarettes["spending_type"] == "flexible"
    assert (
        cigarettes["pattern_source"] == "mita_default"
    )  # nothing stated, nothing invented
    assert cigarettes["purchases"] == []
    assert (cigarettes["per_day"], cigarettes["per_day_rounded"]) == ("6.67", "7")
    await save(m2, token, draft)

    m3 = mcp.at(at(3))
    await call(
        m3,
        token,
        "add_transaction",
        {"amount": "3.50", "budget_line": "Cigarettes", "idempotency_key": key()},
    )
    seen = await look(m3, token, connection, user, month=11, today=date(2026, 11, 3))
    cal_line = seen.line("my:Cigarettes")
    assert cal_line["spending_type"] == "flexible"
    assert cal_line["purchases"] == [] and cal_line["next_purchase"] is None
    assert (cal_line["spent"], cal_line["remaining"]) == ("3.50", "196.50")
    # 196.50 over the 28 days left (3-30 Nov): guidance, exact and rounded.
    assert (cal_line["left_per_day"], cal_line["left_per_day_rounded"]) == ("7.02", "7")
    assert cal_line["left_per_week"] == "49.13"
    # No date carries a cigarette "purchase".
    assert not any(
        p["category"] == "my:Cigarettes"
        for d in seen.cal["days"]
        for p in d["purchases"]
    )
    # A Saturday spend is not "over" a weekday share: it draws on the envelope.
    m7 = mcp.at(at(7))
    await call(
        m7,
        token,
        "add_transaction",
        {"amount": "20.00", "budget_line": "Cigarettes", "idempotency_key": key()},
    )
    seen = await look(m7, token, connection, user, month=11, today=date(2026, 11, 7))
    assert seen.day(7)["state"] == "within"
    assert seen.line("my:Cigarettes")["remaining"] == "176.50"
    # pacing within the line, not redistribution between lines
    assert all(a == 0 for (_p, _s, a) in seen.rows.values())


# --- the €7 left of a €50 purchase is not lost -----------------------------------------


async def test_a_purchase_under_its_plan_keeps_the_rest_for_the_line(
    mcp, seed, connection
):
    user, token = await person(mcp, seed)
    m2 = mcp.at(at(2))
    draft = await preview(
        m2,
        token,
        budget_lines=[{"label": "Groceries", "amount": 200, "replaces": ["groceries"]}],
        spending_patterns=WEDNESDAYS,
    )
    await save(m2, token, draft)
    m4 = mcp.at(at(4))
    await call(
        m4,
        token,
        "add_transaction",
        {"amount": "43.00", "budget_line": "Groceries", "idempotency_key": key()},
    )
    seen = await look(m4, token, connection, user, month=11, today=date(2026, 11, 4))
    groceries = seen.line("my:Groceries")
    assert (groceries["spent"], groceries["remaining"]) == ("43.00", "157.00")
    first = groceries["purchases"][0]
    assert (first["date"], first["planned"], first["spent"]) == (
        "2026-11-04",
        "50.00",
        "43.00",
    )
    assert groceries["next_purchase"]["date"] == "2026-11-11"
    # The next shop of €55 uses its own €50 and the €7 left from the 4th.
    m11 = mcp.at(at(11))
    await call(
        m11,
        token,
        "add_transaction",
        {"amount": "55.00", "budget_line": "Groceries", "idempotency_key": key()},
    )
    rows = await rows_of(connection, user, "my:Groceries")
    assert rows[4][0] == D("45.00") and rows[11][0] == D("55.00")
    assert rows[18][0] == D("50.00") and rows[25][0] == D("50.00")  # untouched
    seen = await look(m11, token, connection, user, month=11, today=date(2026, 11, 11))
    assert all(a == 0 for (_p, _s, a) in seen.rows.values())


# --- Test 6: no medical insurance --------------------------------------------------------


async def test_no_medical_insurance_and_no_public_transport(mcp, seed):
    _user, token = await person(mcp, seed)
    m = mcp.at(at(2))
    before = await preview(m, token)
    assert any(
        a["category"] == "insurance medical" for a in before["category_allocations"]
    )
    out = await call(
        m,
        token,
        "save_spending_patterns",
        {
            "patterns": [
                {"line": "Medical insurance", "kind": "not_applicable"},
                {"line": "transport public", "kind": "not_applicable"},
            ]
        },
    )
    assert out["status"] == "saved"
    assert [s["category"] for s in out["saved"]] == [
        "insurance medical",
        "transport public",
    ]
    after = await preview(m, token)
    codes = {a["category"] for a in after["category_allocations"]}
    assert "insurance medical" not in codes and "transport public" not in codes
    assert [x["category"] for x in after["not_applicable_lines"]] == [
        "insurance medical",
        "transport public",
    ]
    assert after["fixed_obligations"] == []  # nothing invented as an obligation
    recurring = await call(m, token, "get_recurring_expenses")
    assert recurring["scheduled_recurring"] == []


# --- Test 7: the user's amount is protected ---------------------------------------------


async def test_fuel_stays_exactly_what_the_user_set(mcp, seed, connection):
    user, token = await person(mcp, seed)
    m = mcp.at(at(2))
    draft = await preview(
        m,
        token,
        budget_lines=[{"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}],
        spending_patterns=[
            {
                "line": "Fuel",
                "kind": "planned",
                "frequency": "weekly",
                "weekdays": ["friday"],
            }
        ],
    )
    fuel = line(draft, "my:Fuel")
    assert (fuel["amount"], fuel["source"]) == ("200.00", "set_by_you")
    await save(m, token, draft)
    await call(
        mcp.at(at(6)),
        token,
        "add_transaction",
        {"amount": "250.00", "budget_line": "Fuel", "idempotency_key": key()},
    )
    seen = await look(
        mcp.at(at(6)), token, connection, user, month=11, today=date(2026, 11, 6)
    )
    fuel_line = seen.line("my:Fuel")
    assert fuel_line["planned"] == "200.00"  # never raised from other lines
    assert fuel_line["remaining"] == "-50.00"  # the overspend stays visible
    again = await preview(mcp.at(at(6)), token)
    assert line(again, "my:Fuel")["amount"] == "200.00"


# --- Test 8: a frequency change is previewed, then saved ----------------------------------


async def test_changing_groceries_to_twice_a_month(mcp, seed, connection):
    user, token = await person(mcp, seed)
    m = mcp.at(at(2))
    lines = [{"label": "Groceries", "amount": 200, "replaces": ["groceries"]}]
    await save(
        m,
        token,
        await preview(m, token, budget_lines=lines, spending_patterns=WEDNESDAYS),
    )
    await call(
        mcp.at(at(4)),
        token,
        "add_transaction",
        {"amount": "48.00", "budget_line": "Groceries", "idempotency_key": key()},
    )
    ledger_before = (
        await connection.execute(
            text(
                "SELECT id, amount, category, spent_at FROM transactions WHERE user_id = :u"
            ),
            {"u": user.id},
        )
    ).all()

    m5 = mcp.at(at(5))
    twice = [
        {
            "line": "Groceries",
            "kind": "planned",
            "frequency": "times_per_month",
            "times_per_month": 2,
        }
    ]
    draft = await preview(m5, token, spending_patterns=twice)
    groceries = line(draft, "my:Groceries")
    assert groceries["amount"] == "200.00"  # the monthly total is unchanged
    assert [(p["date"], p["amount"]) for p in groceries["purchases"]] == [
        ("2026-11-08", "100.00"),
        ("2026-11-23", "100.00"),
    ]
    assert draft["changes"] == []  # no amount changes; only the dates
    # Nothing is persisted by a preview.
    status = await call(m5, token, "get_setup_status")
    stated = {x["category"]: x for x in status["spending"]["lines"]}
    assert stated["my:Groceries"]["pattern"] == "every Wednesday"
    assert set((await rows_of(connection, user, "my:Groceries"))) == {4, 11, 18, 25}

    await save(m5, token, draft)
    rows = await rows_of(connection, user, "my:Groceries")
    assert {d: p for d, (p, _m) in rows.items() if p} == {
        4: D("48.00"),  # the purchase recorded on the 4th keeps its money
        8: D("52.00"),
        23: D("100.00"),
    }
    status = await call(m5, token, "get_setup_status")
    stated = {x["category"]: x for x in status["spending"]["lines"]}
    assert (
        stated["my:Groceries"]["pattern"] == "2 times a month (dates proposed by MITA)"
    )
    ledger_after = (
        await connection.execute(
            text(
                "SELECT id, amount, category, spent_at FROM transactions WHERE user_id = :u"
            ),
            {"u": user.id},
        )
    ).all()
    assert ledger_after == ledger_before  # past transactions untouched


# --- Test 9: a returning user is asked only what is missing --------------------------------


async def test_a_returning_user_is_asked_only_what_is_missing(mcp, seed):
    user = await seed.user(tz=TZ, currency="EUR", income="2000.00", onboarded=True)
    await seed.profile(user, household_size=1)
    await seed.scheduled(
        user,
        category="transportation",
        amount=D("270.00"),
        merchant="Car loan",
        scheduled_date=date(2026, 11, 15),
    )
    await connection_exec(
        seed, user, "UPDATE users SET savings_goal = 500 WHERE id = :u"
    )
    m = mcp.at(at(2))
    token = m.token(user)
    status = await call(m, token, "get_setup_status")
    assert status["missing_fields"] == []
    assert status["known"]["monthly_net_income"] == "2000.00"
    assert status["known"]["monthly_savings_target"] == "500.00"
    assert status["recurring_expense_count"] == 1
    assert status["suggested_next_step"] == "describe_spending"
    assert status["spending"]["lines"] == []
    await call(
        m,
        token,
        "save_spending_patterns",
        {"patterns": [{"line": "Coffee and walks", "kind": "flexible"}]},
    )
    status = await call(m, token, "get_setup_status")
    assert status["suggested_next_step"] == "build_budget"
    assert [x["category"] for x in status["spending"]["lines"]] == [
        "my:Coffee and walks"
    ]


async def connection_exec(seed, user, sql):
    await seed.connection.execute(text(sql), {"u": user.id})


# --- Test 10: the whole authenticated flow -------------------------------------------------


async def test_the_whole_flow_through_mcp(mcp, seed, connection):
    user, token = await person(mcp, seed)
    other, other_token = await person(mcp, seed)
    m = mcp.at(at(2))
    await call(
        m,
        token,
        "add_recurring_expense",
        {
            "name": "Car loan",
            "amount": "270.00",
            "category": "transportation",
            "recurrence": "monthly",
            "day_of_month": 15,
            "idempotency_key": key(),
        },
    )
    saved = await call(
        m,
        token,
        "save_spending_patterns",
        {
            "patterns": [
                {
                    "line": "Groceries",
                    "kind": "planned",
                    "frequency": "weekly",
                    "weekdays": ["wednesday"],
                    "typical_amount": "50",
                },
                {"line": "Coffee and walks", "kind": "flexible"},
                {"line": "Medical insurance", "kind": "not_applicable"},
            ]
        },
    )
    assert [s["next_purchases"] for s in saved["saved"]][0] == [
        "2026-11-04",
        "2026-11-11",
        "2026-11-18",
        "2026-11-25",
    ]
    draft = await preview(
        m,
        token,
        budget_lines=[
            {"label": "Groceries", "amount": 200, "replaces": ["groceries"]},
            {"label": "Coffee and walks", "amount": 100},
        ],
    )
    assert line(draft, "my:Groceries")["spending_type"] == "planned"  # inherited
    assert line(draft, "my:Coffee and walks")["spending_type"] == "flexible"
    assert draft["fixed_obligations"][0]["name"] == "Car loan"
    await save(m, token, draft)

    seen = await look(m, token, connection, user, month=11, today=date(2026, 11, 2))
    assert seen.forecast["commitments_reserved"] == "270.00"
    car = next(b for b in seen.cal["bills"] if b["name"] == "Car loan")
    day4 = seen.day(4)
    assert [(p["category"], p["planned"]) for p in day4["purchases"]] == [
        ("my:Groceries", "50.00")
    ]
    assert D(day4["planned_scheduled"]) == D("50.00")  # only the real purchase
    assert D(day4["planned_flexible"]) > 0  # flexible guidance, shown apart

    m4 = mcp.at(at(4))
    await call(
        m4,
        token,
        "add_transactions",
        {
            "expenses": [
                {"amount": "47.80", "budget_line": "Groceries"},
                {"amount": "3.00", "budget_line": "Coffee and walks"},
                {
                    "amount": "60.00",
                    "category": "transportation",
                    "merchant": "BMW parts",
                },
            ],
            "idempotency_key": key(),
        },
    )
    after = await look(m4, token, connection, user, month=11, today=date(2026, 11, 4))
    assert after.forecast["total_spent"] == "110.80"
    assert (
        after.forecast["commitments_reserved"] == "270.00"
    )  # the part is not the loan
    assert (
        next(b for b in after.cal["bills"] if b["name"] == "Car loan")["paid"] == "0.00"
    )
    assert after.line("my:Groceries")["remaining"] == "152.20"
    coffee = after.line("my:Coffee and walks")
    assert coffee["remaining"] == "97.00"
    assert coffee["left_per_day"] == "3.59"  # 97 over 27 days, guidance only

    m15 = mcp.at(at(15))
    await call(
        m15,
        token,
        "add_transaction",
        {
            "amount": "270.00",
            "obligation_ref": car["obligation_ref"],
            "idempotency_key": key(),
        },
    )
    paid = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    assert (
        next(b for b in paid.cal["bills"] if b["name"] == "Car loan")["state"] == "paid"
    )
    assert paid.forecast["commitments_reserved"] == "0.00"

    # The other account sees none of it, and cannot use this user's refs.
    theirs = await call(
        mcp.at(at(15)), other_token, "get_calendar_month", {"year": 2026, "month": 11}
    )
    assert theirs["bills"] == [] and theirs["summary"]["total_spent"] == "0.00"
    refused = await mcp.at(at(15)).call(
        other_token,
        "add_transaction",
        {
            "amount": "1.00",
            "obligation_ref": car["obligation_ref"],
            "idempotency_key": key(),
        },
    )
    assert refused.is_error
    their_status = await call(mcp.at(at(15)), other_token, "get_setup_status")
    assert their_status["spending"]["lines"] == []


# --- approximate patterns: dates MITA proposes are said to be proposed --------------


async def test_fuel_about_once_a_week_gets_proposed_dates(mcp, seed, connection):
    """'€200 a month on fuel, I refuel about once a week for ~€50' gives a
    frequency and an amount, not a weekday: MITA proposes one date a week
    (4, 11, 18, 25 Nov), says they are proposed, and keeps €200 exact."""
    user, token = await person(mcp, seed)
    m = mcp.at(at(2))
    weekly = [
        {
            "line": "Fuel",
            "kind": "planned",
            "frequency": "weekly",
            "typical_amount": "50",
        }
    ]
    draft = await preview(
        m,
        token,
        budget_lines=[{"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}],
        spending_patterns=weekly,
    )
    fuel = line(draft, "my:Fuel")
    assert fuel["amount"] == "200.00"
    assert fuel["pattern"] == "about once a week (dates proposed by MITA)"
    assert fuel["purchase_dates_stated"] is False
    assert [
        (p["date"][-2:], p["amount"], p["proposed"]) for p in fuel["purchases"]
    ] == [
        ("04", "50.00", True),
        ("11", "50.00", True),
        ("18", "50.00", True),
        ("25", "50.00", True),
    ]
    await save(m, token, draft)
    seen = await look(m, token, connection, user, month=11, today=date(2026, 11, 2))
    cal_fuel = seen.line("my:Fuel")
    assert cal_fuel["purchase_dates_stated"] is False
    assert all(p["proposed"] for p in cal_fuel["purchases"])
    assert cal_fuel["next_purchase"]["date"] == "2026-11-04"


# --- daily intelligence for flexible budgets ----------------------------------------


async def test_flexible_budgets_keep_a_daily_guide_and_flag_fast_spending(
    mcp, seed, connection
):
    """Cigarettes €200 and Coffee and walks €100, both flexible. By 5 Nov the
    user spent €90 on cigarettes: within the month's €200, but at 90 / 5 =
    18.00 a day against 200 / 30 = 6.67 planned (2.70× the pace) — faster
    than its pace, not over its limit. The day's guide is what is left of
    each envelope over the 26 days left (5-30 Nov)."""
    user, token = await person(mcp, seed)
    m2 = mcp.at(at(2))
    draft = await preview(
        m2,
        token,
        budget_lines=[
            {"label": "Cigarettes", "amount": 200},
            {"label": "Coffee and walks", "amount": 100},
        ],
    )
    await save(m2, token, draft)
    m5 = mcp.at(at(5))
    await call(
        m5,
        token,
        "add_transaction",
        {"amount": "90.00", "budget_line": "Cigarettes", "idempotency_key": key()},
    )
    seen = await look(m5, token, connection, user, month=11, today=date(2026, 11, 5))
    cig = seen.line("my:Cigarettes")
    assert (cig["spent"], cig["remaining"]) == ("90.00", "110.00")
    assert (cig["pace_per_day"], cig["planned_per_day"]) == ("18.00", "6.67")
    assert cig["pace_status"] == "faster_than_pace"
    assert cig["left_per_day"] == "4.23"  # 110.00 / 26 days, the revised safe pace
    assert cig["days_until_exhausted"] == 6  # 110 / 18 at this pace
    coffee = seen.line("my:Coffee and walks")
    assert (coffee["pace_status"], coffee["left_per_day"]) == ("not_started", "3.85")
    # One source: the forecast's at-risk list names the same line, same pace.
    risk = {c["category"]: c for c in seen.forecast["categories_at_risk"]}
    assert risk["my:Cigarettes"]["daily_pace"] == "18.00"
    # The day's guide for flexible spending, shown on dates with no purchase.
    summary = seen.summary
    assert D(summary["flexible_left"]) == D(cig["remaining"]) + D(
        coffee["remaining"]
    ) + sum(
        D(x["remaining"])
        for x in seen.cal["categories"]
        if x["spending_type"] == "flexible"
        and x["category"] not in ("my:Cigarettes", "my:Coffee and walks")
    )
    per_day = sum(
        D(x["left_per_day"])
        for x in seen.cal["categories"]
        if x["spending_type"] == "flexible"
    )
    assert D(summary["flexible_per_day"]) == per_day
    assert summary["flexible_per_day_rounded"] == str(round(per_day))
    # A date ahead without a purchase holds no scheduled money — and still
    # its flexible share — never a fabricated purchase.
    day20 = seen.day(20)
    assert day20["planned_scheduled"] == "0.00" and D(day20["planned_flexible"]) > 0
    # Spending past the envelope is over its limit.
    await call(
        m5,
        token,
        "add_transaction",
        {"amount": "120.00", "budget_line": "Cigarettes", "idempotency_key": key()},
    )
    seen = await look(m5, token, connection, user, month=11, today=date(2026, 11, 5))
    cig = seen.line("my:Cigarettes")
    assert (cig["remaining"], cig["pace_status"]) == ("-10.00", "over_limit")
    assert cig["left_per_day"] == "0.00"


# --- F-12: money of a line that does not apply is shown, never moved silently --------


async def test_freed_money_is_shown_and_can_be_given_to_chosen_lines(mcp, seed):
    _user, token = await person(mcp, seed)
    m = mcp.at(at(2))
    lines = [
        {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]},
        {"label": "Cigarettes", "amount": 200},
    ]
    kept = await preview(m, token, budget_lines=lines)
    kept_by = {a["category"]: D(a["amount"]) for a in kept["category_allocations"]}
    excluded = [
        {"line": "Medical insurance", "kind": "not_applicable"},
        {"line": "transport public", "kind": "not_applicable"},
    ]
    draft = await preview(m, token, budget_lines=lines, spending_patterns=excluded)
    freed = draft["freed_money"]
    would = {x["category"]: x["amount_freed"] for x in draft["not_applicable_lines"]}
    assert would == {
        "insurance medical": format(kept_by["insurance medical"], "f"),
        "transport public": format(kept_by["transport public"], "f"),
    }
    assert (
        D(freed["total"]) == kept_by["insurance medical"] + kept_by["transport public"]
    )
    # Conserved to the cent: what other lines gained + what stays unallocated.
    gained = sum(D(x["amount"]) for x in freed["to_other_lines"])
    assert gained + D(freed["unallocated"]) == D(freed["total"])
    for x in freed["to_other_lines"]:
        now = D(line(draft, x["category"])["amount"])
        assert now - kept_by[x["category"]] == D(x["amount"])
    assert any("freed" in w and "budget_lines" in w for w in draft["warnings"])
    # The user's own amounts never move, and the exclusion is not persisted.
    assert line(draft, "my:Fuel")["amount"] == "200.00"
    again = await preview(m, token, budget_lines=lines)
    assert any(
        a["category"] == "insurance medical" for a in again["category_allocations"]
    )
    # Explicit redistribution: the user gives groceries an exact amount.
    chosen = await preview(
        m,
        token,
        budget_lines=lines
        + [{"label": "Groceries", "amount": 300, "replaces": ["groceries"]}],
        spending_patterns=excluded,
    )
    assert line(chosen, "my:Groceries")["amount"] == "300.00"
