"""The calendar's second layer — what MITA sends (MCP 2.11.0, component v5).

Owner briefs of 2026-11-13 and 2026-11-16
(docs/chatgpt-app/calendar-guidance-layer.md): 2.10.0 was financially right
and almost empty. A date now shows two layers that are never merged:

* activity — recorded spending, planned purchases from a stated pattern,
  bills on their due dates (``planned_scheduled``, ``day_lines``);
* the average left per day — on today and every date ahead: for all
  categories ``summary.flexible_per_day`` (the flexible budgets' left ÷ the
  days left, today included, never more than the safe average a day); under
  a flexible budget's filter, that budget's ``left_per_day``.

It is an arithmetic average, and is said to be one: MITA has no method that
personalizes a daily figure (income level, country, history and pay days do
not enter it — §3 of the doc), so it is never presented as a
recommendation. No new formula: it is the figure 2.7.0 already published.
The one addition is ``summary.flexible_per_day_capped`` — which branch of the
existing ``min(Σ left_per_day, max(0, safe_daily_limit))`` applied. These
tests pin the figures by hand, the branches of that flag, that nothing of it
reaches what is scheduled, that it is the same for any income or country,
and the reference profile's five kinds of money. What the component draws is
``test_calendar_rendering.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.mcp import MCP_SERVER_VERSION
from app.mcp.serializers import CALENDAR_METHOD
from app.mcp.tools.calendar import GET_DESCRIPTION
from app.mcp.ui import CALENDAR_DESCRIPTION, CALENDAR_URI
from tests_mcp.test_flexible_envelopes_calendar import (
    CAR,
    COFFEE,
    COFFEE_DAILY,
    FUN,
    GROCERIES,
    RESTAURANTS,
    call,
    key,
    noon,
    november,
    see,
)

D = Decimal
ZERO = D("0.00")
FLEXIBLE = (GROCERIES, CAR, FUN, RESTAURANTS)
CAPPED_WORDS = "(limited to the safe average a day)"
LAYER_WORDS = (
    "The calendar shows that average on today and each date ahead, apart from "
    "what is scheduled — it is not a purchase or a plan for any date."
)
AVERAGE_WORDS = "— what is left ÷ the days left, an average, not a recommendation."


def per_day(amount: Decimal, days: int) -> Decimal:
    return (amount / days).quantize(D("0.01"), ROUND_HALF_UP)


def guides_of(seen) -> dict:
    return {
        c["category"]: c["left_per_day"]
        for c in seen.data["categories"]
        if c["spending_type"] == "flexible"
    }


async def test_the_daily_guide_is_mitas_figure_for_the_money_with_no_dates(mcp, seed):
    """12 Nov: coffee every day (stated) is a planned purchase on its dates;
    Groceries, Car maintenance, Entertainment and Restaurants are flexible
    budgets. Their guide, by hand: 19 days from the 12th, today included."""
    _user, token, _draft = await november(mcp, seed, patterns=[COFFEE_DAILY])
    m12 = mcp.at(noon(12))
    for amount, line, day in (
        ("1.50", "Coffee", 3),
        ("1.50", "Coffee", 4),
        ("40.00", "Restaurants", 10),
    ):
        await call(
            m12,
            token,
            "add_transaction",
            {
                "amount": amount,
                "budget_line": line,
                "date": f"2026-11-{day:02d}",
                "idempotency_key": key(),
            },
        )
    seen = await see(m12, token)
    summary = seen.summary

    # each flexible budget: what is left on it ÷ the 19 days left
    assert guides_of(seen) == {
        GROCERIES: "16.84",  # 320.00 / 19
        CAR: "10.53",  # 200.00 / 19
        FUN: "5.26",  # 100.00 / 19
        RESTAURANTS: "3.16",  # 60.00 / 19 (40.00 spent)
    }
    for code in FLEXIBLE:
        line = seen.line(code)
        assert D(line["left_per_day"]) == per_day(max(ZERO, D(line["remaining"])), 19)
    # all categories: ONE aggregate — their sum, under the safe average
    assert summary["flexible_left"] == "680.00"
    assert summary["flexible_per_day"] == "35.79"
    assert summary["flexible_per_day_rounded"] == "36"
    assert summary["average_per_day"] == "40.11"  # 722.00 / 18 days after today
    assert summary["flexible_per_day_capped"] is False
    assert sum(D(g) for g in guides_of(seen).values()) == D("35.79")
    # a planned purchase and a bill have their money on their dates: no guide
    assert seen.line(COFFEE)["spending_type"] == "planned"
    assert seen.line(COFFEE)["left_per_day"] is None
    for c in seen.data["categories"]:
        if c["group"] == "commitment":
            assert c["left_per_day"] is None, c["category"]

    # The guide is never in what is scheduled: each date's planned_scheduled
    # is its purchases and its bills, to the cent, and the days ahead sum to
    # scheduled_after_today — 18 coffees and the two loans, nothing else.
    bills = {15: D("270.00"), 25: D("70.00")}
    for d in seen.data["days"]:
        day = int(d["date"][-2:])
        purchases = sum((D(p["planned"]) for p in d["purchases"]), ZERO)
        assert D(d["planned_scheduled"]) == purchases + bills.get(day, ZERO), day
    assert seen.day(15)["planned_scheduled"] == "271.50"
    assert summary["scheduled_after_today"] == "367.00"
    assert D(summary["scheduled_after_today"]) == sum(
        (
            D(d["planned_scheduled"])
            for d in seen.data["days"]
            if d["day_kind"] == "future"
        ),
        ZERO,
    )
    # and never handed to the component as a date's line
    for iso, entries in seen.payload["day_lines"].items():
        for line, scheduled, spent in entries:
            if line in FLEXIBLE:
                assert scheduled == "0.00" and D(spent) > 0, (iso, line)
    assert not any(
        line == RESTAURANTS
        for iso, entries in seen.payload["day_lines"].items()
        if iso != "2026-11-10"
        for line, _scheduled, _spent in entries
    )

    # what the model reads: an average, said to be one, and where it is drawn
    assert "about 35.79 a day on average " + AVERAGE_WORDS in seen.text
    assert LAYER_WORDS in seen.text
    assert CAPPED_WORDS not in seen.text
    assert "monthly limits with no dates" in seen.text


async def test_capped_says_when_the_guide_is_the_safe_average(mcp, seed):
    """2 Nov, no pattern stated: every line is a flexible budget — 29 days
    left, today included; the safe average divides by the 28 after today."""
    _user, token, _draft = await november(mcp, seed)
    m2 = mcp.at(noon(2))
    seen = await see(m2, token)
    assert guides_of(seen) == {
        GROCERIES: "11.03",  # 320 / 29
        CAR: "6.90",  # 200 / 29
        FUN: "3.45",
        RESTAURANTS: "3.45",
        COFFEE: "1.55",  # 45 / 29: no pattern, so a flexible budget
    }
    assert seen.summary["flexible_per_day"] == "26.38"  # their sum
    assert seen.summary["average_per_day"] == "27.32"  # 765.00 / 28
    assert seen.summary["flexible_per_day_capped"] is False

    # €300 of shopping nobody planned: the budgets still show 765.00, the
    # month as a whole has 465.00 after bills and savings — 16.61 a day.
    await call(
        m2,
        token,
        "add_transaction",
        {"amount": "300.00", "category": "shopping", "idempotency_key": key()},
    )
    seen = await see(m2, token)
    assert seen.summary["flexible_left"] == "765.00"
    assert sum(D(g) for g in guides_of(seen).values()) == D("26.38")  # unchanged
    assert seen.summary["average_per_day"] == "16.61"
    assert seen.summary["flexible_per_day"] == "16.61"
    assert seen.summary["flexible_per_day_capped"] is True
    assert "about 16.61 a day on average " + CAPPED_WORDS in seen.text

    # €1,500 more: nothing is safe to spend; the guide is 0, never negative.
    await call(
        m2,
        token,
        "add_transaction",
        {"amount": "1500.00", "category": "shopping", "idempotency_key": key()},
    )
    seen = await see(m2, token)
    assert D(seen.summary["average_per_day"]) < ZERO
    assert seen.summary["flexible_per_day"] == "0.00"
    assert seen.summary["flexible_per_day_rounded"] == "0"
    assert seen.summary["flexible_per_day_capped"] is True
    # each budget keeps its own guide: the user's lines are never donors
    assert guides_of(seen)[GROCERIES] == "11.03"
    # and still nothing of it is scheduled
    assert seen.summary["scheduled_after_today"] == "340.00"


async def test_no_guide_and_no_flag_for_a_month_that_ended_or_has_no_plan(mcp, seed):
    _user, token, _draft = await november(mcp, seed)
    december = mcp.at(datetime(2026, 12, 2, 10, 0, tzinfo=timezone.utc))
    ended = await see(december, token, 2026, 11)
    assert ended.data["month_position"] == "past"
    assert ended.summary["flexible_per_day"] is None
    assert ended.summary["flexible_per_day_capped"] is None
    assert all(c["left_per_day"] is None for c in ended.data["categories"])
    unplanned = await see(december, token, 2026, 12)
    assert unplanned.data["plan_status"] == "not_generated"
    assert unplanned.summary["flexible_per_day"] is None
    assert unplanned.summary["flexible_per_day_capped"] is None


async def test_a_month_ahead_gets_its_whole_budget_as_guidance_never_as_dates(
    mcp, seed
):
    """November seen from 20 October: nothing is spent yet, every day is left,
    so each guide is the monthly amount ÷ 30 — guidance, said so; no date
    holds it (2.9.0 drew the same 3.33 as each date's plan; that stays gone)."""
    _user, token, _draft = await november(mcp, seed)
    october = mcp.at(datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc))
    ahead = await see(october, token)
    assert ahead.data["month_position"] == "future"
    assert guides_of(ahead) == {
        GROCERIES: "10.67",
        CAR: "6.67",
        FUN: "3.33",
        RESTAURANTS: "3.33",
        COFFEE: "1.50",
    }
    assert ahead.summary["flexible_per_day"] == "25.50"
    assert ahead.summary["flexible_per_day_capped"] is False  # 765.00 / 30 = 25.50
    for d in ahead.data["days"]:
        day = int(d["date"][-2:])
        assert D(d["planned_scheduled"]) == {15: D("270.00"), 25: D("70.00")}.get(
            day, ZERO
        )
    assert all(
        line not in FLEXIBLE + (COFFEE,)
        for entries in ahead.payload["day_lines"].values()
        for line, _scheduled, _spent in entries
    )


