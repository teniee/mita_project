"""A budget is not a schedule: flexible monthly budgets in the calendar.

Owner brief of 2026-11-11 (docs/chatgpt-app/flexible-envelopes-calendar.md),
after MITA MCP 2.9.0 on staging showed, for November 2026:

    Groceries        320 a month  ->  10.67 on every date
    Car maintenance  200 a month  ->   6.67 on every date
    Entertainment    100 a month  ->   3.33 / 3.34 on every date
    Restaurants      100 a month  ->   3.33 / 3.34 on every date

Nobody scheduled a restaurant visit a day. A flexible budget is a monthly
limit with no dates; MITA's plan rows keep its money evenly over the month
only as bookkeeping, and the calendar handed those rows to its component as
each date's plan. Since 2.10.0 a date holds only what belongs to it:

* recorded spending, on the date it was recorded;
* a saved bill, on its due date — never paid by itself;
* a planned purchase, on the date a pattern the user stated gives;
* nothing of a flexible budget: its amount, spending, remainder and daily
  guidance are the line's and the month's, said to be guidance.

Every test drives the real MCP tools on PostgreSQL. The month is the brief's
November 2026 (Europe/Sofia, EUR, 30 days): income 1,985, savings 500, a car
loan of 270 on the 15th and a laptop loan of 70 on the 25th, the user's own
lines Groceries 320, Car maintenance 200, Entertainment 100, Restaurants 100
and Coffee 45 — which leaves exactly 380 that the user deliberately did not
allocate. All of it is fictional.
"""

from __future__ import annotations

import calendar as calendar_module
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional

import pytest
from sqlalchemy import text

from app.mcp.queries.calendar import build_calendar
from app.mcp.serializers import WIDGET_PAYLOAD_VERSION
from app.mcp.ui import CALENDAR_URI, calendar_html
from tests_mcp.conftest import structured

D = Decimal
ZERO = D("0.00")
TZ = "Europe/Sofia"
NOV = (2026, 11)

GROCERIES = "my:Groceries"
CAR = "my:Car maintenance"
FUN = "my:Entertainment"
RESTAURANTS = "my:Restaurants"
COFFEE = "my:Coffee"
ENVELOPES = {GROCERIES: "320.00", CAR: "200.00", FUN: "100.00", RESTAURANTS: "100.00"}
# What 2.9.0 put on every date for them: the monthly limit ÷ 30 days.
DAILY_SHARES = {"10.66", "10.67", "6.66", "6.67", "3.33", "3.34"}

LINES = [
    {"label": "Groceries", "amount": 320},
    {"label": "Car maintenance", "amount": 200},
    {"label": "Entertainment", "amount": 100},
    {"label": "Restaurants", "amount": 100},
    {"label": "Coffee", "amount": 45},
]
COFFEE_DAILY = {
    "line": "Coffee",
    "kind": "planned",
    "frequency": "daily",
    "typical_amount": "1.50",
}
GROCERIES_WEDNESDAYS = {
    "line": "Groceries",
    "kind": "planned",
    "frequency": "weekly",
    "weekdays": ["wednesday"],
}


def noon(day: int, month: int = 11, year: int = 2026) -> datetime:
    """Noon in Sofia (10:00 UTC in winter) on that date."""
    return datetime(year, month, day, 10, 0, tzinfo=timezone.utc)


def key() -> str:
    return uuid.uuid4().hex


async def call(m, token, tool, arguments=None):
    return structured(await m.call(token, tool, arguments or {}))


