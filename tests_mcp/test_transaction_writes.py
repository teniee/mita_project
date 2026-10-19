"""Recording, correcting and deleting expenses through the MCP write tools.

Real tools over the SDK client, real PostgreSQL, the canonical ledger writers
underneath. Every assertion is on exact stored values, not status codes.
"""

import base64
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.mcp.analytics import EVENT_PROPERTIES
from app.mcp.idempotency import KEY_REUSED_MESSAGE
from app.mcp.tools.inputs import EXPENSE_CATEGORIES
from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)  # 12:00 in Sofia


def new_key() -> str:
    return uuid.uuid4().hex


async def add(m, token, **args):
    args.setdefault("idempotency_key", new_key())
    return await m.call(token, "add_transaction", args)


async def add_many(m, token, expenses, **args):
    args.setdefault("idempotency_key", new_key())
    return await m.call(token, "add_transactions", {"expenses": expenses, **args})


async def stored(connection, user, *, include_deleted=False):
    query = (
        "SELECT id, user_id, amount, category, merchant, currency, spent_at, deleted_at "
        "FROM transactions WHERE user_id = :u"
    )
    if not include_deleted:
        query += " AND deleted_at IS NULL"
    result = await connection.execute(
        text(query + " ORDER BY spent_at, id"), {"u": user.id}
    )
    return result.mappings().all()


async def plan_spent(connection, user, day: date, category: str):
    return (
        await connection.execute(
            text(
                "SELECT spent_amount FROM daily_plan WHERE user_id = :u AND category = :c "
                "AND date = :d"
            ),
            {
                "u": user.id,
                "c": category,
                "d": datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
            },
        )
    ).scalar_one()


async def idempotency_rows(connection, user):
    return (
        await connection.execute(
            text("SELECT count(*) FROM mcp_idempotency_keys WHERE user_id = :u"),
            {"u": user.id},
        )
    ).scalar_one()


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


@pytest.fixture
async def sofia(seed):
    return await seed.user(tz="Europe/Sofia", currency="EUR", name="Ana")


@pytest.fixture
async def bob(seed):
    return await seed.user(tz="UTC", currency="USD", name="Bob-the-other-user")


# --- add_transaction ---------------------------------------------------------


async def test_add_records_exact_amount_merchant_category_and_local_today(
    m, sofia, connection
):
    token = m.token(sofia)
    result = structured(
        await add(m, token, amount="36.80", category="groceries", merchant="Lidl")
    )
    assert result["status"] == "recorded" and result["count"] == 1
    assert result["currency"] == "EUR" and result["total"] == "36.80"
    item = result["transactions"][0]
    assert (item["date"], item["amount"], item["category"], item["merchant"]) == (
        "2026-10-11",
        "36.80",
        "groceries",
        "Lidl",
    )
    assert item["ref"].startswith("tx_")
    assert result["month_to_date_spent"] == "36.80"

    (row,) = await stored(connection, sofia)
    assert row["amount"] == Decimal("36.80") and row["currency"] == "EUR"
    assert row["merchant"] == "Lidl" and row["category"] == "groceries"
    assert row["spent_at"] == NOW  # "today" is the moment of recording

    listed = structured(await m.call(token, "list_transactions", {}))
    assert [t["ref"] for t in listed["transactions"]] == [item["ref"]]


@pytest.mark.parametrize(
    "merchant,expected",
    [
        ("Кафе „Мечта“", "Кафе „Мечта“"),
        ("Ünïcødé ☕ Café  No.5", "Ünïcødé ☕ Café  No.5"),
        ("  Lidl Varna  ", "Lidl Varna"),  # only surrounding whitespace is trimmed
        ("x" * 200, "x" * 200),
    ],
)
async def test_merchant_text_is_preserved_exactly(
    m, sofia, connection, merchant, expected
):
    result = structured(
        await add(m, m.token(sofia), amount=5, category="dining", merchant=merchant)
    )
    assert result["transactions"][0]["merchant"] == expected
    (row,) = await stored(connection, sofia)
    assert row["merchant"] == expected


