"""MITA's money figures agree everywhere, and today's rebalancing is pinned.

Every scenario records its expenses through MITA's own tools, so the real
ledger path runs (``rebuild_month_plan`` and the real-time rebalancer), then
``look`` checks the same month across

* ``get_budget_status``, ``get_budget_forecast``, ``get_calendar_month`` and
  ``show_financial_calendar``;
* the stored ``daily_plan`` rows (money conserved, the spend cache in step);
* the mobile API's figures, computed the way its routes compute them from the
  same rows (the routes themselves need the API environment):
  ``GET /api/budget/forecast`` — ``compute_forecast`` over the stored rows
  with the user's local day, as the route computes it since F-9 — the app's
  day figure, ``GET /api/budget/live_status``: the local day's plan rows
  except money set aside (F-9) — and the app calendar's day budget (the sum
  of a date's rows).

The fixture month (``base_month``), Europe/Sofia, EUR, "today" Monday 19
October 2026 (19 days begun, 12 left):

    1 Oct   rent 800.00, Savings 300.00 (set aside)
    5 Oct   utilities 100.00
    daily   groceries 10.00 (31 days, 310.00)
    Sats    dining out 20.00 on 3, 10, 17, 24, 31 (100.00)

    plan 1,610.00 = commitments 900.00 + set aside 300.00 + everyday 410.00

Tests named ``…_today`` pin MITA's rebalancing as it is (F-8; the owner kept
it on 2026-10-25 — R1, R2, R4 and R5 of
``docs/chatgpt-app/f8-money-model-proposal.md`` were not adopted): they
document it with figures anyone can check by hand, so a change is deliberate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple

from sqlalchemy import text

from app.core.category_priority import is_set_aside
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    compute_forecast,
)
from app.services.monthly_plan_service import SAVINGS_GOAL_CATEGORY
from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)  # 15:00 in Sofia
TODAY = date(2026, 10, 19)
TZ = "Europe/Sofia"
SAVINGS = SAVINGS_GOAL_CATEGORY
SATURDAYS = (3, 10, 17, 24, 31)
D = Decimal
ADJUSTMENT = "_mita_realtime_adjustment_v1"


def key() -> str:
    return uuid.uuid4().hex


async def base_month(seed, *, extra: Optional[Dict[int, Dict[str, str]]] = None):
    user = await seed.user(tz=TZ, currency="EUR", income="3000.00")
    for day in range(1, 32):
        allocations = {"groceries": "10.00"}
        if day == 1:
            allocations.update({"rent": "800.00", SAVINGS: "300.00"})
        if day == 5:
            allocations["utilities"] = "100.00"
        if day in SATURDAYS:
            allocations["dining out"] = "20.00"
        allocations.update((extra or {}).get(day, {}))
        await seed.plan(user, date(2026, 10, day), allocations)
    return user


async def spend(m, token, day: int, amount: str, category: str, *, month: int = 10):
    out = structured(
        await m.call(
            token,
            "add_transaction",
            {
                "amount": amount,
                "category": category,
                "date": date(2026, month, day).isoformat(),
                "idempotency_key": key(),
            },
        )
    )
    return out["transactions"][0]["ref"]


async def pay_bills_on_time(m, token):
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")


Rows = Dict[Tuple[int, str], Tuple[Decimal, Decimal, Decimal]]


async def plan_rows(connection, user, month: int = 10) -> Rows:
    """{(day, category): (planned, cached spent, real-time adjustment)}."""
    result = await connection.execute(
        text(
            "SELECT date, category, planned_amount, spent_amount, plan_json "
            "FROM daily_plan WHERE user_id = :u "
            "AND date >= :start AND date < :end ORDER BY date, category"
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
        day = row["date"].date() if hasattr(row["date"], "date") else row["date"]
        rows[(day.day, row["category"])] = (
            D(str(row["planned_amount"])),
            D(str(row["spent_amount"] or 0)),
            D(str(meta.get(ADJUSTMENT, "0"))),
        )
    return rows


def planned(rows: Rows, category: str, days=None) -> Decimal:
    return sum(
        (
            p
            for (d, c), (p, _s, _a) in rows.items()
            if c == category and (days is None or d in days)
        ),
        D("0"),
    )


async def mobile_commitments(connection, user, month: int):
    """What GET /api/budget/forecast passes the engine: the base plan of the
    rows it loaded and the saved payments due (the same shared helpers)."""
    from sqlalchemy.orm import Session

    from app.db.models import DailyPlan
    from app.services.core.engine.budget_forecast_engine import commitment_expectations
    from app.services.monthly_obligations import obligations_due
    from app.services.monthly_plan_service import base_totals_by_category, month_bounds

    def build(sync_connection):
        session = Session(bind=sync_connection)
        try:
            start, end = month_bounds(2026, month)
            rows = (
                session.query(DailyPlan)
                .filter(
                    DailyPlan.user_id == user.id,
                    DailyPlan.date >= start,
                    DailyPlan.date < end,
                )
                .all()
            )
            due = obligations_due(session, user.id, 2026, month)
            return commitment_expectations(base_totals_by_category(rows), due)
        finally:
            session.close()

    return await connection.run_sync(build)


@dataclass
class Look:
    status: dict
    forecast: dict
    cal: dict
    view: dict
    rows: Rows

    @property
    def summary(self) -> dict:
        return self.cal["summary"]

    def day(self, day: int) -> dict:
        return next(x for x in self.cal["days"] if x["date"].endswith(f"-{day:02d}"))

    def line(self, code: str) -> dict:
        return next(x for x in self.cal["categories"] if code in x["category_codes"])


async def look(
    m, token, connection, user, *, month: int = 10, today: date = TODAY
) -> Look:
    """The month through every surface, and the checks that must always hold."""
    args = {"year": 2026, "month": month}
    status = structured(await m.call(token, "get_budget_status", args))
    forecast = structured(await m.call(token, "get_budget_forecast", args))
    cal = structured(await m.call(token, "get_calendar_month", args))
    view = structured(await m.call(token, "show_financial_calendar", args))
    rows = await plan_rows(connection, user, month)
    summary = cal["summary"]

    # The render tool and the data tool are one calculation.
    assert view["summary"] == summary
    assert view["plan_status"] == cal["plan_status"] == status["plan_status"]
    # Spending is the ledger everywhere.
    assert status["total_spent"] == summary["total_spent"]
    days_spent = sum(D(x["spent"]) for x in cal["days"] if x["spent"] is not None)
    assert days_spent == D(summary["total_spent"])
    if cal["plan_status"] != "generated":
        return Look(status, forecast, cal, view, rows)

    assert forecast["total_spent"] == summary["total_spent"]
    assert (
        status["total_planned"] == forecast["total_planned"] == summary["total_planned"]
    )
    assert status["total_remaining"] == forecast["remaining_budget"]
    assert summary["total_remaining"] == forecast["remaining_budget"]
    assert summary["savings_set_aside"] == forecast["savings_set_aside"]
    assert summary["commitments_reserved"] == forecast["commitments_reserved"]
    left = (
        D(forecast["remaining_budget"])
        - D(forecast["savings_set_aside"])
        - D(forecast["commitments_reserved"])
    )
    assert D(summary["left_to_spend"]) == left
    if cal["month_position"] == "past":
        assert summary["average_per_day"] is None
        assert forecast["safe_daily_limit"] == "0.00"
    else:
        assert summary["average_per_day"] == forecast["safe_daily_limit"]
    # The groups add up to the plan, and so do the dates.
    groups = sum(
        D(summary[k])
        for k in ("commitments_planned", "set_aside_planned", "everyday_planned")
    )
    assert groups == D(summary["total_planned"])
    days_planned = sum(D(x["planned"]) + D(x["set_aside"]) for x in cal["days"])
    assert days_planned == D(summary["total_planned"])
    # The mobile calendar's day budget is the sum of that date's rows (the
    # day-budget invariant); ChatGPT shows it as the date's plan + set aside.
    for x in cal["days"]:
        day_rows = sum(
            (p for (d, _c), (p, _s, _a) in rows.items() if d == int(x["date"][-2:])),
            D("0"),
        )
        assert day_rows == D(x["planned"]) + D(x["set_aside"]), x["date"]
    # Stored rows: money conserved, the spend cache equal to the ledger.
    assert sum(p for p, _s, _a in rows.values()) == D(summary["total_planned"])
    assert sum(s for _p, s, _a in rows.values()) == D(summary["total_spent"])
    assert sum(a for _p, _s, a in rows.values()) == D("0")  # moves, never creates
    # The mobile forecast: the engine over the stored rows, as the API route
    # builds its inputs, with the user's local day.
    mobile = compute_forecast(
        daily_plans=[
            DailyPlanData(date(2026, month, d), c or "other", p, s)
            for (d, c), (p, s, _a) in rows.items()
        ],
        goals=[],
        year=2026,
        month=month,
        today=today,
        commitments=await mobile_commitments(connection, user, month),
    )
    assert format(mobile.total_planned, ".2f") == forecast["total_planned"]
    assert format(mobile.total_spent, ".2f") == forecast["total_spent"]
    assert format(mobile.remaining_budget, ".2f") == forecast["remaining_budget"]
    assert format(mobile.savings_set_aside, ".2f") == forecast["savings_set_aside"]
    reserved = forecast["commitments_reserved"]
    assert format(mobile.commitments_reserved, ".2f") == reserved
    assert format(mobile.safe_daily_limit, ".2f") == forecast["safe_daily_limit"]
    assert mobile.days_remaining == forecast["days_remaining"]
    if cal["month_position"] == "current":
        # The app's day figure (live_status) and ChatGPT's "today" both leave
        # set-aside slices out (owner decision 2026-10-23; F-9).
        app_day = sum(
            (
                p
                for (d, c), (p, _s, _a) in rows.items()
                if d == today.day and not is_set_aside(c)
            ),
            D("0"),
        )
        assert D(status["today"]["planned"]) == app_day
        # Today without bills (R3) is the calendar's everyday part of today.
        cal_today = next(x for x in cal["days"] if x["day_kind"] == "today")
        assert status["today"]["everyday_planned"] == cal_today["planned_everyday"]
        assert status["today"]["everyday_spent"] == cal_today["spent_everyday"]
    return Look(status, forecast, cal, view, rows)


def money(look: Look, *keys: str) -> Tuple[str, ...]:
    return tuple(look.summary[k] for k in keys)


# --- bills ----------------------------------------------------------------------------


async def test_a_bill_paid_on_its_due_date_where_the_plan_holds_it_moves_nothing(
    mcp, seed, connection
):
    m = mcp.at(NOW)
    user = await base_month(seed)
    await seed.scheduled(
        user, category="rent", amount=D("800.00"), scheduled_date=date(2026, 10, 1)
    )
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user)
    assert money(seen, "total_spent", "left_to_spend", "average_per_day") == (
        "900.00",
        "410.00",  # 1,610.00 - 900.00 - 300.00 set aside
        "34.17",  # 410.00 / 12
    )
    assert money(seen, "planned_after_today", "commitments_reserved") == (
        "160.00",  # groceries 12 x 10 + dining out 24th and 31st
        "0.00",  # both bills recorded
    )
    assert all(a == 0 for _p, _s, a in seen.rows.values())  # no rebalancing
    rent = seen.line("rent")
    assert (rent["group"], rent["planned"], rent["spent"]) == (
        "commitment",
        "800.00",
        "800.00",
    )


async def test_f8_a_bill_paid_on_its_due_date_away_from_its_layout_drains_later_dates_today(
    mcp, seed, connection
):
    """Utilities are laid out on the 5th; the saved bill is due on the 18th
    and paid then. Today the 18th counts as €100 of overspending: €20 comes
    from dining out (50 % of 24th + 31st) and €65 from groceries (50 % of
    each day 19th-31st); €15 stays uncovered. The 5th still holds €100, so the
    line plans €185 for one €100 bill and the dates ahead drop from 160 to 80.
    The month's arithmetic is untouched (left 410.00)."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    await seed.scheduled(
        user,
        category="utilities",
        amount=D("100.00"),
        scheduled_date=date(2026, 10, 18),
        merchant="Electricity",
    )
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 18, "100.00", "utilities")
    seen = await look(m, token, connection, user)
    assert money(seen, "left_to_spend", "average_per_day", "planned_after_today") == (
        "410.00",
        "34.17",
        "80.00",
    )
    assert planned(seen.rows, "utilities") == D("185.00")
    assert seen.rows[(5, "utilities")][0] == D("100.00")
    assert seen.rows[(18, "utilities")][:2] == (D("85.00"), D("100.00"))
    assert {d: seen.rows[(d, "groceries")][0] for d in (18, 19, 31)} == {
        18: D("10.00"),
        19: D("5.00"),
        31: D("5.00"),
    }
    assert seen.rows[(24, "dining out")][0] == D("10.00")
    # The bill is paid, so nothing is held for it, although its line still
    # plans 185.00 (the reserve is measured against the reviewed plan, 100.00).
    assert seen.summary["commitments_reserved"] == "0.00"
    assert seen.status["today"]["planned"] == "5.00"  # today's groceries halved
    bill = next(b for b in seen.cal["bills"] if b["category"] == "utilities")
    assert (bill["date"], bill["in_plan"]) == ("2026-10-18", True)


