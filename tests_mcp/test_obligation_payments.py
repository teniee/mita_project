"""A fixed obligation is settled only by the expense the user says paid it.

Owner's real staging month (2026-11, Europe/Sofia, EUR; ``test_bill_due_dates``):
income 2,000, savings 500; Phone 30 on the 10th (``utilities``), Car loan 270
on the 15th (``transportation``), Laptop loan 70 on the 25th (``other``);
their own lines Fuel 200, Cigarettes 200, Coffee and walks 100, Groceries 50,
Housing 50. Their real expenses: a BMW intake pipe €60 on 2 Nov
(``transportation``), personal-care products €23.50 on 3 Nov (``other``),
cigarettes €3.50 and coffee €2 on 3 Nov.

Before 2026-11-03 MITA counted every expense in a bill's category toward the
bill: the reserve held 30 + (270 − 60) + (70 − 23.50) = 286.50 against 370.00
of bills. Now (``obligation_lines``, migration 0041) only an expense linked to
the saved payment (``obligation_ref``) pays it: the car part and the cosmetics
are ordinary spending and the reserve holds 370.00 until the loans are paid.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from app.services.obligation_lines import bill_key
from tests_mcp.test_bill_due_dates import (
    at,
    bills_by_name,
    calendar,
    call,
    key,
    owner_account,
    rows_of,
    where,
)
from tests_mcp.test_money_consistency import look

D = Decimal


async def bill_line_of(connection, user, name: str) -> str:
    """The plan line MITA keeps a saved payment's money on."""
    oid = (
        await connection.execute(
            text(
                "SELECT id FROM scheduled_expenses WHERE user_id = :u AND merchant = :n"
            ),
            {"u": user.id, "n": name},
        )
    ).scalar_one()
    return bill_key(oid)


async def refs(m, token) -> dict:
    out = await call(m, token, "get_recurring_expenses")
    return {i["merchant"]: i for i in out["scheduled_recurring"]}


async def record(m, token, amount, category=None, day=None, **extra):
    arguments = {"amount": amount, "idempotency_key": key()}
    if category is not None:
        arguments["category"] = category
    if day is not None:
        arguments["date"] = date(2026, 11, day).isoformat()
    arguments.update(extra)
    return await call(m, token, "add_transaction", arguments)


async def founders_expenses(mcp, token):
    """The four real expenses, recorded the way ChatGPT recorded them."""
    await record(mcp.at(at(2)), token, "60.00", "transportation", 2)
    m3 = mcp.at(at(3))
    await record(m3, token, "23.50", "other", 3)
    await record(m3, token, "3.50", day=3, budget_line="Cigarettes")
    await record(m3, token, "2.00", day=3, budget_line="Coffee and walks")


# --- Test 1 and Test 2 of the brief ---------------------------------------------


