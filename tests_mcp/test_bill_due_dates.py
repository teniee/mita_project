"""Fixed payments on their due dates, reminders, and paying them (F-8).

Owner decision 2026-11-02 (``docs/chatgpt-app/bill-due-dates.md``): a saved
bill is planned in full on its due date; it is announced
``REMINDER_DAYS`` (5) days before; recording it on time, early, late or in
parts moves only that bill line's own money (``bill_timing``) and is never
overspending in itself; a bill line is never a rebalancing donor. Everyday
lines keep their per-date rebalancing.

The owner's real staging month, entered through MITA's own tools as ChatGPT
did (2026-11-02, Europe/Sofia, EUR): income 2,000, savings 500, household 1;
Phone 30 on the 10th (``utilities``), Car loan 270 on the 15th
(``transportation``), Laptop loan 70 on the 25th (``other``); the user's own
lines Fuel 200 (replaces MITA's fuel), Cigarettes 200, Coffee and walks 100,
Groceries 50 (replaces MITA's groceries), Housing 50. MITA's lines take the
other 530.00 (public transport 151.63, medical insurance 60.65 …), nothing
unallocated: plan 2,000.00. With the old layout the calendar read 52.00 on
the 10th, 38.99 on the 15th and 51.96 on the 25th, the bills spread over
weekdays (the phone on the 5th); reproduced in
``test_the_old_layout_is_what_the_owner_saw``.

Since 2026-11-03 (docs/chatgpt-app/behavioral-budget.md) each saved bill has
a plan line of its own (``"bill:<id>"``, ``line_of``) and is paid only by an
expense recorded as that payment (``pay_bill``: ``obligation_ref``) — a
purchase in the same category is ordinary spending. The owner described no
purchase days, so every other line is a flexible budget: a date ahead holds
only its bills (``planned_scheduled``); the flexible budgets' daily share is
guidance (``planned_flexible``).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Tuple

import pytest
from sqlalchemy import text

from app.core.category_priority import is_set_aside
from app.services.core.engine.bill_timing import BILL_TIMING_KEY, settle
from app.services.monthly_obligations import due_dates_in_month, due_in_month
from app.services.monthly_plan_service import (
    allocations_from_profile,
    bills_on_due_dates,
    month_calendar,
)
from app.services.obligation_lines import bill_key
from tests_mcp.conftest import structured
from tests_mcp.test_money_consistency import look, obligation_ref

D = Decimal
TZ = "Europe/Sofia"
SETUP = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)  # 12:00 in Sofia
PHONE = ("Phone", "30.00", "utilities", 10)
CAR = ("Car loan", "270.00", "transportation", 15)
LAPTOP = ("Laptop loan", "70.00", "other", 25)
OWNER_LINES = [
    {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]},
    {"label": "Cigarettes", "amount": 200},
    {"label": "Coffee and walks", "amount": 100},
    {"label": "Groceries", "amount": 50, "replaces": ["groceries"]},
    {"label": "Housing", "amount": 50},
]
USER_LINES = {
    "my:Fuel": "200.00",
    "my:Cigarettes": "200.00",
    "my:Coffee and walks": "100.00",
    "my:Groceries": "50.00",
    "my:Housing": "50.00",
}
BILLS = ("utilities", "transportation", "other")  # their categories


async def line_of(connection, user, name: str) -> str:
    """The plan line a saved payment's money is on (its own line)."""
    oid = (
        await connection.execute(
            text(
                "SELECT id FROM scheduled_expenses WHERE user_id = :u AND merchant = :n"
            ),
            {"u": user.id, "n": name},
        )
    ).scalar_one()
    return bill_key(oid)


async def bill_lines(connection, user) -> set:
    oids = (
        await connection.execute(
            text("SELECT id FROM scheduled_expenses WHERE user_id = :u"),
            {"u": user.id},
        )
    ).scalars()
    return {bill_key(oid) for oid in oids}


async def pay_bill(
    mcp, token, day: int, amount: str, name: str, *, today=None, due=None
):
    """Record an expense AS the payment of the user's saved payment ``name``."""
    m = mcp.at(at(today or day))
    ref = await obligation_ref(m, token, merchant=name)
    arguments = {
        "amount": amount,
        "obligation_ref": ref,
        "date": date(2026, 11, day).isoformat(),
        "idempotency_key": key(),
    }
    if due is not None:
        arguments["obligation_due_date"] = due
    return await call(m, token, "add_transaction", arguments)


def at(day: int, month: int = 11) -> datetime:
    """Noon in Sofia on that date (10:00 UTC in November)."""
    return datetime(2026, month, day, 10, 0, tzinfo=timezone.utc)


def key() -> str:
    return uuid.uuid4().hex


async def call(m, token, tool, arguments=None):
    return structured(await m.call(token, tool, arguments or {}))


async def add_bill(m, token, name, amount, category, day=None, **rule):
    arguments = {
        "name": name,
        "amount": amount,
        "category": category,
        "recurrence": rule.pop("recurrence", "monthly"),
        "idempotency_key": key(),
    }
    if day is not None:
        arguments["day_of_month"] = day
    arguments.update(rule)
    return await call(m, token, "add_recurring_expense", arguments)