async def november(
    mcp,
    seed,
    *,
    patterns: Optional[List[dict]] = None,
    lines: Optional[List[dict]] = None,
    income: int = 1985,
    bills: bool = True,
):
    """The brief's account, its reviewed November saved on 2 Nov. Returns
    ``(user, token, draft)``."""
    m = mcp.at(noon(2))
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
            "monthly_savings_target": 500,
            # the user said what they spend on: MITA budgets only those
            # lines and leaves the rest of the money unallocated
            "setup_answers": [{"topic": "everyday_spending", "answer": "described"}],
        },
    )
    if bills:
        for name, amount, category, day in (
            ("Car loan", 270, "transportation", 15),
            ("Laptop loan", 70, "other", 25),
        ):
            await call(
                m,
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
    arguments = {"month": "2026-11", "budget_lines": lines or LINES}
    if patterns:
        arguments["spending_patterns"] = patterns
    draft = await call(m, token, "preview_monthly_budget", arguments)
    saved = await call(
        m, token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
    )
    assert saved["status"] == "saved"
    return user, token, draft


class Month:
    """One month as both calendar tools return it: the data the model reads
    and the payload only the component gets."""

    def __init__(self, data: dict, view: dict, payload: dict, text_shown: str):
        self.data = data
        self.view = view
        self.payload = payload
        self.text = text_shown

    @property
    def summary(self) -> dict:
        return self.data["summary"]

    def day(self, day: int) -> dict:
        return next(x for x in self.data["days"] if int(x["date"][-2:]) == day)

    def line(self, code: str) -> dict:
        return next(x for x in self.data["categories"] if x["category"] == code)

    def day_lines(self, day: int) -> Dict[str, tuple]:
        """``{line: (scheduled, spent)}`` the component draws for a date."""
        iso = self.day(day)["date"]
        return {
            entry[0]: (entry[1], entry[2])
            for entry in self.payload["day_lines"].get(iso, [])
        }

    def group(self, code: str) -> str:
        return self.line(code)["group"]

    # --- what the component puts in a date's cell --------------------------
    # The component's rule (financial_calendar.html, cellModel): a begun
    # date shows what was spent, a date ahead what is scheduled; with a
    # category filter, the same two things for that line alone.

    def cell(self, day: int, line: Optional[str] = None) -> Optional[str]:
        """The amount in a date's cell, or None for an empty cell."""
        d = self.day(day)
        if line is None:
            amount = d["spent"] if d["day_kind"] != "future" else d["planned_scheduled"]
        else:
            scheduled, spent = self.day_lines(day).get(line, ("0.00", "0.00"))
            amount = spent if d["day_kind"] != "future" else scheduled
        return amount if amount is not None and D(amount) > 0 else None


async def see(m, token, year: int = 2026, month: int = 11) -> Month:
    args = {"year": year, "month": month}
    data_result = await m.call(token, "get_calendar_month", args)
    view_result = await m.call(token, "show_financial_calendar", args)
    data = structured(data_result)
    payload = view_result.meta["mita/calendar"]
    # Both tools hand the component the same month.
    assert data_result.meta["mita/calendar"] == payload
    assert payload["month"] == data
    return Month(data, structured(view_result), payload, view_result.content[0].text)


async def stored_rows(connection, user, year: int = 2026, month: int = 11) -> dict:
    """``{(day, line): planned_amount}`` of the month, as stored."""
    last = calendar_module.monthrange(year, month)[1]
    result = await connection.execute(
        text(
            "SELECT date, category, planned_amount FROM daily_plan "
            "WHERE user_id = :u AND date >= :start AND date <= :end "
            "ORDER BY date, category"
        ),
        {
            "u": user.id,
            "start": datetime(year, month, 1),
            "end": datetime(year, month, last, 23, 59, 59),
        },
    )
    return {
        (r["date"].day, r["category"]): D(str(r["planned_amount"]))
        for r in result.mappings()
    }


# --- the defect of 2.9.0, reproduced ------------------------------------------------


async def test_november_2026_no_flexible_budget_is_on_any_date(mcp, seed, connection):
    """THE REGRESSION (tests A-D of the brief). On MITA MCP 2.9.0 this test
    fails: the component's month payload carried, for each of the four
    budgets, its stored daily share on all 30 dates — 10.67 for Groceries,
    6.67 for Car maintenance, 3.33 / 3.34 for Entertainment and Restaurants —
    and the category filter drew it as that date's plan; every date ahead
    was ``planned``. Nothing but the two loans is scheduled in this month."""
    user, token, _draft = await november(mcp, seed)
    seen = await see(mcp.at(noon(2)), token)

    # The storage has not changed: each monthly limit is still kept evenly
    # over the 30 days, to the cent — bookkeeping the calendar must not show.
    rows = await stored_rows(connection, user)
    for line, monthly in ENVELOPES.items():
        shares = [amount for (_day, code), amount in rows.items() if code == line]
        assert len(shares) == 30 and sum(shares) == D(monthly)
        assert {format(s, "f") for s in shares} <= DAILY_SHARES

    for line, monthly in ENVELOPES.items():
        budget = seen.line(line)
        # the monthly allocation, what was spent and what is left stay visible
        assert budget["spending_type"] == "flexible"
        assert (budget["planned"], budget["spent"], budget["remaining"]) == (
            monthly,
            "0.00",
            monthly,
        )
        assert budget["purchases"] == [] and budget["next_purchase"] is None
        for day in range(1, 31):
            # A-D: zero fabricated daily purchases, on any date, in any view
            assert line not in seen.day_lines(day), (line, day)
            assert seen.cell(day, line) is None, (line, day)
            assert not any(p["category"] == line for p in seen.day(day)["purchases"])

    # No date carries a daily share anywhere the component reads a date from.
    drawn = {
        amount
        for entries in seen.payload["day_lines"].values()
        for _line, scheduled, spent in entries
        for amount in (scheduled, spent)
    }
    assert not drawn & DAILY_SHARES
    # The dates: the two loans on their due dates, every other date empty.
    scheduled = {
        int(d["date"][-2:]): d["planned_scheduled"]
        for d in seen.data["days"]
        if D(d["planned_scheduled"]) > 0
    }
    assert scheduled == {15: "270.00", 25: "70.00"}
    for day in range(3, 31):  # the dates ahead of 2 Nov
        d = seen.day(day)
        assert d["state"] == "free", d["date"]  # 2.9.0: "planned"
        assert d["purchases"] == [] and d["spent"] is None
        assert seen.cell(day) == scheduled.get(day), d["date"]
    assert seen.summary["scheduled_after_today"] == "340.00"


# --- E, F: coffee ---------------------------------------------------------------------


async def test_confirmed_daily_coffee_is_a_planned_purchase_once_per_date(mcp, seed):
    """E. The user said: a coffee every day, about 1.50. That IS a schedule:
    45.00 over 30 dates, 1.50 each — once per date, in every view."""
    _user, token, draft = await november(mcp, seed, patterns=[COFFEE_DAILY])
    coffee_draft = next(
        a for a in draft["category_allocations"] if a["category"] == COFFEE
    )
    assert coffee_draft["spending_type"] == "planned"
    assert coffee_draft["pattern_source"] == "user_confirmed"
    assert coffee_draft["pattern"] == "every day"

    seen = await see(mcp.at(noon(2)), token)
    coffee = seen.line(COFFEE)
    assert (coffee["spending_type"], coffee["pattern"]) == ("planned", "every day")
    assert coffee["purchase_dates_stated"] is True
    assert (coffee["planned"], coffee["left_per_day"]) == ("45.00", None)
    assert [(p["date"], p["planned"]) for p in coffee["purchases"]] == [
        (f"2026-11-{day:02d}", "1.50") for day in range(1, 31)
    ]
    assert sum(D(p["planned"]) for p in coffee["purchases"]) == D("45.00")
    for day in range(1, 31):
        d = seen.day(day)
        # exactly one purchase event of 1.50, and exactly one drawn amount
        assert [(p["category"], p["planned"]) for p in d["purchases"]] == [
            (COFFEE, "1.50")
        ]
        assert seen.day_lines(day)[COFFEE][0] == "1.50"
        assert D(d["planned_scheduled_everyday"]) == D("1.50")
        bills = {15: D("270.00"), 25: D("70.00")}.get(day, ZERO)
        assert D(d["planned_scheduled"]) == D("1.50") + bills
    # All categories on a date ahead = the coffee (+ a loan): nothing doubled,
    # and no flexible budget beside it.
    assert seen.cell(20) == "1.50" and seen.cell(20, COFFEE) == "1.50"
    assert seen.cell(15) == "271.50"
    assert seen.day(20)["state"] == "planned"
    for line in ENVELOPES:
        assert all(line not in seen.day_lines(day) for day in range(1, 31))
    assert seen.summary["scheduled_after_today"] == "382.00"  # 28 × 1.50 + 340


async def test_coffee_without_a_stated_pattern_has_no_daily_purchases(mcp, seed):
    """F. The same 45.00 with nothing said about when: a monthly limit. No
    daily purchase, and 1.50 on no date."""
    _user, token, draft = await november(mcp, seed)
    coffee_draft = next(
        a for a in draft["category_allocations"] if a["category"] == COFFEE
    )
    assert coffee_draft["spending_type"] == "flexible"
    assert coffee_draft["pattern_source"] == "mita_default"

    seen = await see(mcp.at(noon(2)), token)
    coffee = seen.line(COFFEE)
    assert (coffee["spending_type"], coffee["planned"]) == ("flexible", "45.00")
    assert coffee["purchases"] == [] and coffee["pattern"] is None
    for day in range(1, 31):
        d = seen.day(day)
        assert d["purchases"] == []
        assert COFFEE not in seen.day_lines(day)
        assert seen.cell(day, COFFEE) is None
    assert seen.cell(20) is None  # an empty date
    assert seen.day(20)["state"] == "free"
    # ...and it is still a budget: 45.00 left, about 1.55 a day as guidance
    # (45.00 over the 29 days from the 2nd).
    assert (coffee["remaining"], coffee["left_per_day"]) == ("45.00", "1.55")
    assert coffee["planned_per_day"] == "1.50"  # an analytical pace, on no date


# --- G: a weekly purchase ---------------------------------------------------------------


async def test_weekly_groceries_fall_on_the_wednesdays_not_on_every_day(mcp, seed):
    """G. Groceries every Wednesday: 320.00 over the four Wednesdays of
    November 2026 — 80.00 each — and nothing on any other date."""
    _user, token, _draft = await november(mcp, seed, patterns=[GROCERIES_WEDNESDAYS])
    seen = await see(mcp.at(noon(2)), token)
    groceries = seen.line(GROCERIES)
    assert groceries["spending_type"] == "planned"
    assert groceries["pattern"] == "every Wednesday"
    assert [
        (p["date"], p["planned"], p["proposed"]) for p in groceries["purchases"]
    ] == [
        ("2026-11-04", "80.00", False),
        ("2026-11-11", "80.00", False),
        ("2026-11-18", "80.00", False),
        ("2026-11-25", "80.00", False),
    ]
    wednesdays = {4, 11, 18, 25}
    for day in range(1, 31):
        assert seen.cell(day, GROCERIES) == ("80.00" if day in wednesdays else None)
        assert (GROCERIES in seen.day_lines(day)) == (day in wednesdays)
    assert seen.cell(11) == "80.00" and seen.cell(12) is None
    assert seen.cell(25) == "150.00"  # the shop and the laptop loan
    assert seen.day(11)["state"] == "planned" and seen.day(12)["state"] == "free"


# --- H: what was really spent ------------------------------------------------------------


async def test_a_real_restaurant_expense_stays_on_its_date_and_invents_nothing(
    mcp, seed, connection
):
    """H. 40.00 at a restaurant on 10 Nov against the 100.00 budget: one
    expense on the 10th, 60.00 left, about 2.86 a day as guidance (60.00 over
    the 21 days from the 10th) — and still no restaurant on any other date."""
    user, token, _draft = await november(mcp, seed)
    m10 = mcp.at(noon(10))
    recorded = await call(
        m10,
        token,
        "add_transaction",
        {
            "amount": "40.00",
            "budget_line": "Restaurants",
            "merchant": "Bistro",
            "idempotency_key": key(),
        },
    )
    assert recorded["status"] == "recorded"
    seen = await see(m10, token)

    restaurants = seen.line(RESTAURANTS)
    assert (
        restaurants["planned"],
        restaurants["spent"],
        restaurants["remaining"],
    ) == ("100.00", "40.00", "60.00")
    assert (restaurants["left_per_day"], restaurants["left_per_day_rounded"]) == (
        "2.86",
        "3",
    )
    # 40.00 in ten days is 4.00 a day against an even 3.33: faster than its
    # pace (1.2×), still inside the limit — analysis, not an overspend
    assert restaurants["pace_status"] == "faster_than_pace"
    assert (restaurants["pace_per_day"], restaurants["planned_per_day"]) == (
        "4.00",
        "3.33",
    )

    # the 10th: the expense, exactly once
    day10 = seen.day(10)
    assert (day10["spent"], day10["spent_everyday"]) == ("40.00", "40.00")
    spending = {
        line: amounts
        for line, amounts in seen.day_lines(10).items()
        if seen.group(line) != "set_aside"  # the savings slice is shown apart
    }
    assert spending == {RESTAURANTS: ("0.00", "40.00")}
    assert seen.cell(10) == "40.00" and seen.cell(10, RESTAURANTS) == "40.00"
    # spending inside a monthly limit is not over, and the 10th had no plan
    # of its own to be "within"
    assert day10["state"] == "unplanned" and day10["everyday_left"] is None
    assert day10["purchases"] == []
    # every other date: nothing of the restaurant budget
    for day in range(1, 31):
        if day != 10:
            assert RESTAURANTS not in seen.day_lines(day)
            assert seen.cell(day, RESTAURANTS) is None
    assert all(seen.day(day)["state"] == "free" for day in range(11, 31))
    assert sum(D(x["spent"]) for x in seen.data["days"] if x["spent"]) == D("40.00")
    # exactly one transaction exists: nothing was fabricated in the ledger
    count = await connection.execute(
        text(
            "SELECT count(*), coalesce(sum(amount), 0) FROM transactions "
            "WHERE user_id = :u AND deleted_at IS NULL"
        ),
        {"u": user.id},
    )
    assert tuple(count.one()) == (1, D("40.00"))


async def test_the_whole_budget_on_one_day_is_not_over(mcp, seed):
    """A flexible budget may be spent on a single day: 100.00 at a
    restaurant on the 10th uses the month's limit, exactly — not over."""
    _user, token, _draft = await november(mcp, seed)
    m10 = mcp.at(noon(10))
    await call(
        m10,
        token,
        "add_transaction",
        {"amount": "100.00", "budget_line": "Restaurants", "idempotency_key": key()},
    )
    seen = await see(m10, token)
    restaurants = seen.line(RESTAURANTS)
    assert (restaurants["remaining"], restaurants["left_per_day"]) == ("0.00", "0.00")
    assert seen.day(10)["state"] == "unplanned"
    assert not any(d["state"] == "over" for d in seen.data["days"])
    assert seen.cell(10, RESTAURANTS) == "100.00"
    # One euro more is beyond the month's limit. The limit is the month's,
    # so that is what says so: the line is over by exactly 1.00. (Whether the
    # date is also marked over is the plan rows' date-level comparison, which
    # 2.10.0 does not change: docs/chatgpt-app/flexible-envelopes-calendar.md
    # → "Known limits".)
    await call(
        m10,
        token,
        "add_transaction",
        {"amount": "1.00", "budget_line": "Restaurants", "idempotency_key": key()},
    )
    seen = await see(m10, token)
    restaurants = seen.line(RESTAURANTS)
    assert (restaurants["pace_status"], restaurants["remaining"]) == (
        "over_limit",
        "-1.00",
    )
    assert restaurants["left_per_day"] == "0.00"
    assert seen.day(10)["state"] != "within"
    assert seen.cell(10, RESTAURANTS) == "101.00"


# --- I: fixed obligations ----------------------------------------------------------------


async def test_loans_sit_on_their_due_dates_and_are_never_paid_by_themselves(
    mcp, seed, connection
):
    """I. The car loan (270.00) on the 15th and the laptop loan (70.00) on
    the 25th, in full, on no other date. A due date passing pays nothing;
    only the expense the user says paid it does."""
    user, token, _draft = await november(mcp, seed)
    seen = await see(mcp.at(noon(2)), token)
    assert [
        (b["name"], b["date"], b["amount"], b["state"]) for b in seen.data["bills"]
    ] == [
        ("Car loan", "2026-11-15", "270.00", "later"),
        ("Laptop loan", "2026-11-25", "70.00", "later"),
    ]
    for day in range(1, 31):
        expected = {15: "270.00", 25: "70.00"}.get(day)
        assert seen.cell(day) == expected
        assert (D(seen.day(day)["planned_scheduled"]) > 0) == (expected is not None)
        # a loan is not an everyday purchase
        assert seen.day(day)["planned_scheduled_everyday"] == "0.00"
    assert seen.summary["commitments_reserved"] == "340.00"

    # 16 Nov, nothing recorded: the loan is overdue, not paid, and no expense
    # was invented for it.
    late = await see(mcp.at(noon(16)), token)
    car = next(b for b in late.data["bills"] if b["name"] == "Car loan")
    assert (car["state"], car["paid"], car["outstanding"]) == (
        "overdue",
        "0.00",
        "270.00",
    )
    assert late.day(15)["spent"] == "0.00" and late.summary["total_spent"] == "0.00"
    transactions = await connection.execute(
        text("SELECT count(*) FROM transactions WHERE user_id = :u"), {"u": user.id}
    )
    assert transactions.scalar() == 0

    # The user says which expense paid it: only then is it paid.
    m16 = mcp.at(noon(16))
    await call(
        m16,
        token,
        "add_transaction",
        {
            "amount": "270.00",
            "obligation_ref": car["obligation_ref"],
            "date": "2026-11-15",
            "idempotency_key": key(),
        },
    )
    paid = await see(m16, token)
    car = next(b for b in paid.data["bills"] if b["name"] == "Car loan")
    assert (car["state"], car["paid"], car["paid_dates"]) == (
        "paid",
        "270.00",
        ["2026-11-15"],
    )
    assert paid.summary["commitments_reserved"] == "70.00"  # the laptop loan
    assert paid.day(15)["spent"] == "270.00"
    assert paid.day(15)["spent_everyday"] == "0.00"  # a bill, not everyday money


# --- J: all categories and each filter are one set of events --------------------------------


async def test_all_categories_is_the_sum_of_the_filtered_views(mcp, seed):
    """J. A filter never changes what an amount means: on every date, what
    the lines show one by one adds up to what "All categories" shows — for
    what is scheduled and for what was spent. With daily coffee, weekly
    groceries, both loans and real expenses in the month."""
    _user, token, _draft = await november(
        mcp, seed, patterns=[COFFEE_DAILY, GROCERIES_WEDNESDAYS]
    )
    m12 = mcp.at(noon(12))
    for amount, line, day in (
        ("78.40", "Groceries", 4),
        ("1.50", "Coffee", 4),
        ("40.00", "Restaurants", 10),
        ("12.00", "Entertainment", 10),
        ("85.00", "Groceries", 11),
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
    spending_lines = [
        c["category"] for c in seen.data["categories"] if c["group"] != "set_aside"
    ]
    for day in range(1, 31):
        d = seen.day(day)
        lines = seen.day_lines(day)
        scheduled = sum(
            (D(s) for code, (s, _spent) in lines.items() if code in spending_lines),
            ZERO,
        )
        spent = sum((D(sp) for _code, (_s, sp) in lines.items()), ZERO)
        assert scheduled == D(d["planned_scheduled"]), d["date"]
        if d["spent"] is not None:
            assert spent == D(d["spent"]), d["date"]
        # the cells: every filter's cell adds up to the unfiltered cell
        cells = sum((D(seen.cell(day, code) or "0") for code in spending_lines), ZERO)
        assert cells == D(seen.cell(day) or "0"), d["date"]
    # the month too: each line's dates add up to its spending
    for code in spending_lines:
        total = sum(
            (D(seen.day_lines(day).get(code, ("0", "0"))[1]) for day in range(1, 31)),
            ZERO,
        )
        assert total == D(seen.line(code)["spent"]), code
    # hand-checked dates
    assert seen.cell(4) == "79.90" and seen.cell(4, GROCERIES) == "78.40"
    assert seen.cell(10) == "52.00" and seen.cell(10, RESTAURANTS) == "40.00"
    assert seen.cell(10, FUN) == "12.00" and seen.cell(10, COFFEE) is None
    # The 11th's shop of 85.00 used its own 80.00, the 1.60 left from the 4th
    # and 3.40 of the 18th: the next shop holds 76.60, plus the coffee.
    assert seen.cell(18, GROCERIES) == "76.60" and seen.cell(18) == "78.10"
    assert seen.cell(20) == "1.50" and seen.cell(20, RESTAURANTS) is None


# --- K: the contract ------------------------------------------------------------------------


async def test_the_contract_keeps_the_four_kinds_apart(mcp, seed, connection):
    """K. In what MITA serializes, a transaction, a planned purchase, a bill
    and a flexible budget's guidance are four different things: each has its
    own field, and no amount appears under two of them."""
    user, token, _draft = await november(
        mcp, seed, patterns=[COFFEE_DAILY, GROCERIES_WEDNESDAYS]
    )
    m10 = mcp.at(noon(10))
    await call(
        m10,
        token,
        "add_transaction",
        {"amount": "40.00", "budget_line": "Restaurants", "idempotency_key": key()},
    )
    seen = await see(m10, token)
    rows = await stored_rows(connection, user)
    bills_due = {15: D("270.00"), 25: D("70.00")}
    flexible = [c for c in seen.data["categories"] if c["spending_type"] == "flexible"]
    assert {c["category"] for c in flexible} == {CAR, FUN, RESTAURANTS}

    for d in seen.data["days"]:
        day = int(d["date"][-2:])
        # what the plan rows hold = what is scheduled + the flexible share
        assert D(d["planned"]) == D(d["planned_scheduled"]) + D(d["planned_flexible"])
        # what is scheduled = the planned purchases + the bills due, nothing else
        purchases = sum((D(p["planned"]) for p in d["purchases"]), ZERO)
        assert D(d["planned_scheduled"]) == purchases + bills_due.get(day, ZERO)
        assert D(d["planned_scheduled_everyday"]) == purchases
        # a planned purchase is only ever a planned line's
        assert {p["category"] for p in d["purchases"]} <= {COFFEE, GROCERIES}
        # the flexible share is exactly the flexible lines' stored rows: the
        # bookkeeping, published under one name and never as a plan
        share = sum(
            (rows.get((day, c["category"]), ZERO) for c in flexible),
            ZERO,
        )
        assert D(d["planned_flexible"]) == share
        # spending is the ledger: only the begun dates have any
        assert (d["spent"] is None) == (d["day_kind"] == "future")
    assert seen.day(10)["spent"] == "40.00"
    assert all(
        d["spent"] in (None, "0.00") for d in seen.data["days"] if d != seen.day(10)
    )

    summary = seen.summary
    future = [d for d in seen.data["days"] if d["day_kind"] == "future"]
    assert D(summary["scheduled_after_today"]) == sum(
        (D(d["planned_scheduled"]) for d in future), ZERO
    )
    assert D(summary["planned_after_today"]) == sum(
        (D(d["planned"]) for d in future), ZERO
    )
    # guidance is the month's and the line's: what is left ÷ the days left
    assert D(summary["flexible_left"]) == sum(
        (D(c["remaining"]) for c in flexible), ZERO
    )
    assert D(summary["flexible_per_day"]) == sum(
        (D(c["left_per_day"]) for c in flexible), ZERO
    )
    for c in flexible:
        assert D(c["left_per_day"]) == (D(c["remaining"]) / 21).quantize(D("0.01"))
        assert D(c["planned_per_day"]) == (D(c["planned"]) / 30).quantize(D("0.01"))

    # The component's payload: version 2, a date's lines carry what is
    # scheduled — a flexible budget only where something was spent from it.
    assert seen.payload["version"] == WIDGET_PAYLOAD_VERSION == 2
    for iso, entries in seen.payload["day_lines"].items():
        for line, scheduled, spent in entries:
            if seen.line(line)["spending_type"] == "flexible":
                assert scheduled == "0.00" and D(spent) > 0, (iso, line)
            assert D(scheduled) > 0 or D(spent) > 0
    # What the model reads says so in words, and names no per-date share.
    assert "monthly limits with no dates" in seen.text
    assert "as guidance" in seen.text
    assert "each date also has its own plan" not in seen.text
    assert seen.view["summary"] == summary


async def test_the_published_schema_says_what_each_amount_is(mcp, seed):
    """K. The descriptions ChatGPT reads are the contract: the flexible
    share is named bookkeeping, the guidance guidance, and only
    ``planned_scheduled`` is offered as a date's plan."""
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    get = tools["get_calendar_month"]
    schema = get.output_schema
    day = schema["$defs"]["CalendarDayOut"]["properties"]
    line = schema["$defs"]["CalendarLineOut"]["properties"]
    summary = schema["$defs"]["CalendarSummaryOut"]["properties"]
    assert "Bookkeeping, not a schedule" in day["planned_flexible"]["description"]
    assert "never a purchase" in day["planned_flexible"]["description"]
    assert (
        "only amount to present as planned" in day["planned_scheduled"]["description"]
    )
    assert "planned_scheduled_everyday" in day
    assert "a flexible budget never makes a date planned" in day["state"]["description"]
    assert "Analysis only" in line["planned_per_day"]["description"]
    assert "not a limit or a target for any date" in line["left_per_day"]["description"]
    assert "on no date" in line["spending_type"]["description"]
    assert (
        "No flexible budget is in it" in summary["scheduled_after_today"]["description"]
    )
    assert "no date holds it" in summary["flexible_per_day"]["description"]
    assert "A flexible budget is a monthly limit with no dates" in get.description
    assert "planned_flexible: the flexible budgets' daily share" not in get.description
    # the render tool is bound to the corrected component
    show = tools["show_financial_calendar"].meta
    assert show["ui"]["resourceUri"] == CALENDAR_URI
    assert CALENDAR_URI == "ui://mita/financial-calendar-v4.html"


# --- M: every month length, to the cent -------------------------------------------------------


@pytest.mark.parametrize(
    "year, month, days, pace, coffee_cents",
    [
        (2027, 2, 28, "3.57", {160: 8, 161: 20}),  # February
        (2028, 2, 29, "3.45", {155: 24, 156: 5}),  # a leap year
        (2026, 11, 30, "3.33", {150: 30}),  # 30 days
        (2026, 12, 31, "3.23", {145: 26, 146: 5}),  # 31 days
    ],
)
async def test_every_month_length_is_exact_and_free_of_daily_shares(
    mcp, seed, connection, year, month, days, pace, coffee_cents
):
    """M. A 100.00 flexible budget and a 45.00 daily coffee in months of 28,
    29, 30 and 31 days: the stored rows keep every cent, the coffee's
    purchases add up to 45.00 exactly, and the budget is on no date."""
    m = mcp.at(noon(1, month, year))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 1500,
            "currency": "EUR",
            "timezone": TZ,
            "household_size": 1,
            "monthly_savings_target": 300,
            "setup_answers": [{"topic": "everyday_spending", "answer": "described"}],
        },
    )
    draft = await call(
        m,
        token,
        "preview_monthly_budget",
        {
            "month": f"{year}-{month:02d}",
            "budget_lines": [
                {"label": "Restaurants", "amount": 100},
                {"label": "Coffee", "amount": 45},
            ],
            "spending_patterns": [COFFEE_DAILY],
        },
    )
    await call(m, token, "save_monthly_budget", {"draft_token": draft["draft_token"]})
    seen = await see(m, token, year, month)
    assert len(seen.data["days"]) == days

    rows = await stored_rows(connection, user, year, month)
    stored = [a for (_d, code), a in rows.items() if code == RESTAURANTS]
    assert len(stored) == days and sum(stored) == D("100.00")  # conserved
    assert max(stored) - min(stored) <= D("0.01")

    restaurants = seen.line(RESTAURANTS)
    assert (restaurants["planned"], restaurants["remaining"]) == ("100.00", "100.00")
    assert restaurants["planned_per_day"] == pace
    assert D(restaurants["left_per_day"]) == (D("100.00") / days).quantize(D("0.01"))
    coffee = seen.line(COFFEE)
    assert len(coffee["purchases"]) == days
    assert sum(D(p["planned"]) for p in coffee["purchases"]) == D("45.00")
    counted: Dict[int, int] = {}
    for p in coffee["purchases"]:
        cents = int(D(p["planned"]) * 100)
        counted[cents] = counted.get(cents, 0) + 1
    assert counted == coffee_cents
    for d in seen.data["days"]:
        day = int(d["date"][-2:])
        assert RESTAURANTS not in seen.day_lines(day)
        assert [p["category"] for p in d["purchases"]] == [COFFEE]
        assert d["planned_scheduled"] == d["purchases"][0]["planned"]
        assert D(d["planned"]) == D(d["planned_scheduled"]) + D(d["planned_flexible"])
    # the bookkeeping adds up to the budget, to the cent
    assert sum(D(d["planned_flexible"]) for d in seen.data["days"]) == D("100.00")
    assert sum(D(d["planned_scheduled"]) for d in seen.data["days"]) == D("45.00")


