"""R3 — the month's unpaid bills are held out of the safe daily amount.

The rule (docs/chatgpt-app/r3-bills-reserve.md): a bill is money MITA knows a
payment will take this month and can see being paid — the categories of the
user's saved regular payments that count in the month, and the essential
rent, mortgage and utilities lines — always a category an expense can be
recorded under. Each needs its reviewed (base) plan, or the saved payments due
on it when more; what is recorded under it this month counts as paid:

    held   = per bill max(0, need - recorded)
    left   = plan - spent - protected savings - held
    safe   = left / days after today

Every scenario runs through MITA's own tools and ``look`` (from
``test_money_consistency``), so each one is also checked across
``get_budget_status``, ``get_budget_forecast``, ``get_calendar_month``,
``show_financial_calendar``, the stored rows and the mobile API's forecast.

The fixture month (``base_month``): Europe/Sofia, EUR, today Monday 19
October 2026, 12 days after today. Plan 1,610.00 = rent 800.00 (1st) +
utilities 100.00 (5th) + Savings 300.00 (1st, set aside) + groceries 10.00 a
day (310.00) + dining out 20.00 on Saturdays (100.00): 410.00 of everyday
money, 34.17 a day. Because a held bill moves to "spent" when it is
recorded, paying a bill never changes the everyday money — that is what the
tests below show with figures anyone can check by hand.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from tests_mcp.conftest import structured
from tests_mcp.test_money_consistency import (
    NOW,
    SAVINGS,
    TZ,
    D,
    base_month,
    key,
    look,
    money,
    plan_rows,
    spend,
)

FIGURES = ("left_to_spend", "average_per_day", "commitments_reserved")


async def save_payment(
    seed, user, category: str, amount: str, day: int, *, month: int = 10, **kw
):
    return await seed.scheduled(
        user,
        category=category,
        amount=D(amount),
        scheduled_date=date(2026, month, day),
        **kw,
    )


# --- 1, 2, 9: a saved bill due later this month ----------------------------------------


async def test_rent_due_later_is_held_until_it_is_recorded_then_spent_once(
    mcp, seed, connection
):
    """Scenario 1, 2 and 9. Rent (800.00, saved, due on the 25th) is in the
    reviewed plan too: it is held once (max of plan and payment, never both).

    Unpaid:   1,610.00 - 100.00 spent - 300.00 savings - 800.00 rent = 410.00
              410.00 / 12 = 34.17           (before R3: 1,210.00 / 12 = 100.83)
    Recorded: 1,610.00 - 900.00 spent - 300.00 savings -   0.00      = 410.00
    """
    m = mcp.at(NOW)
    user = await base_month(seed)
    await save_payment(seed, user, "rent", "800.00", 25, merchant="Apartment")
    token = m.token(user)
    await spend(m, token, 5, "100.00", "utilities")
    unpaid = await look(m, token, connection, user)
    assert money(unpaid, *FIGURES) == ("410.00", "34.17", "800.00")
    assert unpaid.forecast["remaining_budget"] == "1510.00"
    assert [(b["date"], b["amount"]) for b in unpaid.cal["bills"]] == [
        ("2026-10-25", "800.00")
    ]
    assert unpaid.line("rent")["group"] == "commitment"

    await spend(m, token, 1, "800.00", "rent")
    paid = await look(m, token, connection, user)
    assert money(paid, *FIGURES) == ("410.00", "34.17", "0.00")
    assert paid.forecast["total_spent"] == "900.00"  # counted once, as spent


# --- 3: a saved internet bill ----------------------------------------------------------


async def test_a_saved_internet_bill_is_held_the_same_everywhere(mcp, seed, connection):
    """Scenario 3. Home internet (30.00, saved under subscriptions, due on the
    27th, planned that day): 1,640.00 - 900.00 - 300.00 - 30.00 = 410.00."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={27: {"subscriptions": "30.00"}})
    await save_payment(seed, user, "subscriptions", "30.00", 27, merchant="Internet")
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    seen = await look(m, token, connection, user)
    assert money(seen, *FIGURES) == ("410.00", "34.17", "30.00")
    assert seen.forecast["commitments_reserved"] == "30.00"
    assert seen.view["summary"]["commitments_reserved"] == "30.00"
    assert seen.line("subscriptions")["group"] == "commitment"


# --- 4: a SACRED line no expense is recorded under ---------------------------------------