async def test_a_car_part_and_cosmetics_do_not_pay_the_loans(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    await founders_expenses(mcp, token)
    m = mcp.at(at(3))
    seen = await look(m, token, connection, user, month=11, today=date(2026, 11, 3))

    # All four are recorded as spending ...
    assert seen.forecast["total_spent"] == "89.00"
    # ... and none of them pays a bill: 30 + 270 + 70 held, not 286.50.
    assert seen.forecast["commitments_reserved"] == "370.00"
    # left = 2,000 − 89 − 500 savings − 370 bills = 1,041.00, over 27 days.
    assert seen.summary["left_to_spend"] == "1041.00"
    assert seen.forecast["safe_daily_limit"] == "38.56"

    bills = bills_by_name(seen.cal)
    car, laptop = bills["Car loan"], bills["Laptop loan"]
    assert (car["paid"], car["outstanding"], car["state"]) == (
        "0.00",
        "270.00",
        "later",
    )
    assert car["paid_dates"] == []
    assert (laptop["paid"], laptop["outstanding"]) == ("0.00", "70.00")
    # The car part is Transport spending, never the loan's line.
    assert seen.line("transportation")["spent"] == "60.00"
    assert seen.line("other")["spent"] == "23.50"


async def test_the_old_category_rule_is_gone_from_the_stored_plan(
    mcp, seed, connection
):
    """The ledger rebuild no longer moves the loan's money to the car part's
    date: the 15th keeps the whole €270; the car part is unplanned spending
    that MITA's own lines cover (never the user's lines, bills or savings)."""
    user, token = await owner_account(mcp, seed)
    await record(mcp.at(at(2)), token, "60.00", "transportation", 2)
    rows = await rows_of(connection, user)
    loan_line = await bill_line_of(connection, user, "Car loan")
    assert where(rows, loan_line) == {15: D("270.00")}
    planned, spent, adjustment, timing = rows[(2, "transportation")]
    assert spent == D("60.00") and timing == 0
    assert planned == D("60.00") and adjustment == D("60.00")  # covered by MITA
    moved_from = {c for (_d, c), (_p, _s, a, _t) in rows.items() if a < 0}
    assert moved_from and not any(
        c.startswith(("my:", "bill:", "savings")) for c in moved_from
    )


# --- paying a bill --------------------------------------------------------------


async def test_a_linked_payment_pays_the_bill_once(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    await founders_expenses(mcp, token)
    m15 = mcp.at(at(15))
    car_ref = (await refs(m15, token))["Car loan"]["obligation_ref"]
    before = await look(
        m15, token, connection, user, month=11, today=date(2026, 11, 15)
    )
    out = await record(m15, token, "270.00", day=15, obligation_ref=car_ref)
    paid = out["transactions"][0]
    assert paid["category"] == "transportation"  # the payment's own category
    assert paid["paid_obligation"]["name"] == "Car loan"
    assert paid["paid_obligation"]["due_date"] == "2026-11-15"

    after = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    car = bills_by_name(after.cal)["Car loan"]
    assert (car["state"], car["paid"], car["outstanding"]) == ("paid", "270.00", "0.00")
    assert car["paid_dates"] == ["2026-11-15"]
    # spent +270, reserve −270: what is left to spend does not move.
    assert D(after.forecast["total_spent"]) - D(before.forecast["total_spent"]) == 270
    assert (
        D(before.forecast["commitments_reserved"])
        - D(after.forecast["commitments_reserved"])
        == 270
    )
    assert after.summary["left_to_spend"] == before.summary["left_to_spend"]
    # Phone (due the 10th, not paid in MITA) is overdue; the laptop still due.
    states = {n: b["state"] for n, b in bills_by_name(after.cal).items()}
    assert states == {"Phone": "overdue", "Car loan": "paid", "Laptop loan": "later"}


async def test_a_bill_paid_early_moves_its_own_money_only(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    m12 = mcp.at(at(12))
    car_ref = (await refs(m12, token))["Car loan"]["obligation_ref"]
    await record(m12, token, "270.00", day=12, obligation_ref=car_ref)
    rows = await rows_of(connection, user)
    line = await bill_line_of(connection, user, "Car loan")
    assert where(rows, line) == {12: D("270.00")}
    assert rows[(12, line)][3] == D("270.00")  # bill timing, not redistribution
    assert all(a == 0 for (_p, _s, a, _t) in rows.values())
    seen = await look(m12, token, connection, user, month=11, today=date(2026, 11, 12))
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["state"], car["paid_dates"]) == ("paid", ["2026-11-12"])


async def test_a_bill_paid_in_parts_keeps_the_rest_held(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    m15 = mcp.at(at(15))
    car_ref = (await refs(m15, token))["Car loan"]["obligation_ref"]
    await record(m15, token, "100.00", day=15, obligation_ref=car_ref)
    seen = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["state"], car["paid"], car["outstanding"]) == (
        "due_today",
        "100.00",
        "170.00",
    )
    m20 = mcp.at(at(20))
    out = await record(m20, token, "170.00", day=20, obligation_ref=car_ref)
    # the earliest due date not yet paid in full: the 15th, paid late
    assert out["transactions"][0]["paid_obligation"]["due_date"] == "2026-11-15"
    seen = await look(m20, token, connection, user, month=11, today=date(2026, 11, 20))
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["state"], car["paid_dates"]) == ("paid", ["2026-11-15", "2026-11-20"])


async def test_an_existing_expense_is_linked_and_unlinked_by_update(
    mcp, seed, connection
):
    user, token = await owner_account(mcp, seed)
    m15 = mcp.at(at(15))
    out = await record(m15, token, "270.00", "transportation", 15)
    ref = out["transactions"][0]["ref"]
    assert out["transactions"][0]["paid_obligation"] is None
    seen = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    assert bills_by_name(seen.cal)["Car loan"]["state"] == "due_today"
    assert seen.forecast["commitments_reserved"] == "370.00"

    car_ref = (await refs(m15, token))["Car loan"]["obligation_ref"]
    changed = await call(
        m15, token, "update_transaction", {"ref": ref, "obligation_ref": car_ref}
    )
    assert changed["status"] == "updated"
    assert changed["changed_fields"] == ["paid_obligation"]
    seen = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    assert bills_by_name(seen.cal)["Car loan"]["state"] == "paid"
    assert seen.forecast["commitments_reserved"] == "100.00"

    removed = await call(
        m15, token, "update_transaction", {"ref": ref, "obligation_ref": ""}
    )
    assert removed["transaction"]["paid_obligation"] is None
    seen = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    assert bills_by_name(seen.cal)["Car loan"]["state"] == "due_today"
    assert seen.forecast["commitments_reserved"] == "370.00"


async def test_deleting_the_payment_makes_the_bill_unpaid_again(mcp, seed, connection):
    user, token = await owner_account(mcp, seed)
    m15 = mcp.at(at(15))
    car_ref = (await refs(m15, token))["Car loan"]["obligation_ref"]
    out = await record(m15, token, "270.00", day=15, obligation_ref=car_ref)
    await call(m15, token, "delete_transaction", {"ref": out["transactions"][0]["ref"]})
    seen = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["state"], car["paid"]) == ("due_today", "0.00")
    assert seen.forecast["commitments_reserved"] == "370.00"