async def test_f8_a_bill_paid_late_counts_as_overspending_on_the_day_paid_today(
    mcp, seed, connection
):
    """Rent planned on the 1st and paid on the 3rd: today the whole €800 is
    overspending on the 3rd; €40 (dining out, 50 % of 10/17/24/31) and €140
    (groceries, 50 % of each day 4th-31st) are moved there, €620 uncovered.
    The 1st keeps its €800, so rent plans €980 for one €800 payment."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    token = m.token(user)
    await spend(m, token, 3, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    seen = await look(m, token, connection, user)
    assert planned(seen.rows, "rent") == D("980.00")
    assert seen.rows[(3, "rent")][:2] == (D("180.00"), D("800.00"))
    assert planned(seen.rows, "groceries", days=range(20, 32)) == D("60.00")
    assert money(
        seen, "left_to_spend", "planned_after_today", "commitments_reserved"
    ) == (
        "410.00",
        "80.00",
        "0.00",  # rent paid: the 180.00 credit is not a second rent
    )


async def test_f8_a_bill_paid_early_is_held_twice_today(mcp, seed, connection):
    """Home internet (€30, a saved bill due on the 27th, planned that day) paid
    on the 15th: today €30 moves from dining out (17th/24th/31st, 10 each) to
    the 15th while the 27th keeps its €30."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={27: {"subscriptions": "30.00"}})
    await seed.scheduled(
        user,
        category="subscriptions",
        amount=D("30.00"),
        scheduled_date=date(2026, 10, 27),
        merchant="Home internet",
    )
    token = m.token(user)
    await pay_bills_on_time(m, token)
    await spend(m, token, 15, "30.00", "subscriptions")
    seen = await look(m, token, connection, user)
    assert planned(seen.rows, "subscriptions") == D("60.00")
    assert seen.rows[(27, "subscriptions")][0] == D("30.00")
    assert [seen.rows[(d, "dining out")][0] for d in (17, 24, 31)] == [D("10.00")] * 3
    assert money(
        seen, "left_to_spend", "planned_after_today", "commitments_reserved"
    ) == (
        "410.00",  # 1,640.00 - 930.00 - 300.00
        "170.00",  # groceries 120 + dining out 20 + the 27th's 30
        "0.00",  # paid early: the 27th's 30.00 is not held again
    )
    assert seen.line("subscriptions")["group"] == "commitment"


