"""Saved payments are safe with the scheduler running (PR #288 review P1, P2).

P1 — the repository ships a daily processor (``rq_scheduler`` → 06:00 UTC →
``cron_task_scheduled_expenses.run_scheduled_expenses_batch``) that turns
every pending scheduled expense due today into a transaction. Nothing runs it
on Railway today, but MITA must not depend on that: a bill saved in ChatGPT
is an obligation paid only by an expense the user links to it
(``obligation_payments``). Here the processor itself runs, on the test's
database, on the owner's reference profile (income 2,500; savings 500; bills
505; flexible budgets 1,115; 380 unallocated): it must create nothing for a
ChatGPT bill, push nothing about it, never record a linked payment twice —
and still do what it always did for a scheduled expense made in the app.

P2 — a monthly payment kept only its clamped next date, so "the 31st" saved
in November became the 30th of every month. The requested day is now kept
(``scheduled_expenses.day_of_month``, migration 0045) and clamped month by
month; rows that never kept one behave exactly as before.

Notifications need Firebase, which the MCP environment does not install: the
module is replaced by a recorder, so the test sees every push the processor
would send.
"""

from __future__ import annotations

import sys
import types
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.mcp.__main__ import REQUIRED_COLUMNS
from app.mcp.writes.recurring import requested_day_of_month
from app.services.monthly_obligations import (
    APP_ORIGIN,
    CHATGPT_ORIGIN,
    UNKNOWN_ORIGIN,
    dated_obligations,
    due_dates_in_month,
)
from tests_mcp.test_flexible_envelopes_calendar import call, key, noon, see

D = Decimal

# The owner's reference profile (fictional breakdown of the real totals).
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


async def reference_profile(mcp, seed):
    """The reference month, saved on 2 November through ChatGPT."""
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
    assert draft["unallocated"] == "380.00" and draft["savings_allocation"] == "500.00"
    saved = await call(
        m2, token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
    )
    assert saved["status"] == "saved"
    return user, token


async def run_scheduler(connection, monkeypatch, today: date):
    """What ``rq_scheduler`` runs at 06:00 UTC, on the test's transaction;
    returns its summary and every push it would have sent."""
    from app.services.core.engine import cron_task_scheduled_expenses as cron

    pushed: List[Tuple[str, str, str]] = []

    class Notifications:  # records instead of calling Firebase
        def __init__(self, db):
            pass

        def notify_scheduled_expense_reminder(self, **kw):
            pushed.append(("reminder", kw["category"], f"{kw['amount']:.2f}"))

        def notify_scheduled_expense_processed(self, **kw):
            pushed.append(("processed", kw["category"], f"{kw['amount']:.2f}"))

    stub = types.ModuleType("app.services.notification_integration")
    stub.NotificationIntegration = Notifications
    monkeypatch.setitem(sys.modules, "app.services.notification_integration", stub)
    session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        summary = await session.run_sync(
            lambda s: cron.run_scheduled_expenses_batch(s, today=today)
        )
        await session.commit()
    finally:
        await session.close()
    return summary, pushed


async def ledger(connection, user) -> Tuple[int, Decimal]:
    row = (
        await connection.execute(
            text(
                "SELECT count(*), coalesce(sum(amount), 0) FROM transactions "
                "WHERE user_id = :u AND deleted_at IS NULL"
            ),
            {"u": user.id},
        )
    ).one()
    return row[0], D(str(row[1]))


async def saved(connection, user) -> List[tuple]:
    """(merchant, status, origin, day_of_month, scheduled_date, transaction_id)"""
    rows = await connection.execute(
        text(
            "SELECT merchant, status, origin, day_of_month, scheduled_date, "
            "transaction_id FROM scheduled_expenses WHERE user_id = :u "
            "ORDER BY scheduled_date, merchant, created_at"
        ),
        {"u": user.id},
    )
    return [tuple(r) for r in rows]


async def due_in(connection, user, year: int, month: int):
    """``monthly_obligations.dated_obligations``: the one due-date rule the
    mobile forecast, the ledger's bill lines and the month rollover read."""

    def read(sync_connection):
        with Session(bind=sync_connection) as session:
            return dated_obligations(session, user.id, year, month)

    return await connection.run_sync(read)


# --- P1: the scheduler never pays a bill saved in ChatGPT ----------------------------------