async def owner_account(mcp, seed, *, extra_bills=(), months=("2026-11",)):
    """The owner's account and reviewed November budget, entered on 2 Nov."""
    m = mcp.at(SETUP)
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 2000,
            "currency": "EUR",
            "timezone": TZ,
            "household_size": 1,
            "monthly_savings_target": 500,
        },
    )
    for name, amount, category, day in (PHONE, CAR, LAPTOP) + tuple(extra_bills):
        await add_bill(m, token, name, amount, category, day)
    for month in months:
        preview = await call(
            m,
            token,
            "preview_monthly_budget",
            {"month": month, "budget_lines": OWNER_LINES},
        )
        saved = await call(
            m, token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
        assert saved["status"] == "saved"
    return user, token


async def spend(mcp, token, day: int, amount: str, category: str, *, today=None):
    m = mcp.at(at(today or day))
    out = await call(
        m,
        token,
        "add_transaction",
        {
            "amount": amount,
            "category": category,
            "date": date(2026, 11, day).isoformat(),
            "idempotency_key": key(),
        },
    )
    return out


Rows = Dict[Tuple[int, str], Tuple[Decimal, Decimal, Decimal, Decimal]]


async def rows_of(connection, user, month: int = 11) -> Rows:
    """{(day, category): (planned, spent cache, realtime adj., bill timing)}."""
    result = await connection.execute(
        text(
            "SELECT date, category, planned_amount, spent_amount, plan_json "
            "FROM daily_plan WHERE user_id = :u AND date >= :start AND date < :end"
        ),
        {
            "u": user.id,
            "start": datetime(2026, month, 1),
            "end": datetime(2026 + month // 12, month % 12 + 1, 1),
        },
    )
    rows: Rows = {}
    for row in result.mappings():
        meta = row["plan_json"] if isinstance(row["plan_json"], dict) else {}
        rows[(row["date"].day, row["category"])] = (
            D(str(row["planned_amount"])),
            D(str(row["spent_amount"] or 0)),
            D(str(meta.get("_mita_realtime_adjustment_v1", "0"))),
            D(str(meta.get(BILL_TIMING_KEY, "0"))),
        )
    return rows


def where(rows: Rows, category: str) -> Dict[int, Decimal]:
    """The dates a category holds money on, and how much."""
    return {d: p for (d, c), (p, _s, _a, _t) in rows.items() if c == category and p}


def line_totals(rows: Rows) -> Dict[str, Decimal]:
    totals: Dict[str, Decimal] = defaultdict(lambda: D("0"))
    for (_d, c), (p, _s, _a, _t) in rows.items():
        totals[c] += p
    return dict(totals)


def no_redistribution(rows: Rows) -> bool:
    return all(a == 0 for (_p, _s, a, _t) in rows.values())


def bills_by_name(cal) -> Dict[str, dict]:
    return {b["name"]: b for b in cal["bills"]}


async def calendar(mcp, token, today: int, month: int = 11):
    return await call(
        mcp.at(at(today)),
        token,
        "get_calendar_month",
        {"year": 2026, "month": month},
    )


# --- the rule, pure ------------------------------------------------------------------


def test_due_dates_follow_the_stated_rule_across_month_lengths():
    on_31st = date(2026, 1, 31)
    assert due_dates_in_month(on_31st, "monthly", 2026, 2) == [date(2026, 2, 28)]
    assert due_dates_in_month(on_31st, "monthly", 2028, 2) == [date(2028, 2, 29)]
    assert due_dates_in_month(on_31st, "monthly", 2026, 4) == [date(2026, 4, 30)]
    assert due_dates_in_month(on_31st, "monthly", 2026, 12) == [date(2026, 12, 31)]
    fridays = due_dates_in_month(date(2026, 11, 6), "weekly", 2026, 11)
    assert [d.day for d in fridays] == [6, 13, 20, 27]
    assert due_dates_in_month(date(2026, 11, 18), "once", 2026, 11) == [
        date(2026, 11, 18)
    ]
    assert due_dates_in_month(date(2026, 11, 18), None, 2026, 12) == []
    # not running yet: first due after the end of next month
    assert due_dates_in_month(date(2027, 1, 5), "monthly", 2026, 11) == []
    # the amount is the dates' sum, always
    for rule, anchor in (("weekly", date(2026, 11, 6)), ("monthly", on_31st)):
        dates = due_dates_in_month(anchor, rule, 2026, 11)
        assert due_in_month(D("20"), anchor, rule, 2026, 11) == D("20") * len(dates)


def test_settle_matches_in_date_order():
    nov = lambda d: date(2026, 11, d)  # noqa: E731
    # on time, early, late, in parts, beyond the line
    assert settle([(nov(15), D(270))], [(nov(15), D(270))]).paid == [
        [(nov(15), D(270))]
    ]
    assert settle([(nov(15), D(270))], [(nov(12), D(270))]).paid == [
        [(nov(12), D(270))]
    ]
    assert settle([(nov(15), D(270))], [(nov(17), D(270))]).paid == [
        [(nov(17), D(270))]
    ]
    parts = settle([(nov(15), D(270))], [(nov(15), D(100)), (nov(20), D(170))])
    assert parts.covered == [D(270)]
    assert parts.paid == [[(nov(15), D(100)), (nov(20), D(170))]]
    beyond = settle([(nov(15), D(270))], [(nov(15), D(300))])
    assert (beyond.covered, beyond.beyond) == ([D(270)], {nov(15): D(30)})
    # a payment uses its own date first, then the oldest unpaid, then the next
    weekly = [(nov(6), D(20)), (nov(13), D(20)), (nov(20), D(20))]
    s = settle(weekly, [(nov(13), D(20)), (nov(14), D(20))])
    assert s.paid == [[(nov(14), D(20))], [(nov(13), D(20))], []]
    # two bills of one category on one date stay two
    same_day = settle([(nov(10), D(12)), (nov(10), D(10))], [(nov(10), D(12))])
    assert same_day.covered == [D(12), D(0)]


def test_a_bill_is_placed_in_full_on_its_date_and_never_beyond_its_line():
    placed = bills_on_due_dates(
        {"transportation": D("270"), "other": D("50")},
        [
            (date(2026, 11, 15), "transportation", D("270")),
            (date(2026, 11, 5), "other", D("40")),
            (date(2026, 11, 25), "other", D("40")),  # only 10 left on the line
            (date(2026, 11, 9), "gifts", D("15")),  # no money on the line
        ],
    )
    assert placed == {
        date(2026, 11, 15): {"transportation": D("270")},
        date(2026, 11, 5): {"other": D("40")},
        date(2026, 11, 25): {"other": D("10")},
    }


def test_the_old_layout_is_what_the_owner_saw():
    """The owner's allocation laid out without due dates gives the staging
    calendar's figures; with them, each bill sits whole on its date."""
    allocation = allocations_from_profile(
        monthly_income=D("2000"),
        savings_goal=D("500"),
        region="ZZ",
        fixed_expenses={
            "utilities": D("30"),
            "transportation": D("270"),
            "other": D("70"),
        },
        manual_allocations={k: D(v) for k, v in USER_LINES.items()},
        replaced_buckets={"transport gas", "groceries"},
    )
    assert allocation.discretionary["transport public"] == D("151.63")
    assert allocation.discretionary["insurance medical"] == D("60.65")
    assert sum(allocation.allocations.values()) == D("2000.00")

    def day(layout, n):
        return sum(
            (
                D(str(v))
                for c, v in layout.get(date(2026, 11, n).isoformat(), {}).items()
                if not is_set_aside(c)
            ),
            D("0"),
        )

    old = month_calendar(2026, 11, allocation.allocations)
    assert (day(old, 10), day(old, 15), day(old, 25)) == (
        D("52.00"),
        D("38.99"),
        D("51.96"),
    )
    new = month_calendar(
        2026,
        11,
        allocation.allocations,
        [
            (date(2026, 11, 10), "utilities", D("30")),
            (date(2026, 11, 15), "transportation", D("270")),
            (date(2026, 11, 25), "other", D("70")),
        ],
    )
    assert (day(new, 10), day(new, 15), day(new, 25)) == (
        D("65.80"),  # everyday 35.80 + phone 30
        D("308.99"),  # everyday 38.99 + car loan 270
        D("105.78"),  # everyday 35.78 + laptop loan 70
    )


# --- the owner's month ---------------------------------------------------------------


async def test_the_owner_s_bills_are_planned_whole_on_their_due_dates(
    mcp, seed, connection
):
    user, token = await owner_account(mcp, seed)
    m = mcp.at(SETUP)
    preview = await call(m, token, "preview_monthly_budget", {"month": "2026-11"})
    assert [(o["name"], o["due_dates"]) for o in preview["fixed_obligations"]] == [
        ("Phone", ["2026-11-10"]),
        ("Car loan", ["2026-11-15"]),
        ("Laptop loan", ["2026-11-25"]),
    ]
    rows = await rows_of(connection, user)
    phone, car, laptop = [
        await line_of(connection, user, n) for n in ("Phone", "Car loan", "Laptop loan")
    ]
    assert where(rows, phone) == {10: D("30.00")}
    assert where(rows, car) == {15: D("270.00")}
    assert where(rows, laptop) == {25: D("70.00")}
    assert not {c for (_d, c) in rows} & set(BILLS)  # never under the category
    totals = line_totals(rows)
    assert {k: totals[k] for k in USER_LINES} == {
        k: D(v) for k, v in USER_LINES.items()
    }
    assert sum(totals.values()) == D("2000.00")

    seen = await look(m, token, connection, user, month=11, today=date(2026, 11, 2))
    days = {d["date"]: d for d in seen.cal["days"]}
    # Each bill alone on its due date; no purchase is planned on any other
    # date (the reminder windows included): the owner described no purchase
    # days, so their lines and MITA's are flexible budgets.
    scheduled = {
        d[-2:]: x["planned_scheduled"]
        for d, x in days.items()
        if D(x["planned_scheduled"]) > 0
    }
    assert scheduled == {"10": "30.00", "15": "270.00", "25": "70.00"}
    assert all(x["purchases"] == [] for x in days.values())
    assert sum(D(x["planned_flexible"]) for x in days.values()) == D("1130.00")
    kinds = {c["category"]: c["spending_type"] for c in seen.cal["categories"]}
    assert {kinds[k] for k in USER_LINES} == {"flexible"}
    assert kinds["transport public"] == "flexible"  # MITA's suggestion, no dates
    assert kinds[car] == "obligation"
    summary = seen.summary
    assert (
        summary["total_planned"],
        summary["commitments_planned"],
        summary["set_aside_planned"],
        summary["everyday_planned"],
    ) == ("2000.00", "370.00", "500.00", "1130.00")
    # R3: bills held until recorded; 1,130.00 over the 28 days after today
    assert (
        summary["commitments_reserved"],
        summary["left_to_spend"],
        summary["average_per_day"],
    ) == ("370.00", "1130.00", "40.36")
    assert [(b["name"], b["date"], b["state"]) for b in seen.cal["bills"]] == [
        ("Phone", "2026-11-10", "later"),
        ("Car loan", "2026-11-15", "later"),
        ("Laptop loan", "2026-11-25", "later"),
    ]
    assert seen.cal["reminders"] == []
    # the user's lines carry the MITA lines they replace, as saved (icons)
    replaces = {c["category"]: c["replaces"] for c in seen.cal["categories"]}
    assert (replaces["my:Fuel"], replaces["my:Groceries"]) == (
        ["transport gas"],
        ["groceries"],
    )
    assert replaces["my:Cigarettes"] == [] and replaces["transport public"] == []


async def test_another_account_gets_its_own_calendar_and_an_empty_one_without_a_plan(
    mcp, seed
):
    """Nothing of the owner's month reaches another account: a different
    user gets their own figures, a user without a budget the empty state."""
    owner, owner_token = await owner_account(mcp, seed)
    m = mcp.at(SETUP)
    other = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    other_token = m.token(other)
    await call(
        m,
        other_token,
        "update_financial_profile",
        {
            "monthly_net_income": 3100,
            "currency": "EUR",
            "timezone": TZ,
            "monthly_savings_target": 300,
        },
    )
    before = await call(
        m, other_token, "get_calendar_month", {"year": 2026, "month": 11}
    )
    assert before["plan_status"] == "not_generated" and before["bills"] == []
    assert before["summary"]["total_planned"] is None
    await add_bill(m, other_token, "Rent", "900.00", "rent", 3)
    preview = await call(m, other_token, "preview_monthly_budget", {"month": "2026-11"})
    await call(
        m, other_token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
    )
    mine = await call(m, other_token, "get_calendar_month", {"year": 2026, "month": 11})
    owners = await call(
        m, owner_token, "get_calendar_month", {"year": 2026, "month": 11}
    )
    assert mine["summary"]["total_planned"] != owners["summary"]["total_planned"]
    assert [b["name"] for b in mine["bills"]] == ["Rent"]
    assert [b["name"] for b in owners["bills"]] == ["Phone", "Car loan", "Laptop loan"]
    assert not any(c["category"].startswith("my:") for c in mine["categories"])


async def test_reminders_announce_a_bill_five_days_ahead_without_money(
    mcp, seed, connection
):
    user, token = await owner_account(mcp, seed)
    expected = {
        19: None,  # six days ahead: no reminder yet
        20: ("upcoming", 5),
        22: ("upcoming", 3),
        24: ("upcoming", 1),
        25: ("due_today", 0),
        26: ("overdue", -1),
    }
    for today, want in expected.items():
        cal = await calendar(mcp, token, today)
        laptop = bills_by_name(cal)["Laptop loan"]
        reminded = [b for b in cal["reminders"] if b["name"] == "Laptop loan"]
        if want is None:
            assert laptop["state"] == "later" and not reminded, today
        else:
            assert (laptop["state"], laptop["days_until"]) == want, today
            assert reminded == [laptop], today
        assert laptop["reminder_from"] == "2026-11-20"
        view = await call(
            mcp.at(at(today)),
            token,
            "show_financial_calendar",
            {"year": 2026, "month": 11},
        )
        assert view["reminders"] == cal["reminders"]
    shown = (
        (
            await mcp.at(at(22)).call(
                token, "show_financial_calendar", {"year": 2026, "month": 11}
            )
        )
        .content[0]
        .text
    )
    assert "Laptop loan 70.00 due 2026-11-25 (in 3 days)" in shown
    shown = (
        (
            await mcp.at(at(24)).call(
                token, "show_financial_calendar", {"year": 2026, "month": 11}
            )
        )
        .content[0]
        .text
    )
    assert "Laptop loan 70.00 due tomorrow (2026-11-25)" in shown
    # the plan never moved
    rows = await rows_of(connection, user)
    assert where(rows, await line_of(connection, user, "Laptop loan")) == {
        25: D("70.00")
    }


async def test_paying_bills_on_their_dates_moves_nothing_and_releases_the_reserve(
    mcp, seed, connection
):
    user, token = await owner_account(mcp, seed)
    before = await look(
        mcp.at(at(15)), token, connection, user, month=11, today=date(2026, 11, 15)
    )
    await pay_bill(mcp, token, 10, "30.00", "Phone", today=15)
    await pay_bill(mcp, token, 15, "270.00", "Car loan")
    after = await look(
        mcp.at(at(15)), token, connection, user, month=11, today=date(2026, 11, 15)
    )
    rows = await rows_of(connection, user)
    assert no_redistribution(rows)
    assert all(t == 0 for (_p, _s, _a, t) in rows.values())  # nothing re-timed
    assert where(rows, await line_of(connection, user, "Car loan")) == {15: D("270.00")}
    # Spent +300, held -300: left to spend and the daily figure do not move.
    assert (
        before.summary["commitments_reserved"],
        after.summary["commitments_reserved"],
    ) == (
        "370.00",
        "70.00",
    )
    assert D(after.summary["total_spent"]) - D(before.summary["total_spent"]) == D(300)
    assert (
        after.summary["left_to_spend"] == before.summary["left_to_spend"] == "1130.00"
    )
    assert after.summary["average_per_day"] == before.summary["average_per_day"]
    redistributed = (
        await connection.execute(
            text("SELECT count(*) FROM redistribution_events WHERE user_id = :u"),
            {"u": user.id},
        )
    ).scalar_one()
    assert redistributed == 0
    bills = bills_by_name(after.cal)
    assert (bills["Car loan"]["state"], bills["Car loan"]["paid_dates"]) == (
        "paid",
        ["2026-11-15"],
    )
    assert bills["Phone"]["state"] == "paid"
    day15 = next(d for d in after.cal["days"] if d["date"] == "2026-11-15")
    assert (day15["spent"], day15["spent_everyday"], day15["state"]) == (
        "270.00",
        "0.00",
        # a bill paid is not everyday spending, and no everyday purchase was
        # scheduled for the 15th: the flexible budgets are on no date (2.10.0)
        "quiet",
    )


async def test_a_bill_paid_early_is_counted_once_on_the_day_paid(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    await pay_bill(mcp, token, 12, "270.00", "Car loan", today=13)
    seen = await look(
        mcp.at(at(13)), token, connection, user, month=11, today=date(2026, 11, 13)
    )
    rows = await rows_of(connection, user)
    car_line = await line_of(connection, user, "Car loan")
    assert where(rows, car_line) == {12: D("270.00")}
    assert rows[(15, car_line)][:2] == (D("0.00"), D("0"))
    assert rows[(12, car_line)][3] == D("270.00")  # bill timing, not
    assert rows[(15, car_line)][3] == D("-270.00")  # redistribution
    assert no_redistribution(rows)
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["date"], car["state"], car["paid_dates"], car["days_until"]) == (
        "2026-11-15",
        "paid",
        ["2026-11-12"],
        2,
    )
    assert not [b for b in seen.cal["reminders"] if b["name"] == "Car loan"]
    days = {d["date"]: d for d in seen.cal["days"]}
    assert days["2026-11-15"]["planned_scheduled"] == "0.00"  # no second car loan
    assert seen.summary["commitments_reserved"] == "100.00"  # phone + laptop
    assert seen.summary["left_to_spend"] == "1130.00"


async def test_a_bill_paid_late_is_overdue_until_recorded_then_moves_with_it(
    mcp, seed, connection
):
    user, token = await owner_account(mcp, seed)
    await pay_bill(mcp, token, 10, "30.00", "Phone", today=16)
    waiting = await calendar(mcp, token, 16)
    car = bills_by_name(waiting)["Car loan"]
    assert (car["state"], car["paid"], car["days_until"]) == ("overdue", "0.00", -1)
    assert [b["name"] for b in waiting["reminders"]] == ["Car loan"]
    assert waiting["summary"]["commitments_reserved"] == "340.00"  # still held

    paid = await pay_bill(mcp, token, 17, "270.00", "Car loan")
    assert paid["transactions"][0]["paid_obligation"]["due_date"] == "2026-11-15"
    seen = await look(
        mcp.at(at(17)), token, connection, user, month=11, today=date(2026, 11, 17)
    )
    rows = await rows_of(connection, user)
    assert where(rows, await line_of(connection, user, "Car loan")) == {17: D("270.00")}
    assert no_redistribution(rows)
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["state"], car["paid_dates"]) == ("paid", ["2026-11-17"])
    day17 = next(d for d in seen.cal["days"] if d["date"] == "2026-11-17")
    assert day17["state"] != "over"
    assert seen.summary["commitments_reserved"] == "70.00"


async def test_a_partly_paid_bill_keeps_the_rest_held(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    await pay_bill(mcp, token, 15, "100.00", "Car loan")
    today = await calendar(mcp, token, 15)
    car = bills_by_name(today)["Car loan"]
    assert (car["state"], car["paid"], car["outstanding"]) == (
        "due_today",
        "100.00",
        "170.00",
    )
    assert today["summary"]["commitments_reserved"] == "270.00"  # 170 + 30 + 70
    shown = (
        (
            await mcp.at(at(15)).call(
                token, "show_financial_calendar", {"year": 2026, "month": 11}
            )
        )
        .content[0]
        .text
    )
    assert "Car loan 270.00 due today, 100.00 paid, 170.00 not yet" in shown
    later = await calendar(mcp, token, 18)
    assert bills_by_name(later)["Car loan"]["state"] == "overdue"

    await pay_bill(mcp, token, 20, "170.00", "Car loan")
    seen = await look(
        mcp.at(at(20)), token, connection, user, month=11, today=date(2026, 11, 20)
    )
    rows = await rows_of(connection, user)
    assert where(rows, await line_of(connection, user, "Car loan")) == {
        15: D("100.00"),
        20: D("170.00"),
    }
    assert no_redistribution(rows)
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["state"], car["paid_dates"]) == (
        "paid",
        ["2026-11-15", "2026-11-20"],
    )


async def test_spending_beyond_a_bill_line_is_overspending_as_before(
    mcp, seed, connection
):
    """€300 recorded as the €270 car loan's payment: €30 is beyond the bill
    and is covered from MITA's everyday lines ahead; no bill line, user line
    or savings line gives."""
    user, token = await owner_account(mcp, seed)
    out = await pay_bill(mcp, token, 15, "300.00", "Car loan")
    assert any("30.00 paid beyond it" in n for n in out["notes"])
    await look(
        mcp.at(at(15)), token, connection, user, month=11, today=date(2026, 11, 15)
    )
    rows = await rows_of(connection, user)
    moved_in = rows[(15, await line_of(connection, user, "Car loan"))]
    assert (moved_in[0], moved_in[2]) == (D("300.00"), D("30.00"))
    givers = {c for (_d, c), (_p, _s, a, _t) in rows.items() if a < 0}
    lines = await bill_lines(connection, user)
    assert givers and not givers & (lines | set(USER_LINES))
    assert not any(is_set_aside(c) for c in givers)


async def test_everyday_overspending_still_rebalances_but_never_from_bills_or_the_user_s_lines(
    mcp, seed, connection
):
    user, token = await owner_account(mcp, seed)
    before = await rows_of(connection, user)
    await spend(mcp, token, 3, "120.00", "dining", today=3)
    seen = await look(
        mcp.at(at(3)), token, connection, user, month=11, today=date(2026, 11, 3)
    )
    rows = await rows_of(connection, user)
    givers = {c for (_d, c), (_p, _s, a, _t) in rows.items() if a < 0}
    assert givers  # MITA's everyday lines covered it, as before
    assert not givers & (await bill_lines(connection, user) | set(USER_LINES))
    totals = line_totals(rows)
    assert {k: totals[k] for k in USER_LINES} == {
        k: D(v) for k, v in USER_LINES.items()
    }
    for bill in await bill_lines(connection, user):
        assert where(rows, bill) == where(before, bill) != {}
    assert seen.summary["commitments_reserved"] == "370.00"


async def test_an_unrelated_expense_in_a_bill_s_category_counts_only_its_amount(
    mcp, seed, connection
):
    """A €15 taxi under Transport is not the car loan (2026-11-03): it pays
    none of it. Until then MITA matched by category and counted €15 toward
    the loan (355.00 held); now the whole loan stays held, the taxi is
    ordinary spending, and the result says the loan is still unpaid so
    ChatGPT can ask the user — MITA never links it by itself."""
    user, token = await owner_account(mcp, seed)
    out = await spend(mcp, token, 5, "15.00", "transportation", today=12)
    assert any(
        "Car loan (270.00 due 2026-11-15)" in n and "does not pay it" in n
        for n in out["notes"]
    )
    assert out["transactions"][0]["paid_obligation"] is None
    cal = await calendar(mcp, token, 12)
    car = bills_by_name(cal)["Car loan"]
    assert (car["state"], car["paid"], car["paid_dates"]) == ("upcoming", "0.00", [])
    assert "Car loan" in [b["name"] for b in cal["reminders"]]
    assert cal["summary"]["commitments_reserved"] == "370.00"  # 270 + 30 + 70
    rows = await rows_of(connection, user)
    assert where(rows, await line_of(connection, user, "Car loan")) == {15: D("270.00")}
    assert rows[(5, "transportation")][1] == D("15.00")  # Transport spending


async def test_two_bills_on_one_day_and_two_in_one_category(mcp, seed, connection):
    user, token = await owner_account(
        mcp,
        seed,
        extra_bills=(
            ("Gym", "25.00", "subscriptions", 15),  # same day as the car loan
            ("Phone insurance", "8.00", "other", 5),  # same category as the laptop
        ),
    )
    rows = await rows_of(connection, user)
    assert where(rows, await line_of(connection, user, "Gym")) == {15: D("25.00")}
    assert where(rows, await line_of(connection, user, "Phone insurance")) == {
        5: D("8.00")
    }
    assert where(rows, await line_of(connection, user, "Laptop loan")) == {
        25: D("70.00")
    }
    cal = await calendar(mcp, token, 2)
    on15 = [b for b in cal["bills"] if b["date"] == "2026-11-15"]
    assert sorted((b["name"], b["amount"]) for b in on15) == [
        ("Car loan", "270.00"),
        ("Gym", "25.00"),
    ]
    day15 = next(d for d in cal["days"] if d["date"] == "2026-11-15")
    assert D(day15["planned"]) - D(day15["planned_everyday"]) == D("295.00")
    # paying the small one does not mark the laptop loan as paid
    await pay_bill(mcp, token, 5, "8.00", "Phone insurance", today=6)
    cal = await calendar(mcp, token, 6)
    states = {b["name"]: (b["state"], b["paid"]) for b in cal["bills"]}
    assert states["Phone insurance"] == ("paid", "8.00")
    assert states["Laptop loan"] == ("later", "0.00")


async def test_weekly_and_one_time_bills_sit_on_their_dates(mcp, seed, connection):
    m = mcp.at(SETUP)
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 2000,
            "currency": "EUR",
            "timezone": TZ,
            "monthly_savings_target": 500,
        },
    )
    await add_bill(
        m, token, "Cleaner", "20.00", "other", recurrence="weekly", weekday="friday"
    )
    # One-time payments come from the app's scheduled-expenses API (ChatGPT's
    # tool saves monthly and weekly ones).
    await seed.scheduled(
        user,
        category="transportation",
        amount=D("120.00"),
        scheduled_date=date(2026, 11, 18),
        recurrence="once",
        merchant="Car service",
    )
    preview = await call(m, token, "preview_monthly_budget", {"month": "2026-11"})
    await call(m, token, "save_monthly_budget", {"draft_token": preview["draft_token"]})
    rows = await rows_of(connection, user)
    cleaner_line = await line_of(connection, user, "Cleaner")
    assert where(rows, cleaner_line) == {
        6: D("20.00"),
        13: D("20.00"),
        20: D("20.00"),
        27: D("20.00"),
    }
    assert where(rows, await line_of(connection, user, "Car service")) == {
        18: D("120.00")
    }
    # one week's payment, recorded on the 14th, pays the oldest unpaid week
    # (the 6th, MITA's default when the user names no date): that week's
    # money moves, nothing else
    out = await pay_bill(mcp, token, 14, "20.00", "Cleaner")
    assert out["transactions"][0]["paid_obligation"]["due_date"] == "2026-11-06"
    rows = await rows_of(connection, user)
    assert where(rows, cleaner_line) == {
        13: D("20.00"),
        14: D("20.00"),
        20: D("20.00"),
        27: D("20.00"),
    }
    assert no_redistribution(rows)
    cal = await calendar(mcp, token, 14)
    cleaner = [(b["date"], b["state"]) for b in cal["bills"] if b["name"] == "Cleaner"]
    assert cleaner == [
        ("2026-11-06", "paid"),  # the oldest unpaid one comes first
        ("2026-11-13", "overdue"),
        ("2026-11-20", "later"),
        ("2026-11-27", "later"),
    ]