async def test_past_date_is_stored_on_that_local_day(m, sofia, connection):
    result = structured(
        await add(m, m.token(sofia), amount="12.50", category="gas", date="2026-10-01")
    )
    assert result["transactions"][0]["date"] == "2026-10-01"
    (row,) = await stored(connection, sofia)
    # Local noon in Sofia (EEST, UTC+3) on that day.
    assert row["spent_at"] == datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "args,message",
    [
        ({"date": "2026-10-12"}, "cannot be dated in the future"),
        ({"date": "2019-01-01"}, "more than 7 years"),
        ({"merchant": "Lidl\x00"}, "control characters"),
    ],
)
async def test_invalid_dates_and_merchants_are_refused(
    m, sofia, connection, args, message
):
    result = await add(m, m.token(sofia), amount=10, category="groceries", **args)
    assert result.is_error and message in result.content[0].text
    assert await stored(connection, sofia) == []
    assert await idempotency_rows(connection, sofia) == 0


@pytest.mark.parametrize(
    "amount",
    [
        "0",
        "0.00",
        "-1",
        "12.345",
        "NaN",
        "Infinity",
        "1000000.00",
        True,
        "abc",
        "1,50",
        None,
    ],
)
async def test_invalid_amounts_are_refused_by_the_schema(m, sofia, connection, amount):
    result = await add(m, m.token(sofia), amount=amount, category="groceries")
    assert result.is_error
    assert await stored(connection, sofia) == []


@pytest.mark.parametrize(
    "category", ["income", "Groceries", "food & drinks", "", "misc"]
)
async def test_invalid_categories_are_refused(m, sofia, connection, category):
    result = await add(m, m.token(sofia), amount=10, category=category)
    assert result.is_error
    assert await stored(connection, sofia) == []


def test_expense_categories_are_the_api_list_without_income():
    from app.core.financial_constants import FinancialConstants

    assert set(
        EXPENSE_CATEGORIES
    ) == FinancialConstants.VALID_TRANSACTION_CATEGORIES - {"income"}
    assert "other" in EXPENSE_CATEGORIES  # a real category the user may choose


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "add_transaction",
            {"amount": 1, "category": "dining", "idempotency_key": "k" * 16},
        ),
        (
            "add_transactions",
            {
                "expenses": [{"amount": 1, "category": "dining"}],
                "idempotency_key": "k" * 16,
            },
        ),
        ("update_transaction", {"ref": "tx_x", "amount": 1}),
        ("delete_transaction", {"ref": "tx_x"}),
    ],
)
@pytest.mark.parametrize("field", ["user_id", "owner", "email", "account_id"])
async def test_write_tools_reject_identity_arguments(
    m, sofia, bob, connection, tool, args, field
):
    value = bob.email if field == "email" else str(bob.id)
    result = await m.call(m.token(sofia), tool, {**args, field: value})
    assert result.is_error
    assert "Extra inputs are not permitted" in result.content[0].text
    assert await stored(connection, sofia) == [] and await stored(connection, bob) == []


async def test_items_reject_undeclared_fields_too(m, sofia, connection):
    result = await add_many(
        m, m.token(sofia), [{"amount": 1, "category": "dining", "user_id": "x"}]
    )
    assert result.is_error and await stored(connection, sofia) == []


async def test_recording_needs_a_known_currency(m, seed, connection):
    newcomer = await seed.user(income="0", onboarded=False)
    result = await add(m, m.token(newcomer), amount=10, category="groceries")
    assert result.is_error and "update_financial_profile" in result.content[0].text
    assert await stored(connection, newcomer) == []


async def test_writes_need_the_finance_write_scope(m, sofia, connection):
    token = m.token(sofia, scopes=["profile:read", "finance:read"])
    result = await add(m, token, amount=10, category="groceries")
    assert result.structured_content["error"]["category"] == "forbidden"
    assert "finance:write" in result.meta["mcp/www_authenticate"][0]
    assert await stored(connection, sofia) == []


# --- add_transactions --------------------------------------------------------