async def test_the_medical_insurance_allowance_is_everyday_money_never_held_twice(
    mcp, seed, connection
):
    """Scenario 4. The budget engine's medical insurance allowance (134.40, as
    in the review account; SACRED, so never a rebalancing donor) has no saved
    payment, and no expense is ever recorded under "insurance medical" — the
    person records "insurance" or "healthcare". Held, it could never be
    released: once paid it would be subtracted twice. So it is not a bill.

    Before paying: 1,744.40 - 900.00 - 300.00 = 544.40, 45.37 a day.
    Paid as "insurance": 544.40 - 134.40 = 410.00 — the payment once.
    (Holding the line: 410.00 before and 275.60 after — counted twice.)"""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={5: {"insurance medical": "134.40"}})
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    before = await look(m, token, connection, user)
    assert money(before, *FIGURES) == ("544.40", "45.37", "0.00")
    assert before.line("insurance medical")["group"] == "everyday"

    await spend(m, token, 5, "134.40", "insurance")
    after = await look(m, token, connection, user)
    assert money(after, *FIGURES) == ("410.00", "34.17", "0.00")


async def test_a_stated_utilities_line_is_held_without_a_saved_payment(
    mcp, seed, connection
):
    """Scenario 4 (other side). Rent and utilities lines exist only because
    the person stated them; with no saved payment row they are still bills
    (rent recorded): 1,610.00 - 800.00 - 300.00 - 100.00 utilities = 410.00."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    seen = await look(m, token, connection, user)
    assert seen.cal["bills"] == []
    assert money(seen, *FIGURES) == ("410.00", "34.17", "100.00")
    assert seen.line("utilities")["group"] == "commitment"


# --- 5, 6: savings and goals -----------------------------------------------------------------


async def test_savings_and_goal_money_are_subtracted_once_and_never_held_as_bills(
    mcp, seed, connection
):
    """Scenario 5 and 6. Savings 300.00 + a goal's 5.00 a day on 20-31 (60.00)
    are protected savings; the unpaid internet bill (30.00) is held; nothing
    is subtracted twice: 1,700.00 - 900.00 - 360.00 - 30.00 = 410.00."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={27: {"subscriptions": "30.00"}})
    goal = await seed.goal(user, title="Holiday", target_amount=D("600.00"))
    for day in range(20, 32):
        await seed.plan(user, date(2026, 10, day), {"goal_savings": "5.00"}, goal=goal)
    await save_payment(seed, user, "subscriptions", "30.00", 27)
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    seen = await look(m, token, connection, user)
    assert seen.forecast["savings_set_aside"] == "360.00"
    assert money(seen, *FIGURES) == ("410.00", "34.17", "30.00")
    assert {seen.line(c)["group"] for c in (SAVINGS, "goal_savings")} == {"set_aside"}


# --- 7: the bill differs from its plan ---------------------------------------------------------