async def test_two_bills_in_one_category(mcp, seed, connection):
    """Two saved subscriptions (12 on the 10th, 10 on the 15th), each planned
    on its date. Paid apart: nothing moves. Paid together on the 10th: today
    the 10th is €10 over and dining out (17th/24th/31st) covers it."""
    extra = {10: {"subscriptions": "12.00"}, 15: {"subscriptions": "10.00"}}
    m = mcp.at(NOW)
    apart = await base_month(seed, extra=extra)
    together = await base_month(seed, extra=extra)
    for user in (apart, together):
        await seed.scheduled(
            user,
            category="subscriptions",
            amount=D("12.00"),
            scheduled_date=date(2026, 10, 10),
        )
        await seed.scheduled(
            user,
            category="subscriptions",
            amount=D("10.00"),
            scheduled_date=date(2026, 10, 15),
        )
    token = m.token(apart)
    await spend(m, token, 10, "12.00", "subscriptions")
    await spend(m, token, 15, "10.00", "subscriptions")
    seen = await look(m, token, connection, apart)
    assert all(a == 0 for _p, _s, a in seen.rows.values())
    assert [b["amount"] for b in seen.cal["bills"]] == ["12.00", "10.00"]

    token = m.token(together)
    await spend(m, token, 10, "22.00", "subscriptions")
    seen = await look(m, token, connection, together)
    assert planned(seen.rows, "subscriptions") == D("32.00")  # today: held twice
    assert sorted(seen.rows[(d, "dining out")][0] for d in (17, 24, 31)) == [
        D("16.66"),
        D("16.67"),
        D("16.67"),
    ]