# --- N: nothing of the user's is changed --------------------------------------------------------


async def _fingerprint(connection, user) -> dict:
    """Everything of the account the calendar could conceivably touch."""

    async def rows(sql: str) -> list:
        result = await connection.execute(text(sql), {"u": user.id})
        return [tuple(r) for r in result]

    return {
        "plan": await rows(
            "SELECT date, category, planned_amount, spent_amount, plan_json::text "
            "FROM daily_plan WHERE user_id = :u ORDER BY date, category"
        ),
        "transactions": await rows(
            "SELECT id, category, amount, spent_at, deleted_at FROM transactions "
            "WHERE user_id = :u ORDER BY id"
        ),
        "obligations": await rows(
            "SELECT id, category, amount, scheduled_date, recurrence, status "
            "FROM scheduled_expenses WHERE user_id = :u ORDER BY id"
        ),
        "patterns": await rows(
            "SELECT * FROM spending_patterns WHERE user_id = :u ORDER BY 1, 2, 3"
        ),
        "lines": await rows(
            "SELECT * FROM mcp_budget_lines WHERE user_id = :u ORDER BY 1, 2, 3"
        ),
        "links": await rows(
            "SELECT * FROM obligation_payments WHERE user_id = :u ORDER BY 1, 2, 3"
        ),
        "profile": await rows(
            "SELECT monthly_income, savings_goal, currency, timezone, country "
            "FROM users WHERE id = :u"
        ),
    }