async def test_batch_is_recorded_atomically_with_exact_total(m, sofia, bob, connection):
    expenses = [
        {"amount": 8, "category": "dining", "merchant": "Coffee bar"},
        {"amount": "55.00", "category": "gas"},
        {
            "amount": "74.35",
            "category": "groceries",
            "merchant": "Lidl",
            "date": "2026-10-10",
        },
    ]
    result = structured(await add_many(m, m.token(sofia), expenses))
    assert result["status"] == "recorded" and result["count"] == 3
    assert result["total"] == "137.35"
    assert [t["amount"] for t in result["transactions"]] == ["8.00", "55.00", "74.35"]
    assert len({t["ref"] for t in result["transactions"]}) == 3
    rows = await stored(connection, sofia)
    assert sorted(r["amount"] for r in rows) == [
        Decimal("8.00"),
        Decimal("55.00"),
        Decimal("74.35"),
    ]
    assert {r["user_id"] for r in rows} == {sofia.id}
    assert await stored(connection, bob) == []


async def test_one_invalid_item_records_nothing_and_names_the_item(
    m, sofia, connection
):
    expenses = [
        {"amount": 8, "category": "dining", "merchant": "Secret Cafe"},
        {"amount": 9, "category": "dining", "date": "2026-12-31"},
    ]
    result = await add_many(m, m.token(sofia), expenses)
    assert result.is_error
    message = result.content[0].text
    assert message.startswith("Item 2:") and "Nothing was recorded" in message
    assert "Secret Cafe" not in message and "8" not in message
    assert await stored(connection, sofia) == []
    assert await idempotency_rows(connection, sofia) == 0


async def test_a_failure_inside_the_ledger_rolls_the_whole_batch_back(
    m, sofia, connection, monkeypatch
):
    from app.mcp.writes import transactions as writes_module

    real = writes_module.add_transactions_to_ledger

    def explode_after_first(db, rows):
        real(db, rows[:1])
        raise RuntimeError("simulated failure after the first row")

    monkeypatch.setattr(
        writes_module, "add_transactions_to_ledger", explode_after_first
    )
    result = await add_many(
        m,
        m.token(sofia),
        [{"amount": 1, "category": "dining"}, {"amount": 2, "category": "dining"}],
    )
    assert result.is_error
    assert result.structured_content["error"]["category"] == "internal"
    assert await stored(connection, sofia) == []
    assert await idempotency_rows(connection, sofia) == 0


async def test_batch_size_is_bounded(m, sofia, connection):
    item = {"amount": 1, "category": "dining"}
    assert (await add_many(m, m.token(sofia), [item] * 26)).is_error
    assert (await add_many(m, m.token(sofia), [])).is_error
    assert await stored(connection, sofia) == []
    ok = structured(await add_many(m, m.token(sofia), [item] * 25))
    assert ok["count"] == 25 and ok["total"] == "25.00"


# --- idempotency ---------------------------------------------------------------


async def test_retried_add_records_once_and_replays_the_original(m, sofia, connection):
    token = m.token(sofia)
    key = new_key()
    first = structured(
        await add(m, token, amount="3.50", category="dining", idempotency_key=key)
    )
    second = structured(
        await add(m, token, amount="3.50", category="dining", idempotency_key=key)
    )
    assert first["status"] == "recorded" and second["status"] == "already_recorded"
    assert second["transactions"] == first["transactions"]
    assert len(await stored(connection, sofia)) == 1


async def test_retried_batch_records_once(m, sofia, connection):
    token = m.token(sofia)
    key = new_key()
    expenses = [{"amount": 1, "category": "dining"}, {"amount": 2, "category": "gas"}]
    first = structured(await add_many(m, token, expenses, idempotency_key=key))
    second = structured(await add_many(m, token, expenses, idempotency_key=key))
    assert second["status"] == "already_recorded"
    assert [t["ref"] for t in second["transactions"]] == [
        t["ref"] for t in first["transactions"]
    ]
    assert len(await stored(connection, sofia)) == 2


async def test_same_key_with_different_data_is_refused(m, sofia, connection):
    token = m.token(sofia)
    key = new_key()
    await add(m, token, amount="3.50", category="dining", idempotency_key=key)
    other = await add(m, token, amount="4.50", category="dining", idempotency_key=key)
    assert other.is_error and KEY_REUSED_MESSAGE in other.content[0].text
    assert [r["amount"] for r in await stored(connection, sofia)] == [Decimal("3.50")]
    # A key belongs to one operation: the batch tool does not replay it either.
    batch = await add_many(
        m, token, [{"amount": "3.50", "category": "dining"}], idempotency_key=key
    )
    assert not batch.is_error  # different operation scope → its own record
    assert len(await stored(connection, sofia)) == 2