async def test_a_payment_recorded_just_after_midnight_in_sofia_is_on_time(
    mcp, seed, connection
):
    """22:30 UTC on 14 Nov is 00:30 on 15 Nov in Sofia (EET, UTC+2): the
    car loan paid then is on its due date — nothing moves."""
    user, token = await owner_account(mcp, seed)
    txn = await seed.txn(
        user,
        "270.00",
        "transportation",
        datetime(2026, 11, 14, 22, 30, tzinfo=timezone.utc),
    )
    await connection.execute(  # the user said it was the car loan's payment
        text(
            "INSERT INTO obligation_payments (id, user_id, scheduled_expense_id, "
            "due_date, transaction_id) SELECT gen_random_uuid(), :u, id, "
            "'2026-11-15', :t FROM scheduled_expenses WHERE user_id = :u "
            "AND merchant = 'Car loan'"
        ),
        {"u": user.id, "t": txn.id},
    )
    await spend(mcp, token, 15, "1.00", "dining")  # a ledger write rebuilds the month
    rows = await rows_of(connection, user)
    car_line = await line_of(connection, user, "Car loan")
    assert rows[(15, car_line)][:2] == (D("270.00"), D("270.00"))
    assert all(t == 0 for (_p, _s, _a, t) in rows.values())
    cal = await calendar(mcp, token, 15)
    assert bills_by_name(cal)["Car loan"]["paid_dates"] == ["2026-11-15"]