async def test_a_payment_saved_after_its_due_day_counts_from_now_on(
    mcp, seed, connection
):
    """Childcare (180, day 5) saved on 19 October: its next due date is 5
    November, so October shows no childcare bill, yet the line counts as a
    commitment in October (the reviewed budget's rule: a repeating payment due
    before the end of next month is running)."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={5: {"childcare": "180.00"}})
    token = m.token(user)
    saved = structured(
        await m.call(
            token,
            "add_recurring_expense",
            {
                "name": "Kindergarten",
                "amount": "180.00",
                "category": "childcare",
                "recurrence": "monthly",
                "day_of_month": 5,
                "idempotency_key": key(),
            },
        )
    )
    assert saved["next_due_date"] == "2026-11-05"
    await pay_bills_on_time(m, token)
    october = await look(m, token, connection, user)
    assert october.line("childcare")["group"] == "commitment"
    assert [b["category"] for b in october.cal["bills"]] == []
    november = structured(
        await m.call(token, "get_calendar_month", {"year": 2026, "month": 11})
    )
    assert [(b["date"], b["amount"]) for b in november["bills"]] == [
        ("2026-11-05", "180.00")
    ]


async def test_a_payment_that_is_not_running_yet_is_everyday_money(
    mcp, seed, connection
):
    """A monthly payment first due on 7 December does not count in October:
    the childcare line stays everyday money and no bill is shown."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={5: {"childcare": "180.00"}})
    await seed.scheduled(
        user, category="childcare", amount=D("180.00"), scheduled_date=date(2026, 12, 7)
    )
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user)
    assert seen.line("childcare")["group"] == "everyday"
    assert seen.cal["bills"] == []
    assert seen.summary["everyday_planned"] == "590.00"  # 410 + 180