async def test_the_scheduler_never_turns_a_bill_saved_in_chatgpt_into_an_expense(
    mcp, seed, connection, monkeypatch
):
    user, token = await reference_profile(mcp, seed)
    rows = await saved(connection, user)
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        ("Phone and internet", "pending", "chatgpt", 5),
        ("Car loan", "pending", "chatgpt", 15),
        ("Home insurance", "pending", "chatgpt", 20),
        ("Laptop loan", "pending", "chatgpt", 25),
    ]

    # The scheduler on the day of saving (the phone bill is 3 days away) and
    # on every due date: nothing is recorded, nothing pushed, nothing rolled.
    for day in (2, 5, 15, 20, 25):
        summary, pushed = await run_scheduler(
            connection, monkeypatch, date(2026, 11, day)
        )
        assert summary["processed"] == 0 and summary["reminders_sent"] == 0, day
        assert pushed == [], day
        assert await ledger(connection, user) == (0, D("0.00")), day
        assert await saved(connection, user) == rows, day

    # The month as the user sees it on the 25th: every bill unpaid and held,
    # savings protected, the 380 still on no line.
    seen = await see(mcp.at(noon(25)), token)
    s = seen.summary
    assert s["total_spent"] == "0.00"
    assert s["commitments_reserved"] == "505.00"
    assert s["savings_set_aside"] == "500.00"
    assert s["total_planned"] == "2120.00"  # 2,500 − 380 unallocated
    assert s["left_to_spend"] == "1115.00"  # 2,120 − 500 − 505
    assert all(b["paid"] == "0.00" for b in seen.data["bills"])

    # Only the user's own linked payment pays a bill — once, even with the
    # scheduler running on its due date afterwards.
    m15 = mcp.at(noon(15))
    loan = next(
        b for b in seen.data["bills"] if b["date"] == "2026-11-15" and b["name"]
    )
    paid = await call(
        m15,
        token,
        "add_transaction",
        {
            "amount": "270.00",
            "category": "transportation",
            "obligation_ref": loan["obligation_ref"],
            "date": "2026-11-15",
            "idempotency_key": key(),
        },
    )
    assert paid["status"] == "recorded"
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 15))
    assert summary["processed"] == 0 and pushed == []
    assert await ledger(connection, user) == (1, D("270.00"))
    after = await see(m15, token)
    assert after.summary["commitments_reserved"] == "235.00"  # 505 − 270
    assert {b["name"]: b["state"] for b in after.data["bills"]}["Car loan"] == "paid"