async def test_the_users_amounts_reserve_savings_and_records_are_untouched(
    mcp, seed, connection
):
    """N. The correction is in what the calendar shows. The user's confirmed
    limits, the 380.00 they left unallocated, the 500.00 of savings, the two
    loans, the stated coffee pattern and the recorded expense are exactly
    what they were — and reading the calendar writes nothing."""
    user, token, draft = await november(mcp, seed, patterns=[COFFEE_DAILY])
    # The reviewed plan: the user's amounts, exactly; 380.00 with no line.
    allocations = {a["category"]: a["amount"] for a in draft["category_allocations"]}
    assert {k: v for k, v in allocations.items() if k.startswith("my:")} == {
        **ENVELOPES,
        COFFEE: "45.00",
    }
    assert draft["unallocated"] == "380.00"
    assert draft["savings_allocation"] == "500.00"

    m10 = mcp.at(noon(10))
    await call(
        m10,
        token,
        "add_transaction",
        {"amount": "40.00", "budget_line": "Restaurants", "idempotency_key": key()},
    )
    before = await _fingerprint(connection, user)

    # the calendar, every way it is opened
    seen = await see(m10, token)
    for arguments in (
        {"year": 2026, "month": 11, "category": "Restaurants"},
        {"year": 2026, "month": 11, "category": "Coffee", "focus_date": "2026-11-20"},
        {"focus_date": "2026-11-15"},
        {"year": 2026, "month": 12},
        {"year": 2026, "month": 10},
    ):
        opened = structured(await m10.call(token, "show_financial_calendar", arguments))
        assert opened["plan_status"] in ("generated", "not_generated")
    assert await _fingerprint(connection, user) == before

    # confirmed monthly limits: unchanged in the saved month
    for line, monthly in {**ENVELOPES, COFFEE: "45.00"}.items():
        assert seen.line(line)["planned"] == monthly
        assert seen.line(line)["source"] == "set_by_you"
    # protected savings: 500.00, never in a date's spending plan
    savings = next(c for c in seen.data["categories"] if c["group"] == "set_aside")
    assert savings["planned"] == "500.00"
    assert seen.summary["savings_set_aside"] == "500.00"
    assert seen.summary["set_aside_planned"] == "500.00"
    # the reserve: income − everything planned = 380.00, on no line
    assert D("1985.00") - D(seen.summary["total_planned"]) == D("380.00")
    assert seen.summary["stated_monthly_income"] == "1985.00"
    # the loans and the pattern
    assert [(b["name"], b["amount"]) for b in seen.data["bills"]] == [
        ("Car loan", "270.00"),
        ("Laptop loan", "70.00"),
    ]
    assert seen.line(COFFEE)["pattern"] == "every day"
    # and the plan still adds up, to the cent, with the budgets on no date
    status = await call(m10, token, "get_budget_status", {"year": 2026, "month": 11})
    forecast = await call(
        m10, token, "get_budget_forecast", {"year": 2026, "month": 11}
    )
    assert status["total_planned"] == forecast["total_planned"] == "1605.00"
    assert seen.summary["total_planned"] == "1605.00"
    assert seen.summary["average_per_day"] == forecast["safe_daily_limit"]
    assert sum(D(d["planned"]) + D(d["set_aside"]) for d in seen.data["days"]) == D(
        "1605.00"
    )