async def test_same_key_from_two_users_is_two_records(m, sofia, bob, connection):
    key = new_key()
    a = structured(
        await add(m, m.token(sofia), amount=5, category="dining", idempotency_key=key)
    )
    b = structured(
        await add(m, m.token(bob), amount=5, category="dining", idempotency_key=key)
    )
    assert a["status"] == b["status"] == "recorded"
    assert (
        len(await stored(connection, sofia)) == 1
        and len(await stored(connection, bob)) == 1
    )
    assert a["transactions"][0]["ref"] != b["transactions"][0]["ref"]


async def test_two_identical_real_purchases_are_two_expenses(m, sofia, connection):
    token = m.token(sofia)
    for _ in range(2):
        await add(m, token, amount="3.50", category="dining", merchant="Costa")
    assert len(await stored(connection, sofia)) == 2  # never deduplicated by content


async def test_key_is_scoped_to_the_chatgpt_conversation(m, sofia, connection):
    token = m.token(sofia)
    args = {"amount": 2, "category": "dining", "idempotency_key": "same-key-123"}
    first = structured(
        await m.call(token, "add_transaction", args, meta={"openai/session": "conv-A"})
    )
    retry = structured(
        await m.call(token, "add_transaction", args, meta={"openai/session": "conv-A"})
    )
    elsewhere = structured(
        await m.call(token, "add_transaction", args, meta={"openai/session": "conv-B"})
    )
    assert (first["status"], retry["status"], elsewhere["status"]) == (
        "recorded",
        "already_recorded",
        "recorded",
    )
    assert len(await stored(connection, sofia)) == 2


async def test_idempotency_rows_hold_no_values(m, sofia, connection):
    await add(m, m.token(sofia), amount="77.77", category="dining", merchant="Zara")
    row = (
        (
            await connection.execute(
                text("SELECT * FROM mcp_idempotency_keys WHERE user_id = :u"),
                {"u": sofia.id},
            )
        )
        .mappings()
        .one()
    )
    flat = " ".join(str(v) for v in row.values())
    assert "77.77" not in flat and "Zara" not in flat and "dining" not in flat


# --- update_transaction --------------------------------------------------------


async def test_update_changes_only_sent_fields_and_rebuilds_the_plan(
    m, sofia, seed, connection
):
    await seed.plan(
        sofia, date(2026, 10, 11), {"groceries": "20.00", "dining": "15.00"}
    )
    token = m.token(sofia)
    recorded = structured(
        await add(m, token, amount="36.80", category="groceries", merchant="Lidl")
    )
    ref = recorded["transactions"][0]["ref"]
    assert await plan_spent(
        connection, sofia, date(2026, 10, 11), "groceries"
    ) == Decimal("36.80")

    changed = structured(
        await m.call(token, "update_transaction", {"ref": ref, "amount": "6.80"})
    )
    assert changed["status"] == "updated" and changed["changed_fields"] == ["amount"]
    assert changed["transaction"]["merchant"] == "Lidl"
    assert changed["transaction"]["category"] == "groceries"
    assert changed["transaction"]["date"] == "2026-10-11"
    assert changed["transaction"]["ref"] == ref
    assert changed["month_to_date_spent"] == "6.80"
    (row,) = await stored(connection, sofia)
    assert row["amount"] == Decimal("6.80") and row["spent_at"] == NOW
    assert await plan_spent(
        connection, sofia, date(2026, 10, 11), "groceries"
    ) == Decimal("6.80")

    moved = structured(
        await m.call(token, "update_transaction", {"ref": ref, "category": "dining"})
    )
    assert moved["changed_fields"] == ["category"]
    assert await plan_spent(connection, sofia, date(2026, 10, 11), "groceries") == 0
    assert await plan_spent(connection, sofia, date(2026, 10, 11), "dining") == Decimal(
        "6.80"
    )