async def test_a_scheduled_expense_from_the_app_still_fires_once_and_rolls_forward(
    mcp, seed, connection, monkeypatch
):
    """Legacy behaviour kept for rows made in the mobile app (origin "app"):
    a transaction on the due date, a push, the next month scheduled — the
    day asked for when the row kept one (P2), the date's day otherwise."""
    user, token = await reference_profile(mcp, seed)
    await seed.scheduled(
        user,
        category="utilities",
        amount=D("60.00"),
        scheduled_date=date(2026, 11, 30),
        recurrence="monthly",
        merchant="Water",
        day_of_month=31,
        origin=APP_ORIGIN,
    )
    await seed.scheduled(
        user,
        category="subscriptions",
        amount=D("9.99"),
        scheduled_date=date(2026, 11, 30),
        recurrence="monthly",
        merchant="Music",
        origin=APP_ORIGIN,
    )
    # three days ahead: the app rows are reminded of, ChatGPT's bills are not
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 27))
    assert sorted(pushed) == [
        ("reminder", "subscriptions", "9.99"),
        ("reminder", "utilities", "60.00"),
    ]
    # until it records them they are bills like any other: held, unpaid
    before = await see(mcp.at(noon(27)), token)
    assert before.summary["commitments_reserved"] == "574.99"  # 505 + 60 + 9.99
    # the due date: both fire, once
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 30))
    assert summary["processed"] == 2 and summary["recurrences_scheduled"] == 2
    assert sorted(pushed) == [
        ("processed", "subscriptions", "9.99"),
        ("processed", "utilities", "60.00"),
    ]
    assert await ledger(connection, user) == (2, D("69.99"))
    # Recorded once and held no more: the rows the processor scheduled next
    # are December's payments, never a second November one (each app row is
    # one occurrence; it never counts before its own date).
    after = await see(mcp.at(noon(30)), token)
    assert after.summary["total_spent"] == "69.99"
    assert after.summary["commitments_reserved"] == "505.00"  # ChatGPT's four
    assert {b["name"] for b in after.data["bills"]} == {
        name for name, *_ in REFERENCE_BILLS
    }
    forecast = await call(mcp.at(noon(30)), token, "get_budget_forecast")
    assert forecast["commitments_reserved"] == "505.00"
    # the one rule behind the mobile forecast, the ledger's bill lines and the
    # month rollover: nothing left of the processed rows in November
    november_dates = await due_in(connection, user, 2026, 11)
    assert {o.merchant for o in november_dates} == {
        name for name, *_ in REFERENCE_BILLS
    }
    december = await see(mcp.at(noon(30)), token, 2026, 12)
    assert sorted(
        (b["date"], b["name"])
        for b in december.data["bills"]
        if b["date"] >= "2026-12-30"
    ) == [("2026-12-30", "Music"), ("2026-12-31", "Water")]
    app_rows = [r for r in await saved(connection, user) if r[2] == "app"]
    assert [(r[0], r[1], r[3], r[4]) for r in app_rows] == [
        ("Music", "processed", None, date(2026, 11, 30)),
        ("Water", "processed", 31, date(2026, 11, 30)),
        ("Music", "pending", 30, date(2026, 12, 30)),  # its own day, kept
        ("Water", "pending", 31, date(2026, 12, 31)),  # the 31st asked for
    ]
    assert all(r[5] is not None for r in app_rows if r[1] == "processed")
    # a retry the same day records nothing more
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 30))
    assert summary["processed"] == 0 and pushed == []
    assert await ledger(connection, user) == (2, D("69.99"))


async def test_a_payment_linked_in_chatgpt_is_never_recorded_twice(
    mcp, seed, connection, monkeypatch
):
    """An app row the user paid through ChatGPT (an expense linked with its
    obligation_ref) is not recorded a second time by the processor: it is
    marked processed with the user's own transaction and rolls forward."""
    user, token = await reference_profile(mcp, seed)
    await seed.scheduled(
        user,
        category="rent",
        amount=D("850.00"),
        scheduled_date=date(2026, 11, 28),
        recurrence="monthly",
        merchant="Flat",
        origin=APP_ORIGIN,
    )
    m28 = mcp.at(noon(28))
    recurring = await call(m28, token, "get_recurring_expenses")
    flat = next(i for i in recurring["scheduled_recurring"] if i["merchant"] == "Flat")
    paid = await call(
        m28,
        token,
        "add_transaction",
        {
            "amount": "850.00",
            "category": "rent",
            "obligation_ref": flat["obligation_ref"],
            "date": "2026-11-28",
            "idempotency_key": key(),
        },
    )
    assert paid["status"] == "recorded"
    assert await ledger(connection, user) == (1, D("850.00"))
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 28))
    assert summary["processed"] == 0 and summary["paid_through_links"] == 1
    assert pushed == []
    assert await ledger(connection, user) == (1, D("850.00"))  # never twice
    # the user pays this row through links now: it stays theirs, pending,
    # with its own date, and the processor never takes it up again
    flat_rows = [r for r in await saved(connection, user) if r[0] == "Flat"]
    assert [(r[1], r[4]) for r in flat_rows] == [("pending", date(2026, 11, 28))]
    november = await call(m28, token, "get_budget_forecast")
    assert november["commitments_reserved"] == "505.00"  # the rent is paid
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 12, 28))
    assert summary["processed"] == 0 and pushed == []
    assert await ledger(connection, user) == (1, D("850.00"))