# --- the rule itself, without a database -----------------------------------------------------------


def _month(kinds=None, spent=None, today=date(2026, 11, 10)):
    """Restaurants 60.00 a month laid evenly (2.00 a date) and groceries
    50.00 on the 4th and the 18th."""
    planned = {(date(2026, 11, d), "restaurants"): D("2.00") for d in range(1, 31)}
    planned[(date(2026, 11, 4), "groceries")] = D("50.00")
    planned[(date(2026, 11, 18), "groceries")] = D("50.00")
    return build_calendar(
        year=2026,
        month=11,
        today=today,
        planned=planned,
        spent=spent or {},
        plan_generated=True,
        kinds=kinds,
        base=planned,
    )


def test_a_dates_state_never_counts_a_flexible_budget_as_its_plan():
    kinds = {"restaurants": "flexible", "groceries": "planned"}
    cal = _month(
        kinds,
        spent={
            (date(2026, 11, 4), "groceries"): D("47.00"),
            (date(2026, 11, 5), "restaurants"): D("2.00"),
        },
    )
    states = {d.day.day: d.status for d in cal.days}
    assert states[4] == "within"  # a purchase was planned, and kept
    assert states[5] == "unplanned"  # spent from the budget; nothing scheduled
    assert states[6] == "quiet"  # nothing scheduled, nothing spent
    assert states[18] == "planned"  # the next shop
    assert states[19] == "free"  # only the budget's share: no plan
    day19 = cal.days[18]
    assert (day19.planned, day19.planned_flexible, day19.planned_scheduled) == (
        D("2.00"),
        D("2.00"),
        ZERO,
    )
    assert [(line.line, line.scheduled) for line in day19.lines] == [
        ("restaurants", ZERO)
    ]
    assert cal.scheduled_after_today == D("50.00")
    assert cal.planned_after_today == D("90.00")  # 20 × 2.00 + 50.00: bookkeeping