async def test_without_saved_payments_only_the_essentials_are_commitments(
    mcp, seed, connection
):
    m = mcp.at(NOW)
    user = await base_month(seed, extra={7: {"subscriptions": "15.00"}})
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user)
    assert seen.cal["bills"] == []
    groups = {x["category"]: x["group"] for x in seen.cal["categories"]}
    assert groups["rent"] == groups["utilities"] == "commitment"
    assert groups["subscriptions"] == "everyday"  # no saved payment behind it
    assert groups[SAVINGS] == "set_aside"


# --- everyday spending ------------------------------------------------------------------


async def test_a_partly_spent_day(mcp, seed, connection):
    m = mcp.at(NOW)
    user = await base_month(seed)
    token = m.token(user)
    await pay_bills_on_time(m, token)
    await spend(m, token, 19, "4.00", "groceries")
    seen = await look(m, token, connection, user)
    day = seen.day(19)
    assert (
        day["state"],
        day["planned_everyday"],
        day["spent_everyday"],
        day["everyday_left"],
    ) == (
        "within",
        "10.00",
        "4.00",
        "6.00",
    )
    assert (seen.status["today"]["planned"], seen.status["today"]["remaining"]) == (
        "10.00",
        "6.00",
    )
    assert all(a == 0 for _p, _s, a in seen.rows.values())


async def test_money_left_on_earlier_dates_rolls_into_the_average(
    mcp, seed, connection
):
    """Nothing spent on groceries or dining so far: the average counts the
    unspent earlier money (rule D, as today), the dates ahead keep their own
    plan. Gap = groceries 1st-19th 190.00 + dining out 3/10/17 60.00."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user)
    assert money(seen, "left_to_spend", "planned_after_today", "average_per_day") == (
        "410.00",
        "160.00",
        "34.17",
    )
    gap = D(seen.summary["left_to_spend"]) - D(seen.summary["planned_after_today"])
    assert gap == D("250.00")


async def test_overspending_a_flexible_line_takes_from_later_dates_today(
    mcp, seed, connection
):
    """€50 of groceries on the 12th (plan 10): €40 over. Dining out gives
    50 % of 17/24/31 (€30); groceries cannot give to itself; rent, utilities
    and Savings never give. €10 stays uncovered and the month shows it."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    token = m.token(user)
    await pay_bills_on_time(m, token)
    await spend(m, token, 12, "50.00", "groceries")
    seen = await look(m, token, connection, user)
    assert seen.rows[(12, "groceries")][:2] == (D("40.00"), D("50.00"))
    assert [seen.rows[(d, "dining out")][0] for d in (17, 24, 31)] == [D("10.00")] * 3
    assert seen.rows[(1, SAVINGS)][0] == D("300.00")
    assert money(seen, "left_to_spend", "average_per_day", "planned_after_today") == (
        "360.00",  # 1,610.00 - 950.00 - 300.00
        "30.00",
        "140.00",
    )
    # The €10 nothing could cover keeps the 12th over: plan now 40, spent 50.
    assert (seen.day(12)["state"], seen.day(12)["planned_everyday"]) == (
        "over",
        "40.00",
    )