@pytest.mark.parametrize(
    "saved,paid,expected",
    [
        # paid less than planned: the line's unused 20.00 stays held — by line,
        # never matched to a bill by amount (owner-approved R3 wording)
        ("800.00", "780.00", ("410.00", "34.17", "20.00")),
        # paid more: nothing held; the extra 50.00 is spending, once
        ("800.00", "850.00", ("360.00", "30.00", "0.00")),
        # the saved payment rose above the reviewed plan: the payment is held
        ("850.00", None, ("360.00", "30.00", "850.00")),
    ],
)
async def test_a_bill_that_differs_from_its_plan(
    mcp, seed, connection, saved, paid, expected
):
    """Scenario 7, against rent planned at 800.00 and due on the 25th."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    await save_payment(seed, user, "rent", saved, 25)
    token = m.token(user)
    await spend(m, token, 5, "100.00", "utilities")
    if paid:
        await spend(m, token, 1, paid, "rent")
    seen = await look(m, token, connection, user)
    assert money(seen, *FIGURES) == expected


# --- 8: two bills in one category ------------------------------------------------------------


async def test_two_saved_bills_in_one_category_are_held_once_each(
    mcp, seed, connection
):
    """Scenario 8. Subscriptions 12.00 (10th) and 10.00 (15th), planned on
    their dates: the category needs 22.00, held once — not 44.00 (plan and
    payments) — and paying the first releases its share."""
    extra = {10: {"subscriptions": "12.00"}, 15: {"subscriptions": "10.00"}}
    m = mcp.at(NOW)
    user = await base_month(seed, extra=extra)
    await save_payment(seed, user, "subscriptions", "12.00", 10)
    await save_payment(seed, user, "subscriptions", "10.00", 15)
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    unpaid = await look(m, token, connection, user)
    assert money(unpaid, *FIGURES) == ("410.00", "34.17", "22.00")
    await spend(m, token, 10, "12.00", "subscriptions")
    half = await look(m, token, connection, user)
    assert money(half, *FIGURES) == ("410.00", "34.17", "10.00")


# --- 10, 11, 12: due today, tomorrow, earlier ------------------------------------------------


@pytest.mark.parametrize("due", [19, 20, 10], ids=["today", "tomorrow", "earlier"])
async def test_an_unrecorded_bill_is_held_whatever_its_date_in_the_month(
    mcp, seed, connection, due
):
    """Scenario 10, 11, 12. The reserve does not depend on the due date inside
    the month: a bill due today, tomorrow or earlier and not recorded is held
    until it is recorded (MITA cannot know an unrecorded bill was paid)."""
    m = mcp.at(NOW)
    user = await base_month(seed, extra={due: {"subscriptions": "30.00"}})
    await save_payment(seed, user, "subscriptions", "30.00", due)
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    seen = await look(m, token, connection, user)
    assert money(seen, *FIGURES) == ("410.00", "34.17", "30.00")
    assert [b["date"] for b in seen.cal["bills"]] == [f"2026-10-{due:02d}"]


# --- 13: no bills --------------------------------------------------------------------------------


async def test_a_month_without_bills_keeps_the_safe_amount_it_had_before_r3(
    mcp, seed, connection
):
    """Scenario 13. Groceries 10.00 a day and Savings 300.00, no rent, no
    utilities, no saved payment: nothing is held and the figure is the
    pre-R3 one, (606.00 - 300.00) / 12 = 25.50."""
    m = mcp.at(NOW)
    user = await seed.user(tz=TZ, currency="EUR", income="3000.00")
    for day in range(1, 32):
        allocations = {"groceries": "10.00"}
        if day == 1:
            allocations[SAVINGS] = "300.00"
        await seed.plan(user, date(2026, 10, day), allocations)
    token = m.token(user)
    await spend(m, token, 19, "4.00", "groceries")
    seen = await look(m, token, connection, user)
    assert money(seen, *FIGURES) == ("306.00", "25.50", "0.00")
    assert seen.summary["commitments_planned"] == "0.00"


# --- 14: bills larger than what is left -------------------------------------------------------


async def test_bills_beyond_what_is_left_give_a_negative_average_not_an_error(
    mcp, seed, connection
):
    """Scenario 14. Rent unpaid (800.00 held) after 450.00 of groceries on
    the 12th: 1,610.00 - 550.00 - 300.00 - 800.00 = -40.00, -3.33 a day — the
    plan no longer covers the bills; every surface says so with the same
    figure (negative averages allowed, owner decision 2026-10-25)."""
    m = mcp.at(NOW)
    user = await base_month(seed)
    await save_payment(seed, user, "rent", "800.00", 25)
    token = m.token(user)
    await spend(m, token, 5, "100.00", "utilities")
    await spend(m, token, 12, "450.00", "groceries")
    seen = await look(m, token, connection, user)
    assert money(seen, *FIGURES) == ("-40.00", "-3.33", "800.00")
    assert seen.forecast["safe_daily_limit"] == "-3.33"


# --- 15, 16: an ended month ----------------------------------------------------------------------


async def test_an_ended_month_is_read_as_stored_and_rebuilt_only_when_edited(
    mcp, seed, connection
):
    """Scenario 15 and 16. September: rent 800.00 on the 1st, groceries 10.00
    a day, the saved rent running. Viewed on 19 October nothing is written;
    the unrecorded rent is held in "left when the month ended". Recording the
    September rent rebuilds September through the existing ledger path, and
    the rent moves from held to spent (the left figure does not change)."""
    m = mcp.at(NOW)
    user = await seed.user(tz=TZ, currency="EUR", income="3000.00")
    for day in range(1, 31):
        allocations = {"groceries": "10.00"}
        if day == 1:
            allocations["rent"] = "800.00"
        await seed.plan(user, date(2026, 9, day), allocations, stale_spent="0.00")
    await save_payment(seed, user, "rent", "800.00", 25, month=10)
    token = m.token(user)

    before = await plan_rows(connection, user, month=9)
    viewed = await look(m, token, connection, user, month=9)
    assert (
        await plan_rows(connection, user, month=9) == before
    )  # viewing writes nothing
    assert viewed.cal["month_position"] == "past"
    assert (
        viewed.summary["left_to_spend"],
        viewed.summary["average_per_day"],
        viewed.summary["commitments_reserved"],
        viewed.forecast["safe_daily_limit"],
    ) == ("300.00", None, "800.00", "0.00")

    structured(
        await m.call(
            token,
            "add_transaction",
            {
                "amount": "800.00",
                "category": "rent",
                "date": "2026-09-01",
                "idempotency_key": key(),
            },
        )
    )
    edited = await look(m, token, connection, user, month=9)
    assert {k: v[0] for k, v in edited.rows.items()} == {
        k: v[0] for k, v in before.items()
    }  # the reviewed plan of the ended month is unchanged
    assert (
        edited.summary["left_to_spend"],
        edited.summary["commitments_reserved"],
        edited.summary["total_spent"],
    ) == ("300.00", "0.00", "800.00")


# --- 17: the first minutes of a month in Sofia -----------------------------------------------


async def test_the_month_turns_at_local_midnight_in_sofia(mcp, seed, connection):
    """Scenario 17. 22:30 UTC on 31 October is 00:30 on 1 November in Sofia
    (EET, UTC+2 since 25 October). The default month is November, the rent
    saved for the 1st is November's bill, and 29 days follow today:
    (1,400.00 - 300.00 - 800.00) / 29 = 10.34."""
    late = datetime(2026, 10, 31, 22, 30, tzinfo=timezone.utc)
    m = mcp.at(late)
    user = await seed.user(tz=TZ, currency="EUR", income="3000.00")
    for day in range(1, 31):
        allocations = {"groceries": "10.00"}
        if day == 1:
            allocations.update({"rent": "800.00", SAVINGS: "300.00"})
        await seed.plan(user, date(2026, 11, day), allocations, stale_spent="0.00")
    await save_payment(seed, user, "rent", "800.00", 1, month=11)
    token = m.token(user)
    default = structured(await m.call(token, "get_budget_forecast"))
    assert (default["year"], default["month"], default["days_remaining"]) == (
        2026,
        11,
        29,
    )
    seen = await look(m, token, connection, user, month=11, today=date(2026, 11, 1))
    assert seen.forecast == default
    assert money(seen, *FIGURES) == ("300.00", "10.34", "800.00")


# --- a saved bill shown on a paired everyday line ------------------------------------------


async def test_a_saved_pass_never_takes_the_everyday_allowance_it_is_shown_with(
    mcp, seed, connection
):
    """A monthly transit pass (30.00, saved under public_transport, due on the
    1st, in the reviewed plan as its own line) is shown on the "transport
    public" line with the 5.00-a-day allowance. Only the pass is held: the
    mobile API (stored categories) and ChatGPT (budget lines) must agree. A
    2.00 ticket recorded as public_transport is spending on that category, so
    it uses the pass's line (by line, never by amount): 30.00 - 2.00 = 28.00.

    1,795.00 - 902.00 - 300.00 - 28.00 = 565.00, 47.08 a day.
    (Holding the whole line: 185.00 - 2.00 = 183.00, 34.17 a day.)"""
    extra = {d: {"transport public": "5.00"} for d in range(2, 32)}
    extra[1] = {"transport public": "5.00", "public_transport": "30.00"}
    m = mcp.at(NOW)
    user = await base_month(seed, extra=extra)
    await save_payment(seed, user, "public_transport", "30.00", 1, merchant="Pass")
    token = m.token(user)
    await spend(m, token, 1, "800.00", "rent")
    await spend(m, token, 5, "100.00", "utilities")
    await spend(m, token, 19, "2.00", "public_transport")
    seen = await look(m, token, connection, user)
    assert money(seen, *FIGURES) == ("565.00", "47.08", "28.00")


# --- today on a bill's date ----------------------------------------------------------------


async def test_today_s_everyday_money_leaves_a_bill_planned_today_out(
    mcp, seed, connection
):
    """On 1 October, the date the plan lays rent on: today's plan is rent
    800.00 + groceries 10.00 (the 300.00 of Savings is set aside), but only the
    groceries are free to spend — the answer to "Can I afford dinner out
    tonight?" must not count the unpaid rent (R3). The figures equal the
    calendar's everyday part of today."""
    first = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)  # 12:00 in Sofia
    m = mcp.at(first)
    user = await base_month(seed)
    await save_payment(seed, user, "rent", "800.00", 1)
    token = m.token(user)
    await spend(m, token, 1, "4.00", "groceries")
    seen = await look(m, token, connection, user, today=date(2026, 10, 1))
    today = seen.status["today"]
    assert (today["planned"], today["remaining"]) == ("810.00", "806.00")
    assert (
        today["everyday_planned"],
        today["everyday_spent"],
        today["everyday_remaining"],
    ) == ("10.00", "4.00", "6.00")
    assert seen.forecast["commitments_reserved"] == "900.00"  # rent + utilities