async def test_a_row_of_unknown_origin_is_never_processed(
    mcp, seed, connection, monkeypatch
):
    """A row with no recorded source — saved before 0045 and not proven to be
    ChatGPT's (its idempotency record gone), or written by a writer that does
    not say — is never turned into an expense or pushed, and its due dates
    follow the rule from before 0045 (the month before its next date counts)."""
    user, token = await reference_profile(mcp, seed)
    await seed.scheduled(
        user,
        category="insurance",
        amount=D("33.00"),
        scheduled_date=date(2026, 12, 3),
        recurrence="monthly",
        merchant="Old row",
    )
    rows = [r for r in await saved(connection, user) if r[0] == "Old row"]
    assert [(r[1], r[2]) for r in rows] == [("pending", UNKNOWN_ORIGIN)]
    for day in (date(2026, 11, 30), date(2026, 12, 3)):
        summary, pushed = await run_scheduler(connection, monkeypatch, day)
        assert summary["processed"] == 0 and pushed == [], day
    assert await ledger(connection, user) == (0, D("0.00"))
    assert [r[1] for r in await saved(connection, user) if r[0] == "Old row"] == [
        "pending"
    ]
    # still a bill of November (3 November), as before 0045
    seen = await see(mcp.at(noon(25)), token)
    assert seen.summary["commitments_reserved"] == "538.00"  # 505 + 33


async def test_a_weekly_app_row_fired_mid_month_never_returns_to_its_date(
    mcp, seed, connection, monkeypatch
):
    """Weekly, made in the app, Wednesday 4 November: the processor records
    the 4th and schedules the 11th. November then holds the 11th, 18th and
    25th — never the 4th again."""
    user, token = await reference_profile(mcp, seed)
    await seed.scheduled(
        user,
        category="entertainment",
        amount=D("12.00"),
        scheduled_date=date(2026, 11, 4),
        recurrence="weekly",
        merchant="Climbing",
        origin=APP_ORIGIN,
    )
    summary, _ = await run_scheduler(connection, monkeypatch, date(2026, 11, 4))
    assert summary["processed"] == 1
    november = await due_in(connection, user, 2026, 11)
    assert [o.day for o in november if o.merchant == "Climbing"] == [
        date(2026, 11, d) for d in (11, 18, 25)
    ]
    seen = await see(mcp.at(noon(5)), token)
    assert seen.summary["total_spent"] == "12.00"
    assert seen.summary["commitments_reserved"] == "541.00"  # 505 + 3 × 12


async def test_a_retried_save_writes_one_obligation(mcp, seed, connection):
    """The same ChatGPT request retried (the same idempotency key) is one
    saved payment, not two that the month would hold twice."""
    m2 = mcp.at(noon(2))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m2.token(user)
    await call(
        m2,
        token,
        "update_financial_profile",
        {"monthly_net_income": 2500, "currency": "EUR", "timezone": "Europe/Sofia"},
    )
    request = {
        "name": "Car loan",
        "amount": 270,
        "category": "transportation",
        "recurrence": "monthly",
        "day_of_month": 15,
        "idempotency_key": key(),
    }
    first = await call(m2, token, "add_recurring_expense", request)
    second = await call(m2, token, "add_recurring_expense", request)
    assert (first["status"], second["status"]) == ("created", "already_created")
    assert len(await saved(connection, user)) == 1


# --- P2: the day of the month asked for ---------------------------------------------------


async def test_the_31st_saved_in_a_30_day_month_stays_the_31st(mcp, seed, connection):
    m10 = mcp.at(noon(10))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m10.token(user)
    await call(
        m10,
        token,
        "update_financial_profile",
        {"monthly_net_income": 2500, "currency": "EUR", "timezone": "Europe/Sofia"},
    )
    created = await call(
        m10,
        token,
        "add_recurring_expense",
        {
            "name": "Rent",
            "amount": 600,
            "category": "rent",
            "recurrence": "monthly",
            "day_of_month": 31,
            "idempotency_key": key(),
        },
    )
    assert created["next_due_date"] == "2026-11-30"
    assert any("no day 31" in n for n in created["notes"])
    rows = await saved(connection, user)
    assert [(r[2], r[3], r[4]) for r in rows] == [("chatgpt", 31, date(2026, 11, 30))]

    # the calendar's bill dates, month by month
    for (year, month), due in (
        ((2026, 11), "2026-11-30"),
        ((2026, 12), "2026-12-31"),
        ((2027, 1), "2027-01-31"),
        ((2027, 2), "2027-02-28"),
    ):
        seen = await see(m10, token, year, month)
        assert [b["date"] for b in seen.data["bills"]] == [due], (year, month)

    # in December the payment is due on the 31st, and a payment made on the
    # 31st is linked to it (the link validation uses the same rule)
    m_dec31 = mcp.at(datetime(2026, 12, 31, 10, 0, tzinfo=timezone.utc))
    recurring = await call(m_dec31, token, "get_recurring_expenses")
    rent = recurring["scheduled_recurring"][0]
    assert [d["due_date"] for d in rent["due_this_month"]] == ["2026-12-31"]
    paid = await call(
        m_dec31,
        token,
        "add_transaction",
        {
            "amount": "600.00",
            "category": "rent",
            "obligation_ref": rent["obligation_ref"],
            "date": "2026-12-31",
            "idempotency_key": key(),
        },
    )
    assert paid["status"] == "recorded"
    december = await see(m_dec31, token, 2026, 12)
    assert [(b["date"], b["state"]) for b in december.data["bills"]] == [
        ("2026-12-31", "paid")
    ]