async def test_savings_and_goal_money_never_pay_for_overspending(mcp, seed, connection):
    m = mcp.at(NOW)
    user = await base_month(seed)
    goal = await seed.goal(user, title="Holiday", target_amount=D("600.00"))
    for day in range(20, 32):
        await seed.plan(user, date(2026, 10, day), {"goal_savings": "5.00"}, goal=goal)
    token = m.token(user)
    await pay_bills_on_time(m, token)
    await spend(m, token, 12, "50.00", "groceries")
    seen = await look(m, token, connection, user)
    assert planned(seen.rows, "goal_savings") == D("60.00")
    assert all(
        a == 0
        for (d, c), (_p, _s, a) in seen.rows.items()
        if c in ("goal_savings", SAVINGS)
    )
    assert money(seen, "savings_set_aside", "left_to_spend", "average_per_day") == (
        "360.00",  # 300 + 12 x 5
        "360.00",
        "30.00",
    )


async def test_today_s_savings_slice_is_not_today_s_spending_anywhere(
    mcp, seed, connection
):
    """F-9 (fixed): with €10 of Savings planned today, ChatGPT's today and the
    mobile day figure (live_status, route test in app/tests) are both the €10
    of groceries; the stored rows of the day hold €20."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={19: {SAVINGS: "10.00"}})
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user)
    assert seen.status["today"]["planned"] == "10.00"
    stored_day = sum(
        (p for (d, _c), (p, _s, _a) in seen.rows.items() if d == 19), D("0")
    )
    assert stored_day == D("20.00")


async def test_a_corrected_then_deleted_expense_leaves_the_plan_as_it_was(
    mcp, seed, connection
):
    m = mcp.at(NOW)
    user = await base_month(seed)
    token = m.token(user)
    await pay_bills_on_time(m, token)
    before = await plan_rows(connection, user)
    ref = await spend(m, token, 12, "50.00", "groceries")
    moved = await plan_rows(connection, user)
    assert moved[(17, "dining out")][0] == D("10.00")
    structured(
        await m.call(token, "update_transaction", {"ref": ref, "amount": "8.00"})
    )
    corrected = await look(m, token, connection, user)
    assert {k: v[0] for k, v in corrected.rows.items()} == {
        k: v[0] for k, v in before.items()
    }
    assert corrected.summary["total_spent"] == "908.00"
    structured(await m.call(token, "delete_transaction", {"ref": ref}))
    deleted = await look(m, token, connection, user)
    assert {k: v[0] for k, v in deleted.rows.items()} == {
        k: v[0] for k, v in before.items()
    }
    assert all(a == 0 for _p, _s, a in deleted.rows.values())
    assert deleted.summary["total_spent"] == "900.00"


# --- days, months, users -----------------------------------------------------------------


async def test_expenses_near_midnight_in_sofia_land_on_the_local_day(
    mcp, seed, connection
):
    """EEST (UTC+3): 20:59 UTC on the 14th is 23:59 on the 14th; 21:30 UTC is
    00:30 on the 15th. Every surface puts them on those local days."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    await seed.txn(
        user, "7.00", "groceries", datetime(2026, 10, 14, 20, 59, tzinfo=timezone.utc)
    )
    await seed.txn(
        user, "9.00", "groceries", datetime(2026, 10, 14, 21, 30, tzinfo=timezone.utc)
    )
    token = m.token(user)
    await pay_bills_on_time(m, token)  # a ledger write rebuilds the month
    seen = await look(m, token, connection, user)
    assert (seen.day(14)["spent"], seen.day(15)["spent"]) == ("7.00", "9.00")
    assert (seen.rows[(14, "groceries")][1], seen.rows[(15, "groceries")][1]) == (
        D("7.00"),
        D("9.00"),
    )


async def test_the_night_daylight_saving_time_ends(mcp, seed, connection):
    """25 October 2026 has 25 hours in Sofia (04:00 EEST -> 03:00 EET).
    00:30 UTC is 03:30 EEST and 21:30 UTC is 23:30 EET: both on the 25th."""
    later = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    m = mcp.at(later)
    user = await base_month(seed)
    await seed.txn(
        user, "3.00", "groceries", datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
    )
    await seed.txn(
        user, "4.00", "groceries", datetime(2026, 10, 25, 21, 30, tzinfo=timezone.utc)
    )
    await seed.txn(
        user, "5.00", "groceries", datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc)
    )
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user, today=date(2026, 10, 26))
    assert (seen.day(25)["spent"], seen.day(26)["spent"]) == ("7.00", "5.00")
    assert seen.forecast["days_remaining"] == 5