async def test_moving_the_date_keeps_the_time_of_day(m, sofia, connection):
    token = m.token(sofia)
    ref = structured(await add(m, token, amount=10, category="groceries"))[
        "transactions"
    ][0]["ref"]
    moved = structured(
        await m.call(token, "update_transaction", {"ref": ref, "date": "2026-09-30"})
    )
    assert moved["changed_fields"] == ["date"]
    assert moved["transaction"]["date"] == "2026-09-30"
    (row,) = await stored(connection, sofia)
    # 12:00 Sofia on 11 Oct → 12:00 Sofia on 30 Sep (both EEST, UTC+3).
    assert row["spent_at"] == datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    assert (
        structured(await m.call(token, "get_financial_summary", {}))["spent_total"]
        == "0.00"
    )


async def test_merchant_can_be_removed_and_resending_is_unchanged(m, sofia, connection):
    token = m.token(sofia)
    ref = structured(await add(m, token, amount=10, category="dining", merchant="Old"))[
        "transactions"
    ][0]["ref"]
    cleared = structured(
        await m.call(token, "update_transaction", {"ref": ref, "merchant": ""})
    )
    assert cleared["changed_fields"] == ["merchant"]
    assert cleared["transaction"]["merchant"] is None
    same = structured(
        await m.call(token, "update_transaction", {"ref": ref, "amount": 10})
    )
    assert same["status"] == "unchanged" and same["changed_fields"] == []


async def test_update_needs_a_field(m, sofia):
    token = m.token(sofia)
    ref = structured(await add(m, token, amount=10, category="dining"))["transactions"][
        0
    ]["ref"]
    result = await m.call(token, "update_transaction", {"ref": ref})
    assert result.is_error and "at least one field" in result.content[0].text


async def test_foreign_reference_cannot_update_or_delete(m, sofia, bob, connection):
    bob_ref = structured(await add(m, m.token(bob), amount="99.99", category="rent"))[
        "transactions"
    ][0]["ref"]
    for tool, extra in (
        ("update_transaction", {"amount": 1}),
        ("delete_transaction", {}),
    ):
        result = await m.call(m.token(sofia), tool, {"ref": bob_ref, **extra})
        assert result.is_error and "No MITA expense matches" in result.content[0].text
        assert "99.99" not in result.content[0].text
    (row,) = await stored(connection, bob)
    assert row["amount"] == Decimal("99.99") and row["deleted_at"] is None


def _tamper(ref: str) -> str:
    raw = bytearray(base64.urlsafe_b64decode(ref[3:] + "=" * (-len(ref[3:]) % 4)))
    raw[-1] ^= 0x01
    return "tx_" + base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")


async def test_forged_and_tampered_references_fail(m, sofia, connection):
    token = m.token(sofia)
    ref = structured(await add(m, token, amount=10, category="dining"))["transactions"][
        0
    ]["ref"]
    (row,) = await stored(connection, sofia)
    for bogus in (
        _tamper(ref),
        "tx_" + "A" * 43,
        str(row["id"]),
        "tx_" + str(row["id"]),
    ):
        for tool, extra in (
            ("update_transaction", {"amount": 1}),
            ("delete_transaction", {}),
        ):
            result = await m.call(token, tool, {"ref": bogus, **extra})
            assert result.is_error, (bogus, tool)
    (after,) = await stored(connection, sofia)
    assert after["amount"] == Decimal("10.00") and after["deleted_at"] is None


async def test_a_deleted_expense_cannot_be_resurrected_by_update(m, sofia, connection):
    token = m.token(sofia)
    ref = structured(await add(m, token, amount=10, category="dining"))["transactions"][
        0
    ]["ref"]
    await m.call(token, "delete_transaction", {"ref": ref})
    result = await m.call(token, "update_transaction", {"ref": ref, "amount": 11})
    assert result.is_error and "was deleted" in result.content[0].text
    (row,) = await stored(connection, sofia, include_deleted=True)
    assert row["deleted_at"] is not None and row["amount"] == Decimal("10.00")


# --- delete_transaction --------------------------------------------------------