def test_the_published_words_name_the_guide_as_a_layer_apart():
    assert MCP_SERVER_VERSION == "2.11.0"
    assert CALENDAR_URI == "ui://mita/financial-calendar-v5.html"
    assert "separate, labelled layer" in CALENDAR_METHOD
    assert (
        "never added to planned_scheduled or scheduled_after_today and never taken "
        "from left_to_spend" in CALENDAR_METHOD
    )
    assert (
        "the calendar shows that average on today and each date ahead, apart from "
        "what is scheduled, and it is never added to planned_scheduled"
        in " ".join(GET_DESCRIPTION.split())
    )
    assert "not personalized recommendations" in GET_DESCRIPTION
    assert "not a personalized recommendation" in CALENDAR_METHOD
    assert "hide the daily average" in CALENDAR_DESCRIPTION
    assert "never part of what is scheduled" in CALENDAR_DESCRIPTION


# --- an average, not a recommendation: the same for any income or country ---------------


async def test_the_daily_figure_is_an_average_the_same_for_any_income_or_country(
    mcp, seed
):
    """MITA has no method that personalizes a daily figure: income level,
    country, history and pay days enter none of left_per_day,
    flexible_per_day or average_per_day (docs/chatgpt-app/calendar-guidance-
    layer.md §3). Two accounts with the same plan and the same spending —
    one on 1,985 a month with no country stated, one on 6,000 in Bulgaria —
    get the same figures to the cent; what differs between people is what
    they spent and what they hold. So the figure is published, worded and
    drawn as an average, never as a recommendation."""
    _a, token_a, _ = await november(mcp, seed)
    _b, token_b, _ = await november(mcp, seed, income=6000)
    m2 = mcp.at(noon(2))
    await call(m2, token_b, "update_financial_profile", {"country": "BG"})
    a, b = await see(m2, token_a), await see(m2, token_b)
    assert b.summary["stated_monthly_income"] == "6000.00"
    assert a.summary["stated_monthly_income"] == "1985.00"
    for field in (
        "flexible_per_day",
        "flexible_per_day_capped",
        "average_per_day",
        "flexible_left",
    ):
        assert a.summary[field] == b.summary[field], field
    assert guides_of(a) == guides_of(b)
    assert "a day on average" in a.text and "not a recommendation" in a.text

    # What differs between people is what they did: 100.00 of groceries
    # lowers that budget's average and the aggregate, nobody else's.
    await call(
        m2,
        token_b,
        "add_transaction",
        {"amount": "100.00", "budget_line": "Groceries", "idempotency_key": key()},
    )
    b = await see(m2, token_b)
    assert guides_of(b)[GROCERIES] == "7.59"  # 220.00 / 29
    assert guides_of(a)[GROCERIES] == "11.03"  # 320.00 / 29, untouched
    assert {k: v for k, v in guides_of(b).items() if k != GROCERIES} == {
        k: v for k, v in guides_of(a).items() if k != GROCERIES
    }
    assert D(b.summary["flexible_per_day"]) < D(a.summary["flexible_per_day"])