async def test_a_month_without_a_saved_plan(mcp, seed, connection):
    """No plan: spending only on every surface; nothing invented."""
    m = mcp.at(NOW)
    user = await seed.user(tz=TZ, currency="EUR", income="3000.00")
    token = m.token(user)
    await spend(m, token, 12, "25.00", "groceries")
    seen = await look(m, token, connection, user)
    assert seen.cal["plan_status"] == "not_generated"
    assert seen.forecast["plan_status"] == "not_generated"
    assert seen.forecast["safe_daily_limit"] is None
    assert (seen.summary["total_planned"], seen.summary["average_per_day"]) == (
        None,
        None,
    )
    assert seen.summary["total_spent"] == "25.00"
    assert seen.day(12)["state"] == "unplanned"


async def test_once_the_mobile_app_plans_the_month_every_surface_agrees(
    mcp, seed, connection
):
    """The mobile endpoints generate a missing month before reading it
    (``ensure_month_plan``); MCP read tools never write. After the app has
    generated it, the ChatGPT tools and the mobile forecast agree."""
    from sqlalchemy.orm import Session

    from app.services.monthly_plan_service import ensure_month_plan

    m = mcp.at(NOW)
    user = await seed.user(tz=TZ, currency="EUR", income="3000.00")

    def materialize(sync_connection):
        session = Session(
            bind=sync_connection, join_transaction_mode="create_savepoint"
        )
        try:
            ensure_month_plan(session, user.id, 2026, 10)
        finally:
            session.close()

    await connection.run_sync(materialize)
    token = m.token(user)
    await spend(m, token, 12, "25.00", "groceries")
    seen = await look(m, token, connection, user)
    assert seen.cal["plan_status"] == "generated"
    assert D(seen.summary["total_planned"]) > 0


async def test_a_future_month(mcp, seed, connection):
    m = mcp.at(NOW)
    user = await base_month(seed)
    for day in range(1, 31):
        allocations = {"groceries": "10.00"}
        if day == 1:
            allocations.update({"rent": "800.00", SAVINGS: "300.00"})
        await seed.plan(user, date(2026, 11, day), allocations, stale_spent="0.00")
    token = m.token(user)
    await pay_bills_on_time(m, token)
    seen = await look(m, token, connection, user, month=11)
    assert seen.cal["month_position"] == "future"
    assert money(seen, "left_to_spend", "average_per_day", "planned_after_today") == (
        "300.00",  # 1,400.00 - 300.00 set aside - 800.00 rent held until recorded
        "10.00",  # 300.00 / 30
        "1100.00",
    )
    assert seen.summary["commitments_reserved"] == "800.00"
    assert all(x["spent"] is None for x in seen.cal["days"])
    assert {x["state"] for x in seen.cal["days"]} == {"planned"}


async def test_a_previous_month(mcp, seed, connection):
    m = mcp.at(NOW)
    user = await base_month(seed)
    for day in range(1, 31):
        await seed.plan(user, date(2026, 9, day), {"groceries": "10.00"})
    token = m.token(user)
    await spend(m, token, 3, "25.00", "groceries", month=9)  # rebuilds September
    seen = await look(m, token, connection, user, month=9)
    assert seen.cal["month_position"] == "past"
    assert money(seen, "total_planned", "total_spent", "left_to_spend") == (
        "300.00",
        "25.00",
        "275.00",
    )
    assert seen.summary["days_remaining"] == 0


async def test_two_users_never_touch_each_others_money(mcp, seed, connection):
    m = mcp.at(NOW)
    alice = await base_month(seed)
    bob = await base_month(seed)
    bob_before = await plan_rows(connection, bob)
    token = m.token(alice)
    await pay_bills_on_time(m, token)
    await spend(m, token, 12, "50.00", "groceries")
    alice_seen = await look(m, token, connection, alice)
    assert alice_seen.summary["total_spent"] == "950.00"
    assert {k: v[0] for k, v in (await plan_rows(connection, bob)).items()} == {
        k: v[0] for k, v in bob_before.items()
    }
    bob_token = m.token(bob)
    await spend(m, bob_token, 2, "3.00", "groceries")
    bob_seen = await look(m, bob_token, connection, bob)
    assert bob_seen.summary["total_spent"] == "3.00"
    assert all(a == 0 for _p, _s, a in bob_seen.rows.values())