async def test_delete_is_soft_excluded_everywhere_and_repeatable(
    m, sofia, seed, connection
):
    await seed.plan(sofia, date(2026, 10, 11), {"dining": "15.00"})
    token = m.token(sofia)
    keep = structured(await add(m, token, amount="4.00", category="dining"))
    gone = structured(
        await add(m, token, amount="9.00", category="dining", merchant="Oops")
    )
    ref = gone["transactions"][0]["ref"]

    deleted = structured(await m.call(token, "delete_transaction", {"ref": ref}))
    assert deleted["status"] == "deleted"
    assert deleted["transaction"]["amount"] == "9.00"
    assert deleted["month_to_date_spent"] == "4.00"
    rows = await stored(connection, sofia, include_deleted=True)
    assert len(rows) == 2 and sum(r["deleted_at"] is not None for r in rows) == 1
    listed = structured(await m.call(token, "list_transactions", {}))
    assert [t["ref"] for t in listed["transactions"]] == [
        keep["transactions"][0]["ref"]
    ]
    summary = structured(await m.call(token, "get_financial_summary", {}))
    assert summary["spent_total"] == "4.00" and summary["transaction_count"] == 1
    assert await plan_spent(connection, sofia, date(2026, 10, 11), "dining") == Decimal(
        "4.00"
    )

    again = structured(await m.call(token, "delete_transaction", {"ref": ref}))
    assert again["status"] == "already_deleted"
    assert len(await stored(connection, sofia)) == 1


# --- timezones -----------------------------------------------------------------


async def test_sofia_local_midnight_decides_the_month(mcp, sofia, connection):
    late = mcp.at(
        datetime(2026, 10, 31, 22, 30, tzinfo=timezone.utc)
    )  # 00:30 1 Nov in Sofia
    result = structured(
        await add(late, late.token(sofia), amount=20, category="groceries")
    )
    assert result["transactions"][0]["date"] == "2026-11-01"
    november = structured(
        await late.call(late.token(sofia), "get_financial_summary", {})
    )
    assert (november["year"], november["month"], november["spent_total"]) == (
        2026,
        11,
        "20.00",
    )
    october = structured(
        await late.call(
            late.token(sofia), "get_financial_summary", {"year": 2026, "month": 10}
        )
    )
    assert october["spent_total"] == "0.00"


async def test_utc_user_late_evening_stays_on_the_same_day(mcp, bob):
    late = mcp.at(datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc))
    result = structured(
        await add(late, late.token(bob), amount=20, category="groceries")
    )
    assert result["transactions"][0]["date"] == "2026-10-31"


@pytest.mark.parametrize(
    "day,utc_hour",
    [
        ("2026-03-29", 9),  # spring forward in Sofia: noon is EEST (UTC+3)
        ("2025-10-26", 10),  # fall back (last Sunday of Oct 2025): EET, UTC+2
        ("2026-03-28", 10),  # the day before spring forward: still EET
    ],
)
async def test_dst_days_store_local_noon(m, sofia, connection, day, utc_hour):
    result = structured(
        await add(m, m.token(sofia), amount=1, category="dining", date=day)
    )
    assert result["transactions"][0]["date"] == day
    (row,) = await stored(connection, sofia)
    y, mo, d = map(int, day.split("-"))
    assert row["spent_at"] == datetime(y, mo, d, utc_hour, 0, tzinfo=timezone.utc)


# --- pagination ----------------------------------------------------------------


async def test_paging_returns_every_row_once_in_a_stable_order(
    m, sofia, seed, connection
):
    same_moment = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
    for i in range(4):  # ties on spent_at are broken by id
        await seed.txn(sofia, f"{i + 1}.00", "dining", same_moment, merchant=f"Tie {i}")
    for day in (1, 2, 3):
        await seed.txn(
            sofia, "10.00", "gas", datetime(2026, 10, day, 8, tzinfo=timezone.utc)
        )
    await seed.txn(sofia, "999.00", "gas", same_moment, deleted=True)
    token = m.token(sofia)
    window = {"start_date": "2026-10-01", "end_date": "2026-10-11", "limit": 3}

    pages, cursor = [], None
    while True:
        args = dict(window, **({"cursor": cursor} if cursor else {}))
        page = structured(await m.call(token, "list_transactions", args))
        pages.append(page)
        cursor = page["next_cursor"]
        assert (cursor is not None) == page["has_more"]
        assert page["matching_count"] == 7 and page["matching_total"] == "40.00"
        if not page["has_more"]:
            break
    assert [p["returned_count"] for p in pages] == [3, 3, 1]
    refs = [t["ref"] for p in pages for t in p["transactions"]]
    assert len(refs) == len(set(refs)) == 7
    amounts = [t["amount"] for p in pages for t in p["transactions"]]
    assert "999.00" not in amounts
    one_shot = structured(
        await m.call(token, "list_transactions", dict(window, limit=200))
    )
    assert [t["ref"] for t in one_shot["transactions"]] == refs  # same order