def test_a_month_saved_before_line_kinds_reads_exactly_as_before():
    """A legacy layout has no flexible budget: its rows are MITA's old
    per-date plan and stay scheduled, with the states they always had."""
    cal = _month(
        kinds=None,
        spent={(date(2026, 11, 5), "restaurants"): D("3.00")},
    )
    states = {d.day.day: d.status for d in cal.days}
    assert (states[4], states[5], states[6], states[19]) == (
        "within",
        "over",
        "within",
        "planned",
    )
    assert all(d.planned_flexible == ZERO for d in cal.days)
    assert all(d.planned_scheduled == d.planned for d in cal.days)
    assert all(d.scheduled_everyday == d.planned_everyday for d in cal.days)
    assert cal.scheduled_after_today == cal.planned_after_today == D("90.00")
    assert all(line.scheduled == line.planned for d in cal.days for line in d.lines)


# --- the component -----------------------------------------------------------------------------------


def test_the_component_cannot_draw_a_flexible_budget_on_a_date():
    """L (source rules; the rendered checks are in
    scripts/mcp/calendar_widget_review.py). The component reads a date's
    amounts from what is scheduled and what was spent, takes only the
    version 2 payload, and has no daily guide left to put in a cell."""
    html = calendar_html()
    assert "ui://mita/financial-calendar-v4.html" in html
    assert "var PAYLOAD_VERSION = 2;" in html
    assert "payload.version === PAYLOAD_VERSION" in html
    # day_lines are [line, scheduled, spent]; the stored plan row is gone
    assert "{ key: l[0], scheduled: l[1], spent: l[2] }" in html
    assert not re.search(r"\bl\.planned\b", html) and "match.planned" not in html
    # no "≈" guide in a cell, and no style for one
    assert "≈" not in html and ".guide" not in html
    # a date's plan is planned_scheduled everywhere, the image included
    assert "planned: day.planned_scheduled," in html
    assert "cellAmount(day.planned_scheduled)" in html
    assert "cellAmount(day.planned)" not in html
    # the flexible share is used only to choose words, never shown as money
    for use in html.split("day.planned_flexible")[1:]:
        assert use.lstrip().startswith(") > 0")
    assert "day.planned_everyday, cur" not in html
    # guidance stays, with the month, said to be guidance
    assert "as guidance, not a daily limit" in html
    assert "Monthly limits with no purchase dates" in html