def _monthly(anchor: date, day: Optional[int], year: int, month: int) -> List[date]:
    return due_dates_in_month(anchor, "monthly", year, month, day)


def test_the_requested_day_through_every_month_length_and_leap_year():
    nov30 = date(2026, 11, 30)  # "the 31st", saved on 10 November
    assert [
        _monthly(nov30, 31, y, m)[0]
        for y, m in (
            (2026, 11),
            (2026, 12),
            (2027, 1),
            (2027, 2),
            (2027, 3),
            (2027, 4),
            (2028, 2),
        )
    ] == [
        date(2026, 11, 30),
        date(2026, 12, 31),
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
        date(2027, 4, 30),
        date(2028, 2, 29),  # leap year
    ]
    # "the 30th" saved in January: February clamps, March is the 30th again
    jan30 = date(2027, 1, 30)
    assert [_monthly(jan30, 30, 2027, m)[0] for m in (1, 2, 3)] == [
        date(2027, 1, 30),
        date(2027, 2, 28),
        date(2027, 3, 30),
    ]
    # "the 29th" saved in a February without one: the 28th, then the 29th
    feb28 = date(2027, 2, 28)
    assert _monthly(feb28, 29, 2027, 2) == [date(2027, 2, 28)]
    assert _monthly(feb28, 29, 2027, 3) == [date(2027, 3, 29)]
    assert _monthly(feb28, 29, 2028, 2) == [date(2028, 2, 29)]
    # a row that never kept its day: exactly as before, never a guessed 31st
    assert _monthly(nov30, None, 2026, 12) == [date(2026, 12, 30)]
    # not running yet, and weekly / one-time payments ignore the day
    assert _monthly(date(2027, 3, 31), 31, 2027, 1) == []
    assert due_dates_in_month(date(2026, 11, 30), "once", 2026, 12, 31) == []
    weekly = due_dates_in_month(date(2026, 11, 4), "weekly", 2026, 11, 31)
    assert weekly == [date(2026, 11, d) for d in (4, 11, 18, 25)]


def test_a_row_made_in_the_app_never_counts_before_its_own_date():
    """A row scheduled in the mobile app is ONE occurrence (the processor
    records it and schedules the next row), so it counts from its own date
    on; a payment saved in ChatGPT is the obligation itself and still counts
    in the month before its next date (2.5.0's rule: a bill saved after this
    month's date passed is this month's too)."""
    nov28 = date(2026, 11, 28)
    app = [
        due_dates_in_month(nov28, "monthly", 2026, m, None, APP_ORIGIN)
        for m in (10, 11, 12)
    ]
    assert app == [[], [date(2026, 11, 28)], [date(2026, 12, 28)]]
    chatgpt = due_dates_in_month(nov28, "monthly", 2026, 10, None, CHATGPT_ORIGIN)
    assert chatgpt == [date(2026, 10, 28)]
    assert due_dates_in_month(nov28, "monthly", 2026, 10) == [date(2026, 10, 28)]
    # weekly, scheduled for Wednesday 11 November: not the 4th, every later one
    nov11 = date(2026, 11, 11)
    assert due_dates_in_month(nov11, "weekly", 2026, 11, None, APP_ORIGIN) == [
        date(2026, 11, d) for d in (11, 18, 25)
    ]
    assert due_dates_in_month(nov11, "weekly", 2026, 11, None, CHATGPT_ORIGIN) == [
        date(2026, 11, d) for d in (4, 11, 18, 25)
    ]
    # the requested day still applies to an app row's later months
    assert due_dates_in_month(
        date(2026, 11, 30), "monthly", 2026, 12, 31, APP_ORIGIN
    ) == [date(2026, 12, 31)]