# --- refusals and isolation ------------------------------------------------------


async def test_a_payment_keeps_its_bill_s_category(mcp, seed):
    _user, token = await owner_account(mcp, seed)
    m = mcp.at(at(15))
    car_ref = (await refs(m, token))["Car loan"]["obligation_ref"]
    result = await m.call(
        token,
        "add_transaction",
        {
            "amount": "270.00",
            "category": "other",
            "obligation_ref": car_ref,
            "idempotency_key": key(),
        },
    )
    assert result.is_error
    assert "recorded under its category" in result.content[0].text


async def test_a_due_date_must_be_one_of_the_bill_s(mcp, seed):
    _user, token = await owner_account(mcp, seed)
    m = mcp.at(at(15))
    car_ref = (await refs(m, token))["Car loan"]["obligation_ref"]
    result = await m.call(
        token,
        "add_transaction",
        {
            "amount": "270.00",
            "obligation_ref": car_ref,
            "obligation_due_date": "2026-11-14",
            "idempotency_key": key(),
        },
    )
    assert result.is_error
    assert "2026-11-15" in result.content[0].text


async def test_another_user_s_obligation_is_not_found(mcp, seed):
    _owner, owner_token = await owner_account(mcp, seed)
    m = mcp.at(at(15))
    car_ref = (await refs(m, owner_token))["Car loan"]["obligation_ref"]
    other = await seed.user(currency="EUR", tz="Europe/Sofia")
    other_token = m.token(other)
    result = await m.call(
        other_token,
        "add_transaction",
        {"amount": "270.00", "obligation_ref": car_ref, "idempotency_key": key()},
    )
    assert result.is_error
    assert "No saved regular payment" in result.content[0].text
    # A transaction reference is never an obligation reference.
    out = await record(m, owner_token, "5.00", "other", 15)
    result = await m.call(
        owner_token,
        "add_transaction",
        {
            "amount": "1.00",
            "obligation_ref": out["transactions"][0]["ref"],
            "idempotency_key": key(),
        },
    )
    assert result.is_error


# --- a plan saved before obligations had lines of their own ----------------------