async def test_next_month_and_a_reminder_across_the_month_end(mcp, seed, connection):
    user, token = await owner_account(
        mcp,
        seed,
        extra_bills=(("Rent", "300.00", "rent", 1),),
        months=("2026-11", "2026-12"),
    )
    december = await rows_of(connection, user, month=12)
    assert where(december, await line_of(connection, user, "Phone")) == {10: D("30.00")}
    assert where(december, await line_of(connection, user, "Car loan")) == {
        15: D("270.00")
    }
    assert where(december, await line_of(connection, user, "Laptop loan")) == {
        25: D("70.00")
    }
    assert where(december, await line_of(connection, user, "Rent")) == {1: D("300.00")}
    next_month = await calendar(mcp, token, 28, month=12)
    assert [(b["name"], b["state"]) for b in next_month["bills"]] == [
        ("Rent", "upcoming"),
        ("Phone", "later"),
        ("Car loan", "later"),
        ("Laptop loan", "later"),
    ]
    # On 28 November, November's calendar already reminds of 1 December's rent.
    november = await calendar(mcp, token, 28)
    rent = [b for b in november["reminders"] if b["name"] == "Rent"]
    assert [(b["date"], b["state"], b["days_until"]) for b in rent] == [
        ("2026-12-01", "upcoming", 3)
    ]
    await look(
        mcp.at(at(28)), token, connection, user, month=12, today=date(2026, 11, 28)
    )