def test_the_requested_day_is_what_the_user_gave():
    assert requested_day_of_month("monthly", day_of_month=31, first_date=None) == 31
    # "the 31st", with its first date given as 30 November: still the 31st
    assert (
        requested_day_of_month(
            "monthly", day_of_month=31, first_date=date(2026, 11, 30)
        )
        == 31
    )
    assert (
        requested_day_of_month(
            "monthly", day_of_month=None, first_date=date(2027, 1, 31)
        )
        == 31
    )
    assert requested_day_of_month("weekly", day_of_month=None, first_date=None) is None
    assert requested_day_of_month("once", day_of_month=None, first_date=None) is None


# --- independent review of the Gate 1 commit: every finding, pinned ---------


async def _app_row(seed, user, **values):
    row = dict(
        category="rent",
        amount=D("850.00"),
        scheduled_date=date(2026, 11, 28),
        recurrence="monthly",
        merchant="Flat",
        origin=APP_ORIGIN,
    )
    row.update(values)
    return await seed.scheduled(user, **row)


async def _ref(m, token, merchant):
    recurring = await call(m, token, "get_recurring_expenses")
    return next(
        i for i in recurring["scheduled_recurring"] if i["merchant"] == merchant
    )


async def _pay(m, token, ref, amount, day, category="rent"):
    return await call(
        m,
        token,
        "add_transaction",
        {
            "amount": amount,
            "category": category,
            "obligation_ref": ref,
            "date": day,
            "idempotency_key": key(),
        },
    )


async def test_payments_linked_ahead_are_never_recorded_again(
    mcp, seed, connection, monkeypatch
):
    """Finding 5. November's and December's rent paid on 27 November in
    ChatGPT (MITA links the second to 28 December). Neither date is ever
    recorded by the processor: 2 rents paid, 2 recorded."""
    user, token = await reference_profile(mcp, seed)
    await _app_row(seed, user)
    m27 = mcp.at(noon(27))
    flat = await _ref(m27, token, "Flat")
    dues = [
        (await _pay(m27, token, flat["obligation_ref"], "850.00", "2026-11-27"))[
            "transactions"
        ][0]["paid_obligation"]["due_date"]
        for _ in range(2)
    ]
    assert dues == ["2026-11-28", "2026-12-28"]
    for day in (date(2026, 11, 28), date(2026, 12, 28)):
        summary, pushed = await run_scheduler(connection, monkeypatch, day)
        assert summary["processed"] == 0 and pushed == [], day
    assert await ledger(connection, user) == (2, D("1700.00"))
    december = await call(
        mcp.at(datetime(2026, 12, 29, 10, 0, tzinfo=timezone.utc)),
        token,
        "get_recurring_expenses",
    )
    flat = next(i for i in december["scheduled_recurring"] if i["merchant"] == "Flat")
    assert flat["due_this_month"] == [
        {
            "due_date": "2026-12-28",
            "amount": "850.00",
            "paid": "850.00",
            "outstanding": "0.00",
        }
    ]


async def test_weekly_payments_linked_ahead_are_never_recorded_again(
    mcp, seed, connection, monkeypatch
):
    """Finding 5, weekly: two sessions paid on 3 November (linked to the 4th
    and the 11th); the processor records neither."""
    user, token = await reference_profile(mcp, seed)
    await _app_row(
        seed,
        user,
        category="entertainment",
        amount=D("12.00"),
        scheduled_date=date(2026, 11, 4),
        recurrence="weekly",
        merchant="Climbing",
    )
    m3 = mcp.at(noon(3))
    climb = await _ref(m3, token, "Climbing")
    for _ in range(2):
        await _pay(
            m3, token, climb["obligation_ref"], "12.00", "2026-11-03", "entertainment"
        )
    for day in (date(2026, 11, 4), date(2026, 11, 11)):
        summary, _ = await run_scheduler(connection, monkeypatch, day)
        assert summary["processed"] == 0, day
    assert await ledger(connection, user) == (2, D("24.00"))