# --- the review month (F-8 as found) -----------------------------------------------------

REVIEW_NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
REVIEW_SPENDING = [
    (1, "850.00", "rent"),
    (1, "38.40", "groceries"),
    (2, "6.80", "dining"),
    (3, "64.20", "groceries"),
    (4, "18.00", "entertainment"),
    (5, "180.00", "childcare"),
    (6, "22.15", "groceries"),
    (7, "55.00", "gas"),
    (8, "12.40", "dining"),
    (9, "41.90", "groceries"),
    (10, "74.50", "dining"),
    (11, "29.99", "shopping"),
    (12, "16.30", "healthcare"),
    (13, "33.75", "groceries"),
    (14, "7.20", "public_transport"),
    (15, "48.60", "groceries"),
    (16, "21.40", "dining"),
    (17, "86.30", "groceries"),
    (18, "95.00", "utilities"),
    (19, "9.50", "dining"),
    (20, "27.80", "groceries"),
    (21, "52.00", "gas"),
    (22, "14.90", "entertainment"),
    (23, "39.60", "groceries"),
    (24, "23.40", "groceries"),
]


async def test_f8_review_month_as_today(mcp, seed, connection):
    """The account behind F-8, entered through MITA's tools exactly as the
    calendar review did on 24 October (income 3,200, savings target 400,
    rent / kindergarten / utilities / internet saved, the reviewed budget, a
    goal, the month's expenses). The plan and the dates staging showed,
    reproduced. Since the bills' reserve (owner decision 2026-10-25) home
    internet 30.00 (saved, due on the 27th, not recorded) is held, while the
    paid utilities and kindergarten hold nothing although their lines show
    190.00 and 231.04. Medical insurance 134.40 is the budget engine's
    allowance in the reviewed plan, never recorded against, so it stays
    everyday money: left 823.91 and 117.70 a day (before R3: 853.91 and
    121.99; R3 with every SACRED line held: 689.51 and 98.50)."""
    m = mcp.at(REVIEW_NOW)
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    structured(
        await m.call(
            token,
            "update_financial_profile",
            {
                "monthly_net_income": "3200.00",
                "currency": "EUR",
                "timezone": TZ,
                "household_size": 3,
                "monthly_savings_target": "400.00",
            },
        )
    )
    for name, amount, category, day in (
        ("Apartment rent", "850.00", "rent", 1),
        ("Kindergarten", "180.00", "childcare", 5),
        ("Electricity and water", "95.00", "utilities", 18),
        ("Home internet", "30.00", "subscriptions", 27),
    ):
        structured(
            await m.call(
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
        )
    preview = structured(
        await m.call(token, "preview_monthly_budget", {"month": "2026-10"})
    )
    structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
    )
    structured(
        await m.call(
            token,
            "create_savings_goal",
            {
                "title": "Family holiday",
                "target_amount": "1200.00",
                "target_date": "2027-06-30",
                "category": "travel",
                "idempotency_key": key(),
            },
        )
    )
    base = await plan_rows(connection, user)
    base_ahead = sum(
        (
            p
            for (d, c), (p, _s, _a) in base.items()
            if d > 24 and c not in (SAVINGS, "goal_savings")
        ),
        D("0"),
    )
    assert base_ahead == D("299.95")
    items = [
        {"amount": a, "category": c, "date": date(2026, 10, d).isoformat()}
        for d, a, c in REVIEW_SPENDING
    ]
    structured(
        await m.call(
            token, "add_transactions", {"expenses": items, "idempotency_key": key()}
        )
    )
    seen = await look(m, token, connection, user, today=date(2026, 10, 24))
    assert money(
        seen,
        "total_planned",
        "total_spent",
        "left_to_spend",
        "average_per_day",
        "planned_after_today",
        "commitments_reserved",
    ) == ("3160.84", "1869.09", "823.91", "117.70", "12.16", "30.00")
    lines = {x["category"]: (x["planned"], x["spent"]) for x in seen.cal["categories"]}
    assert lines["utilities"] == ("190.00", "95.00")  # one 95.00 bill
    assert lines["childcare"] == ("231.04", "180.00")  # one 180.00 bill
    assert lines["subscriptions"] == ("9.17", "0.00")  # a 30.00 bill due on the 27th