# --- the reference profile: five kinds of money, never merged ----------------------------

# The owner's reference totals (fictional breakdown): income 2,500, savings
# 500, bills 505, flexible budgets 1,115, and 380 deliberately unallocated.
REFERENCE_LINES = [
    {"label": "Groceries", "amount": 320},
    {"label": "Car maintenance", "amount": 200},
    {"label": "Entertainment", "amount": 100},
    {"label": "Restaurants", "amount": 100},
    {"label": "Coffee", "amount": 45},
    {"label": "Fuel", "amount": 200},
    {"label": "Clothing", "amount": 150},
]
REFERENCE_BILLS = (
    ("Phone and internet", 45, "utilities", 5),
    ("Car loan", 270, "transportation", 15),
    ("Home insurance", 120, "insurance", 20),
    ("Laptop loan", 70, "other", 25),
)


async def test_the_reference_profile_keeps_its_five_kinds_of_money_apart(mcp, seed):
    m2 = mcp.at(noon(2))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m2.token(user)
    await call(
        m2,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 2500,
            "currency": "EUR",
            "timezone": "Europe/Sofia",
            "household_size": 1,
            "monthly_savings_target": 500,
            "setup_answers": [{"topic": "everyday_spending", "answer": "described"}],
        },
    )
    for name, amount, category, day in REFERENCE_BILLS:
        await call(
            m2,
            token,
            "add_recurring_expense",
            {
                "name": name,
                "amount": amount,
                "category": category,
                "recurrence": "monthly",
                "day_of_month": day,
                "idempotency_key": key(),
            },
        )
    draft = await call(
        m2,
        token,
        "preview_monthly_budget",
        {"month": "2026-11", "budget_lines": REFERENCE_LINES},
    )
    # the plan: savings 500 protected, the bills, the user's lines exactly,
    # and the 380 left unallocated — never spread into anything
    assert draft["savings_allocation"] == "500.00"
    assert draft["unallocated"] == "380.00"
    saved = await call(
        m2, token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
    )
    assert saved["status"] == "saved"

    m12 = mcp.at(noon(12))
    await call(
        m12,
        token,
        "add_transaction",
        {
            "amount": "50.00",
            "budget_line": "Groceries",
            "date": "2026-11-10",
            "idempotency_key": key(),
        },
    )
    seen = await see(m12, token)
    s = seen.summary
    # 1. protected savings and 5. the unallocated reserve: in no spendable figure
    assert s["total_planned"] == "2120.00"  # 500 + 505 + 1,115: the 380 is on no line
    assert D("2500.00") - D(s["total_planned"]) == D("380.00")
    assert s["set_aside_planned"] == "500.00" and s["savings_set_aside"] == "500.00"
    # 2. the bills: on their due dates, held until a linked payment
    assert s["commitments_planned"] == "505.00"
    assert s["commitments_reserved"] == "505.00"
    assert {b["date"][-2:]: b["amount"] for b in seen.data["bills"]} == {
        "05": "45.00",
        "15": "270.00",
        "20": "120.00",
        "25": "70.00",
    }
    assert all(b["paid"] == "0.00" for b in seen.data["bills"])
    assert s["scheduled_after_today"] == "460.00"  # 270 + 120 + 70: bills only
    # 3./4. the flexible budgets: monthly limits on no date, the expense on its
    # date only, every one an average of what it still holds
    flexible = [c for c in seen.data["categories"] if c["spending_type"] == "flexible"]
    assert sum(D(c["planned"]) for c in flexible) == D("1115.00")
    assert all(c["purchases"] == [] and c["next_purchase"] is None for c in flexible)
    assert seen.line("my:Groceries")["remaining"] == "270.00"
    assert seen.line("my:Car maintenance")["remaining"] == "200.00"  # irregular:
    # nothing invented for it — no purchase, no date, only its month
    on_dates = {
        line
        for entries in seen.payload["day_lines"].values()
        for line, _scheduled, _spent in entries
    }
    assert on_dates & {c["category"] for c in flexible} == {"my:Groceries"}
    assert seen.day_lines(10)["my:Groceries"] == ("0.00", "50.00")
    for c in flexible:
        assert D(c["left_per_day"]) == per_day(D(c["remaining"]), 19), c["category"]
    # the aggregate is what the budgets hold ÷ the 19 days, under the safe
    # average (1,065.00 left after bills and savings ÷ 18 days after today)
    assert s["flexible_left"] == "1065.00"
    assert s["left_to_spend"] == "1065.00"
    assert s["average_per_day"] == "59.17"
    assert s["flexible_per_day"] == "56.05" and s["flexible_per_day_capped"] is False
    assert D(s["flexible_per_day"]) * 19 <= D(s["flexible_left"]) + D("0.19")
    # never double counted: what is scheduled ahead holds no average, and
    # reading the month changes nothing recorded
    assert D(s["scheduled_after_today"]) == sum(
        (
            D(d["planned_scheduled"])
            for d in seen.data["days"]
            if d["day_kind"] == "future"
        ),
        ZERO,
    )
    again = await see(m12, token)
    assert again.summary == s and again.data["days"] == seen.data["days"]
    assert s["total_spent"] == "50.00"