async def test_the_mobile_rollover_puts_bills_on_their_dates(
    mcp, seed, connection, monkeypatch
):
    """The app materializes a missing month from the last one
    (``ensure_month_plan``): the bills go on their dates there too."""
    from sqlalchemy.orm import Session

    import app.services.monthly_plan_service as plans
    from app.services.monthly_plan_service import ensure_month_plan

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            moment = at(28)
            return moment if tz else moment.replace(tzinfo=None)

    monkeypatch.setattr(plans, "datetime", Frozen)
    user, token = await owner_account(mcp, seed)

    def materialize(sync_connection):
        session = Session(
            bind=sync_connection, join_transaction_mode="create_savepoint"
        )
        try:
            return ensure_month_plan(session, user.id, 2026, 12)
        finally:
            session.close()

    result = await connection.run_sync(materialize)
    assert (result.created, result.source) == (True, "rollover")
    december = await rows_of(connection, user, month=12)
    assert where(december, await line_of(connection, user, "Phone")) == {10: D("30.00")}
    assert where(december, await line_of(connection, user, "Car loan")) == {
        15: D("270.00")
    }
    assert where(december, await line_of(connection, user, "Laptop loan")) == {
        25: D("70.00")
    }
    assert sum(line_totals(december).values()) == D("2000.00")
    # The new month keeps how the money is spent (flexible lines over all 31
    # days, not the weekdays November happened to have), not a day count.
    assert len(where(december, "my:Cigarettes")) == 31
    kinds = (
        (
            await connection.execute(
                text(
                    "SELECT DISTINCT plan_json->>'_mita_line_kind_v1' FROM daily_plan "
                    "WHERE user_id = :u AND date >= '2026-12-01' AND goal_id IS NULL"
                ),
                {"u": user.id},
            )
        )
        .scalars()
        .all()
    )
    assert set(kinds) == {"obligation", "flexible", "set_aside"}
    await look(
        mcp.at(at(28)), token, connection, user, month=12, today=date(2026, 11, 28)
    )