async def test_a_deleted_linked_payment_leaves_the_bill_unpaid_and_held(
    mcp, seed, connection, monkeypatch
):
    """Findings 3 and its variant. The linked payment is deleted before or
    after the run: the bill is unpaid again, still held, never lost, and the
    processor records nothing on the user's behalf."""
    user, token = await reference_profile(mcp, seed)
    await _app_row(seed, user)
    m20 = mcp.at(noon(20))
    flat = await _ref(m20, token, "Flat")
    first = await _pay(m20, token, flat["obligation_ref"], "850.00", "2026-11-20")
    await call(
        m20, token, "delete_transaction", {"ref": first["transactions"][0]["ref"]}
    )
    held = await call(mcp.at(noon(27)), token, "get_budget_forecast")
    assert held["commitments_reserved"] == "1355.00"  # 505 + the unpaid 850
    summary, _ = await run_scheduler(connection, monkeypatch, date(2026, 11, 28))
    assert summary["processed"] == 0
    assert await ledger(connection, user) == (0, D("0.00"))
    after = await call(mcp.at(noon(28)), token, "get_budget_forecast")
    assert after["commitments_reserved"] == "1355.00"  # still held, not lost
    # paid and linked on the due date, deleted after the run: unpaid again
    second = await _pay(
        mcp.at(noon(28)), token, flat["obligation_ref"], "850.00", "2026-11-28"
    )
    paid = await call(mcp.at(noon(28)), token, "get_budget_forecast")
    assert paid["commitments_reserved"] == "505.00"
    await call(
        mcp.at(noon(28)),
        token,
        "delete_transaction",
        {"ref": second["transactions"][0]["ref"]},
    )
    again = await call(mcp.at(noon(28)), token, "get_budget_forecast")
    assert again["commitments_reserved"] == "1355.00"


async def test_a_partial_linked_payment_keeps_the_rest_held(
    mcp, seed, connection, monkeypatch
):
    """Finding 4. 400.00 of 850.00 paid: the 450.00 still owed stays held
    before and after the run, and nothing is recorded for it."""
    user, token = await reference_profile(mcp, seed)
    await _app_row(seed, user)
    m20 = mcp.at(noon(20))
    flat = await _ref(m20, token, "Flat")
    await _pay(m20, token, flat["obligation_ref"], "400.00", "2026-11-20")
    before = await call(mcp.at(noon(27)), token, "get_budget_forecast")
    assert before["commitments_reserved"] == "955.00"  # 505 + 450
    summary, _ = await run_scheduler(connection, monkeypatch, date(2026, 11, 28))
    assert summary["processed"] == 0 and summary["paid_through_links"] == 1
    assert await ledger(connection, user) == (1, D("400.00"))
    after = await call(mcp.at(noon(28)), token, "get_budget_forecast")
    assert after["commitments_reserved"] == "955.00"


async def test_no_reminder_for_a_bill_paid_through_links(
    mcp, seed, connection, monkeypatch
):
    """Finding 8: rent paid and linked on the 20th; no "due in 3 days" push
    on the 25th (it could prompt a second real payment)."""
    user, token = await reference_profile(mcp, seed)
    await _app_row(seed, user)
    m20 = mcp.at(noon(20))
    flat = await _ref(m20, token, "Flat")
    await _pay(m20, token, flat["obligation_ref"], "850.00", "2026-11-20")
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 25))
    assert pushed == [] and summary["reminders_sent"] == 0


async def test_a_row_another_run_already_handled_is_never_recorded_again(
    seed, connection, monkeypatch
):
    """Finding 6: two runs. The second still holds the row it selected before
    the first committed; under the ledger lock it re-reads the row, sees it
    processed, and records nothing."""
    from app.services.core.engine import expense_tracker

    user = await seed.user(income="2500")
    row = await _app_row(
        seed, user, category="utilities", amount=D("60.00"), merchant="Water"
    )
    real_lock = expense_tracker.lock_user_ledger

    def lock_after_the_other_run(db, user_id):
        # the other run commits first: the row is processed by the time this
        # run gets the lock
        db.execute(
            text("UPDATE scheduled_expenses SET status = 'processed' WHERE id = :id"),
            {"id": row.id},
        )
        db.commit()
        real_lock(db, user_id)

    monkeypatch.setattr(expense_tracker, "lock_user_ledger", lock_after_the_other_run)
    summary, pushed = await run_scheduler(connection, monkeypatch, date(2026, 11, 28))
    assert summary["processed"] == 0 and pushed == []
    assert await ledger(connection, user) == (0, D("0.00"))
    assert [r[1] for r in await saved(connection, user)] == ["processed"]