async def test_cursor_is_bound_to_the_user_and_the_query(m, sofia, bob, seed):
    for day in (1, 2, 3):
        await seed.txn(
            sofia, "1.00", "gas", datetime(2026, 10, day, 8, tzinfo=timezone.utc)
        )
    window = {"start_date": "2026-10-01", "end_date": "2026-10-11", "limit": 1}
    first = structured(await m.call(m.token(sofia), "list_transactions", window))
    cursor = first["next_cursor"]
    assert cursor
    attempts = [
        (m.token(bob), dict(window, cursor=cursor)),
        (m.token(sofia), dict(window, cursor=cursor, category="gas")),
        (m.token(sofia), dict(window, cursor=cursor, start_date="2026-10-02")),
        (
            m.token(sofia),
            dict(window, cursor=cursor[:-2] + ("AA" if cursor[-2:] != "AA" else "BB")),
        ),
    ]
    for token, args in attempts:
        result = await m.call(token, "list_transactions", args)
        assert result.is_error and "cursor" in result.content[0].text, args


# --- analytics -----------------------------------------------------------------


async def test_write_events_carry_no_values_and_no_raw_ids(
    m, sofia, seed, analytics_sink
):
    await seed.profile(sofia, usage_analytics_enabled=True)
    token = m.token(sofia)
    await m.call(
        token,
        "add_transaction",
        {
            "amount": "36.80",
            "category": "groceries",
            "merchant": "Lidl Varna",
            "idempotency_key": new_key(),
            "entry_method": "receipt_image",
        },
        meta={"openai/session": "raw-conversation-id-123", "openai/locale": "bg-BG"},
    )
    names = analytics_sink.names()
    assert names == [
        "tool_call_succeeded",
        "transaction_created",
        "receipt_flow_completed",
    ]
    for event in analytics_sink.events:
        stored_row = repr(event.row())  # exactly what reaches analytics.events
        assert "user_id" not in event.row()
        for secret in (
            "36.80",
            "Lidl",
            "raw-conversation-id-123",
            str(sofia.id),
            sofia.email,
        ):
            assert secret not in stored_row, (event.event_name, secret)
        assert set(event.properties) <= EVENT_PROPERTIES[event.event_name]
        assert event.user_key and len(event.user_key) == 32
        assert event.session_key and len(event.session_key) == 32
        assert event.locale == "bg-BG" and event.tool_name == "add_transaction"
    created = next(
        e for e in analytics_sink.events if e.event_name == "transaction_created"
    )
    assert created.properties == {"entry_method": "receipt_image"}


async def test_without_consent_events_are_unlinked(m, sofia, analytics_sink):
    await add(m, m.token(sofia), amount=1, category="dining")
    assert analytics_sink.events
    for event in analytics_sink.events:
        assert (
            event.user_key is None
            and event.session_key is None
            and event.user_id is None
        )


async def test_a_broken_analytics_sink_never_fails_a_write(
    m, sofia, connection, analytics_sink
):
    def broken(events):
        raise RuntimeError("analytics database is down")

    analytics_sink.record = broken
    result = await add(m, m.token(sofia), amount="12.00", category="dining")
    assert structured(result)["status"] == "recorded"
    assert [r["amount"] for r in await stored(connection, sofia)] == [Decimal("12.00")]


async def test_replay_is_marked_in_analytics(m, sofia, seed, analytics_sink):
    await seed.profile(sofia, usage_analytics_enabled=True)
    token = m.token(sofia)
    key = new_key()
    for _ in range(2):
        await add(m, token, amount=1, category="dining", idempotency_key=key)
    calls = [e for e in analytics_sink.events if e.event_name == "tool_call_succeeded"]
    assert [c.properties for c in calls] == [{}, {"replayed": True}]
    assert analytics_sink.names().count("transaction_created") == 1