async def test_a_plan_saved_before_due_dates_is_corrected_only_when_the_user_saves_again(
    mcp, seed, connection
):
    """A month saved with the old layout keeps it (no silent rewrite); paying
    a bill already moves only that line's money; a new preview says that
    saving changes only where the bills sit, and saving puts them there."""
    user, token = await owner_account(mcp, seed)
    # Re-lay November as the old engine saved it: the bills under their
    # categories, the loans spread over the weekdays, the phone on the 5th,
    # and no line kinds (a plan saved before 2.7.0).
    await connection.execute(
        text("DELETE FROM daily_plan WHERE user_id = :u AND category LIKE 'bill:%'"),
        {"u": user.id},
    )
    await connection.execute(
        text(
            "UPDATE daily_plan SET plan_json = NULLIF(plan_json - "
            "'_mita_line_kind_v1', '{}'::jsonb) WHERE user_id = :u"
        ),
        {"u": user.id},
    )
    weekdays = [d for d in range(1, 31) if date(2026, 11, d).weekday() < 5]
    old = {(5, "utilities"): D("30.00")}
    for category, total in (("transportation", 270), ("other", 70)):
        cents, rest = divmod(total * 100, len(weekdays))
        for i, d in enumerate(weekdays):
            old[(d, category)] = D(cents + (1 if i < rest else 0)) / 100
    for (d, category), amount in old.items():
        await seed.plan(user, date(2026, 11, d), {category: str(amount)})
    await pay_bill(mcp, token, 15, "270.00", "Car loan", today=16)
    rows = await rows_of(connection, user)
    assert no_redistribution(rows)  # paid in full from its own line's money
    assert sum(where(rows, "transportation").values()) == D("270.00")
    preview = await call(
        mcp.at(at(16)), token, "preview_monthly_budget", {"month": "2026-11"}
    )
    assert preview["changes"] == []  # same amounts, now on lines of their own
    assert any("a line of its own" in w for w in preview["warnings"])
    await call(
        mcp.at(at(16)),
        token,
        "save_monthly_budget",
        {"draft_token": preview["draft_token"]},
    )
    rows = await rows_of(connection, user)
    assert where(rows, await line_of(connection, user, "Phone")) == {10: D("30.00")}
    car = await line_of(connection, user, "Car loan")
    assert where(rows, car) == {15: D("270.00")}  # paid on the 15th
    assert where(rows, await line_of(connection, user, "Laptop loan")) == {
        25: D("70.00")
    }
    assert not {c for (_d, c) in rows} & set(BILLS)
    totals = line_totals(rows)
    assert {k: totals[k] for k in USER_LINES} == {
        k: D(v) for k, v in USER_LINES.items()
    }


@pytest.mark.parametrize("category", ["rent", "utilities"])
async def test_a_stated_essential_without_a_saved_payment_is_a_bill_line_too(
    mcp, seed, connection, category
):
    """Rent or utilities in a plan with no saved payment (the mobile
    onboarding's lines) are bills (R3): paid on another date than the plan's,
    they move their own money and nobody else's."""
    from tests_mcp.test_money_consistency import base_month

    user = await base_month(seed)
    m = mcp.at(datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc))
    token = m.token(user)
    planned_day = 1 if category == "rent" else 5
    amount = "800.00" if category == "rent" else "100.00"
    await call(
        m,
        token,
        "add_transaction",
        {
            "amount": amount,
            "category": category,
            "date": "2026-10-09",
            "idempotency_key": key(),
        },
    )
    rows = await rows_of(connection, user, month=10)
    assert where(rows, category) == {9: D(amount)}
    assert rows[(planned_day, category)][0] == D("0.00")
    assert no_redistribution(rows)