async def test_a_legacy_plan_is_settled_by_links_too(mcp, seed, connection):
    """A month saved under 2.5.0 holds the car loan under ``transportation``.
    The car part no longer reduces the reserve there either."""
    user = await seed.user(tz="Europe/Sofia", currency="EUR", income="2000.00")
    await seed.scheduled(
        user,
        category="transportation",
        amount=D("270.00"),
        merchant="Car loan",
        scheduled_date=date(2026, 11, 15),
        recurrence="monthly",
    )
    await seed.plan(
        user, date(2026, 11, 15), {"transportation": "270.00"}, stale_spent="0"
    )
    for day in range(1, 31):
        await seed.plan(
            user, date(2026, 11, day), {"groceries": "10.00"}, stale_spent="0"
        )
    m = mcp.at(at(2))
    token = m.token(user)
    await record(m, token, "60.00", "transportation", 2)
    seen = await look(m, token, connection, user, month=11, today=date(2026, 11, 2))
    assert seen.forecast["commitments_reserved"] == "270.00"  # was 210.00
    car = bills_by_name(seen.cal)["Car loan"]
    assert (car["paid"], car["outstanding"]) == ("0.00", "270.00")
    rows = await rows_of(connection, user)
    assert rows[(15, "transportation")][0] == D("270.00")  # the loan's money stays
    assert rows[(2, "transportation")][2] == D("60.00")  # the part was covered

    m15 = mcp.at(at(15))
    car_ref = (await refs(m15, token))["Car loan"]["obligation_ref"]
    await record(m15, token, "270.00", day=15, obligation_ref=car_ref)
    seen = await look(m15, token, connection, user, month=11, today=date(2026, 11, 15))
    assert seen.forecast["commitments_reserved"] == "0.00"
    assert bills_by_name(seen.cal)["Car loan"]["state"] == "paid"


async def test_a_weekly_bill_s_payment_pays_the_date_it_names(mcp, seed, connection):
    user = await seed.user(tz="Europe/Sofia", currency="EUR", income="2000.00")
    await seed.profile(
        user,
        income_confirmed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        currency_confirmed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        timezone_confirmed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )
    m = mcp.at(at(2))
    token = m.token(user)
    await call(
        m,
        token,
        "add_recurring_expense",
        {
            "name": "Cleaner",
            "amount": "25.00",
            "category": "other",
            "recurrence": "weekly",
            "weekday": "wednesday",
            "idempotency_key": key(),
        },
    )
    preview = await call(m, token, "preview_monthly_budget", {"month": "2026-11"})
    await call(m, token, "save_monthly_budget", {"draft_token": preview["draft_token"]})
    ref = (await refs(m, token))["Cleaner"]["obligation_ref"]
    m12 = mcp.at(at(12))
    out = await record(
        m12,
        token,
        "25.00",
        day=12,
        obligation_ref=ref,
        obligation_due_date="2026-11-18",  # paid the next week's visit early
    )
    assert out["transactions"][0]["paid_obligation"]["due_date"] == "2026-11-18"
    seen = await look(m12, token, connection, user, month=11, today=date(2026, 11, 12))
    by_date = {b["date"]: b for b in seen.cal["bills"]}
    assert by_date["2026-11-18"]["state"] == "paid"
    assert by_date["2026-11-11"]["state"] == "overdue"  # 11th not paid in MITA
    assert seen.forecast["commitments_reserved"] == "75.00"  # 4, 11, 25 unpaid


async def test_ids_never_leave_mita(mcp, seed, connection):
    """Refs are opaque: the obligation's database id is not in any result."""
    _user, token = await owner_account(mcp, seed)
    m = mcp.at(at(3))
    ids = (
        (
            await connection.execute(
                text("SELECT id FROM scheduled_expenses WHERE user_id = :u"),
                {"u": _user.id},
            )
        )
        .scalars()
        .all()
    )
    texts = [
        str(await call(m, token, "get_recurring_expenses")),
        str(await calendar(m, token, 3)),
    ]
    for oid in ids:
        assert str(oid) not in texts[0] and str(oid) not in texts[1]
        assert uuid.UUID(str(oid)).hex not in texts[0] + texts[1]