async def test_an_app_row_keeps_its_requested_day_as_it_rolls_forward(
    seed, connection, monkeypatch
):
    """Finding 7: an app row made for 31 January is recorded on 31 January,
    28 February and 31 March 2027, never drifting to the 28th."""
    user = await seed.user(income="2500")
    await _app_row(
        seed,
        user,
        category="utilities",
        amount=D("60.00"),
        scheduled_date=date(2027, 1, 31),
        merchant="Water",
    )
    for day in (date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)):
        summary, _ = await run_scheduler(connection, monkeypatch, day)
        assert summary["processed"] == 1, day
    rows = await saved(connection, user)
    assert [(r[1], r[3], r[4]) for r in rows] == [
        ("processed", None, date(2027, 1, 31)),
        ("processed", 31, date(2027, 2, 28)),
        ("processed", 31, date(2027, 3, 31)),
        ("pending", 31, date(2027, 4, 30)),
    ]
    assert await ledger(connection, user) == (3, D("180.00"))


async def test_a_reused_key_asking_for_another_day_is_refused(mcp, seed, connection):
    """Finding 9: "the 31st" and "the 30th" share November's date; the same
    idempotency key reused for the other day is refused, never replayed."""
    m10 = mcp.at(noon(10))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m10.token(user)
    await call(
        m10,
        token,
        "update_financial_profile",
        {"monthly_net_income": 2500, "currency": "EUR", "timezone": "Europe/Sofia"},
    )
    request = {
        "name": "Rent",
        "amount": 600,
        "category": "rent",
        "recurrence": "monthly",
        "day_of_month": 31,
        "idempotency_key": key(),
    }
    first = await call(m10, token, "add_recurring_expense", request)
    assert first["status"] == "created"
    refused = await m10.call(
        token, "add_recurring_expense", {**request, "day_of_month": 30}
    )
    assert refused.is_error and "different" in refused.content[0].text.lower()
    rows = await saved(connection, user)
    assert [(r[3], r[4]) for r in rows] == [(31, date(2026, 11, 30))]


async def test_the_service_is_not_ready_without_the_0045_columns(connection):
    """A deployment that reaches a database without migration 0045 never
    becomes healthy (``__main__.database_ready``): the columns it writes are
    required like its tables."""
    assert set(REQUIRED_COLUMNS) == {
        ("scheduled_expenses", "origin"),
        ("scheduled_expenses", "day_of_month"),
    }
    found = await connection.execute(
        text(
            "SELECT count(*) FROM information_schema.columns WHERE table_name = "
            "'scheduled_expenses' AND column_name IN ('origin', 'day_of_month')"
        )
    )
    assert found.scalar_one() == 2


def test_no_other_writer_creates_transactions_from_saved_payments():
    """The processor is the only path that turns a scheduled expense into a
    transaction, and it filters on origin = "app" in both its phases."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cron = (
        root / "app/services/core/engine/cron_task_scheduled_expenses.py"
    ).read_text()
    assert cron.count("ScheduledExpense.origin == APP_ORIGIN") == 2
    assert "from app.services.monthly_obligations import APP_ORIGIN" in cron
    assert "origin=expense.origin" in cron  # the next row keeps it
    assert (APP_ORIGIN, CHATGPT_ORIGIN, UNKNOWN_ORIGIN) == ("app", "chatgpt", "unknown")
    recurring_tool = (root / "app/mcp/tools/recurring.py").read_text()
    assert "origin=CHATGPT_ORIGIN" in recurring_tool
    # "app" — the only processable origin — is written by exactly one place:
    # the app's own create route. Every other writer states another origin
    # or gets the safe default ("unknown").
    writers = [
        path.relative_to(root).as_posix()
        for path in (root / "app").rglob("*.py")
        if "origin=APP_ORIGIN" in path.read_text()
    ]
    assert writers == ["app/api/scheduled_expenses/routes.py"]
    model = (root / "app/db/models/scheduled_expense.py").read_text()
    assert 'default="unknown", server_default="unknown"' in model
    service = (root / "app/services/scheduled_expense_service.py").read_text()
    assert "origin: str = UNKNOWN_ORIGIN" in service
