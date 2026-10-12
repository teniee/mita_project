"""preview_monthly_budget → reviewed draft → save_monthly_budget.

The central invariant: the plan the user reviewed is exactly the plan that is
saved — per category and per day, to the cent — and a preview writes nothing.
Everything is driven through the real tools, as a conversation would.
"""

import base64
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.mcp.writes.budget import CHANGED_DRAFT, EXPIRED_DRAFT, INVALID_DRAFT
from app.services.core.engine.realtime_rebalancer import REALTIME_ADJUSTMENT_KEY
from app.services.monthly_plan_service import allocations_from_profile, month_calendar
from tests_mcp.conftest import structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)  # 12:00 in Sofia


def new_key() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


@pytest.fixture
async def ana(m, seed):
    """A ChatGPT-created account after the user stated their profile and rent."""
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    token = m.token(user)
    structured(
        await m.call(
            token,
            "update_financial_profile",
            {
                "monthly_net_income": 2500,
                "currency": "EUR",
                "timezone": "Europe/Sofia",
                "household_size": 2,
                "monthly_savings_target": 400,
            },
        )
    )
    structured(
        await m.call(
            token,
            "add_recurring_expense",
            {
                "name": "Rent",
                "amount": 700,
                "category": "rent",
                "recurrence": "monthly",
                "day_of_month": 1,
                "idempotency_key": new_key(),
            },
        )
    )
    return user


async def plan_rows(connection, user, *, goal_rows=False):
    clause = "goal_id IS NOT NULL" if goal_rows else "goal_id IS NULL"
    result = await connection.execute(
        text(
            f"SELECT date, category, planned_amount, spent_amount, plan_json FROM daily_plan "  # nosec B608
            f"WHERE user_id = :u AND {clause} ORDER BY date, category"
        ),
        {"u": user.id},
    )
    return result.mappings().all()


def by_category(rows):
    totals = defaultdict(Decimal)
    for row in rows:
        totals[row["category"]] += Decimal(str(row["planned_amount"]))
    return dict(totals)


def preview_allocations(preview):
    expected = {
        o["category"]: Decimal(o["amount"]) for o in preview["fixed_obligations"]
    }
    for item in preview["category_allocations"]:
        expected[item["category"]] = expected.get(
            item["category"], Decimal("0")
        ) + Decimal(item["amount"])
    if Decimal(preview["savings_allocation"]) > 0:
        expected["savings goal based"] = Decimal(preview["savings_allocation"])
    return expected


async def test_preview_is_the_canonical_engine_and_writes_nothing(m, ana, connection):
    token = m.token(ana)
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    assert preview["status"] == "preview" and preview["month"] == "2026-10"
    assert preview["existing_plan"] is False and preview["currency"] == "EUR"
    assert preview["stated_monthly_income"] == "2500.00"
    assert preview["fixed_obligations"] == [
        {"name": "Rent", "category": "rent", "amount": "700.00", "basis": "monthly"}
    ]
    assert preview["fixed_obligations_total"] == "700.00"
    assert preview["savings_allocation"] == "400.00"

    engine = allocations_from_profile(
        monthly_income=Decimal("2500"),
        savings_goal=Decimal("400"),
        region="ZZ",
        fixed_expenses={"rent": Decimal("700")},
    )
    assert {
        c["category"]: Decimal(c["amount"]) for c in preview["category_allocations"]
    } == (engine.discretionary)
    assert Decimal(preview["unallocated"]) == engine.unallocated
    # The arithmetic closes to the cent.
    flexible = Decimal(preview["flexible_total"])
    assert Decimal("700.00") + Decimal("400.00") + flexible == Decimal("2500.00")
    categories_sum = sum(Decimal(c["amount"]) for c in preview["category_allocations"])
    assert categories_sum + Decimal(preview["unallocated"]) == flexible
    assert Decimal(preview["plan_total"]) == Decimal("1100.00") + categories_sum
    assert Decimal(preview["daily_flexible_average"]) == (flexible / 31).quantize(
        Decimal("0.01")
    )
    assert preview["days_in_month"] == 31 and preview["days_remaining"] == 21
    assert preview["recurring_included"] is True
    assert preview["draft_token"].startswith("bd1_")
    assert any("No region is stated" in a for a in preview["assumptions"])
    assert any("Household size (2)" in a for a in preview["assumptions"])
    sources = {s["input"]: s["source"] for s in preview["data_sources"]}
    assert sources["monthly_net_income"] == "stated by the user"
    assert "1 recurring" in sources["fixed_obligations"]

    assert await plan_rows(connection, ana) == []  # a preview writes nothing
    user = (
        await connection.execute(
            text("SELECT has_onboarded FROM users WHERE id = :u"), {"u": ana.id}
        )
    ).scalar_one()
    assert user is False


async def test_saved_plan_is_exactly_the_reviewed_plan(
    m, ana, connection, analytics_sink
):
    token = m.token(ana)
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    saved = structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
    )
    assert saved["status"] == "saved" and saved["month"] == "2026-10"
    assert saved["plan_total"] == preview["plan_total"]

    rows = await plan_rows(connection, ana)
    expected = preview_allocations(preview)
    assert by_category(rows) == expected
    assert sum(by_category(rows).values()) == Decimal(preview["plan_total"])
    # Day by day: the canonical layout of exactly those allocations.
    layout = month_calendar(2026, 10, expected)
    stored_days = {
        (row["date"].date().isoformat(), row["category"]): Decimal(
            str(row["planned_amount"])
        )
        for row in rows
    }
    assert stored_days == {
        (day, category): Decimal(str(amount))
        for day, categories in layout.items()
        for category, amount in categories.items()
    }
    assert stored_days[("2026-10-01", "rent")] == Decimal("700.00")  # rent on the 1st

    status = structured(await m.call(token, "get_budget_status", {}))
    assert status["plan_status"] == "generated"
    assert status["total_planned"] == preview["plan_total"]
    setup = structured(await m.call(token, "get_setup_status", {}))
    assert setup["monthly_plan_exists"] is True
    assert setup["suggested_next_step"] == "record_expenses"
    onboarded = (
        await connection.execute(
            text("SELECT has_onboarded FROM users WHERE id = :u"), {"u": ana.id}
        )
    ).scalar_one()
    assert onboarded is True
    names = analytics_sink.names()
    assert "budget_previewed" in names and "budget_saved" in names
    assert "onboarding_completed" in names


async def test_saving_the_same_draft_twice_changes_nothing(m, ana, connection):
    token = m.token(ana)
    draft = structured(await m.call(token, "preview_monthly_budget", {}))["draft_token"]
    first = structured(
        await m.call(token, "save_monthly_budget", {"draft_token": draft})
    )
    rows = await plan_rows(connection, ana)
    again = structured(
        await m.call(token, "save_monthly_budget", {"draft_token": draft})
    )
    assert (first["status"], again["status"]) == ("saved", "already_saved")
    assert await plan_rows(connection, ana) == rows


def _tamper(token: str) -> str:
    body = token[4:]
    raw = bytearray(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    raw[3] ^= 0x01  # inside the payload (the month)
    return "bd1_" + base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")


async def test_forged_foreign_and_expired_drafts_are_refused(
    m, mcp, ana, seed, connection
):
    token = m.token(ana)
    draft = structured(await m.call(token, "preview_monthly_budget", {}))["draft_token"]
    bob = await seed.user(tz="UTC", currency="USD", income="9000.00")
    for bogus, who in (
        (_tamper(draft), token),
        ("bd1_" + "A" * 54, token),
        ("not-a-draft-token", token),
        (draft, m.token(bob)),  # Ana's draft in Bob's hands
    ):
        result = await m.call(who, "save_monthly_budget", {"draft_token": bogus})
        assert result.is_error and INVALID_DRAFT in result.content[0].text
    later = mcp.at(NOW + timedelta(minutes=31))
    expired = await later.call(
        later.token(ana), "save_monthly_budget", {"draft_token": draft}
    )
    assert expired.is_error and EXPIRED_DRAFT in expired.content[0].text
    assert (
        await plan_rows(connection, ana) == []
        and await plan_rows(connection, bob) == []
    )


async def test_changed_inputs_invalidate_the_preview(m, ana, connection):
    token = m.token(ana)
    draft = structured(await m.call(token, "preview_monthly_budget", {}))["draft_token"]
    await m.call(token, "update_financial_profile", {"monthly_net_income": 2600})
    result = await m.call(token, "save_monthly_budget", {"draft_token": draft})
    assert result.is_error and CHANGED_DRAFT in result.content[0].text
    assert await plan_rows(connection, ana) == []


async def test_recording_an_expense_does_not_invalidate_the_preview(m, ana, connection):
    token = m.token(ana)
    draft = structured(await m.call(token, "preview_monthly_budget", {}))["draft_token"]
    await m.call(
        token,
        "add_transaction",
        {"amount": "36.80", "category": "groceries", "idempotency_key": new_key()},
    )
    saved = structured(
        await m.call(token, "save_monthly_budget", {"draft_token": draft})
    )
    assert saved["status"] == "saved"
    # The expense is accrued against the newly saved plan.
    status = structured(await m.call(token, "get_budget_status", {}))
    assert status["total_spent"] == "36.80"


async def test_replacing_a_plan_keeps_goal_reservations_and_reaccrues_spend(
    m, ana, seed, connection
):
    token = m.token(ana)
    old_goal = await seed.goal(ana, title="Old goal", target_date=date(2027, 6, 30))
    await seed.plan(ana, date(2026, 10, 1), {"legacy category": "999.00"})
    await seed.plan(ana, date(2026, 10, 2), {"goal_savings": "5.00"}, goal=old_goal)
    await m.call(
        token,
        "add_transaction",
        {
            "amount": "12.00",
            "category": "groceries",
            "date": "2026-10-05",
            "idempotency_key": new_key(),
        },
    )
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    assert preview["existing_plan"] is True
    assert any(
        "replaces it, including days already past" in w for w in preview["warnings"]
    )
    saved = structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
    )
    assert saved["status"] == "replaced"
    assert any("including days already past" in n for n in saved["notes"])
    rows = await plan_rows(connection, ana)
    assert "legacy category" not in {r["category"] for r in rows}
    # The 12.00 on 5 Oct overspent that day's groceries slice, so the rebuild's
    # automatic redistribution moved money in-month (as in the app). The BASE
    # plan — adjustments backed out — is exactly the reviewed one.
    assert any("automatic redistribution" in n for n in saved["notes"])
    base = defaultdict(Decimal)
    for r in rows:
        meta = r["plan_json"] or {}
        if meta.get("_mita_transaction_generated_v1"):
            continue
        adjustment = Decimal(str(meta.get(REALTIME_ADJUSTMENT_KEY, "0")))
        base[r["category"]] += Decimal(str(r["planned_amount"])) - adjustment
    assert dict(base) == preview_allocations(preview)
    goal_rows = await plan_rows(connection, ana, goal_rows=True)
    assert [(r["category"], r["planned_amount"]) for r in goal_rows] == [
        ("goal_savings", Decimal("5.00"))
    ]
    spent = sum(Decimal(str(r["spent_amount"])) for r in rows)
    assert spent == Decimal("12.00")  # the ledger, re-accrued once


async def test_next_month_can_be_planned_but_not_later_or_earlier(m, ana, connection):
    token = m.token(ana)
    nxt = structured(
        await m.call(token, "preview_monthly_budget", {"month": "2026-11"})
    )
    assert nxt["month"] == "2026-11" and nxt["days_remaining"] is None
    saved = structured(
        await m.call(token, "save_monthly_budget", {"draft_token": nxt["draft_token"]})
    )
    assert saved["month"] == "2026-11"
    for bad in ("2026-12", "2026-09", "2026-13"):
        result = await m.call(token, "preview_monthly_budget", {"month": bad})
        assert result.is_error, bad
    assert (await m.call(token, "preview_monthly_budget", {"month": "Oct"})).is_error


async def test_a_draft_cannot_be_saved_after_its_month_ended(mcp, ana, connection):
    late = mcp.at(datetime(2026, 10, 31, 21, 50, tzinfo=timezone.utc))  # 23:50 Sofia
    draft = structured(await late.call(late.token(ana), "preview_monthly_budget", {}))[
        "draft_token"
    ]
    after = mcp.at(
        datetime(2026, 10, 31, 22, 10, tzinfo=timezone.utc)
    )  # 1 Nov in Sofia
    result = await after.call(
        after.token(ana), "save_monthly_budget", {"draft_token": draft}
    )
    assert result.is_error and "current month" in result.content[0].text
    assert await plan_rows(connection, ana) == []


@pytest.mark.parametrize(
    "income,currency,message",
    [
        (None, "EUR", "monthly net income"),
        ("2500", None, "currency"),
    ],
)
async def test_preview_needs_income_and_currency(m, seed, income, currency, message):
    user = await seed.user(income="0", onboarded=False)
    args = {}
    if income:
        args["monthly_net_income"] = income
    if currency:
        args["currency"] = currency
    await m.call(m.token(user), "update_financial_profile", args)
    result = await m.call(m.token(user), "preview_monthly_budget", {})
    assert result.is_error and message in result.content[0].text


async def test_obligations_above_income_are_refused(m, ana):
    token = m.token(ana)
    await m.call(
        token,
        "add_recurring_expense",
        {
            "name": "Mortgage",
            "amount": 2000,
            "category": "mortgage",
            "recurrence": "monthly",
            "day_of_month": 5,
            "idempotency_key": new_key(),
        },
    )
    result = await m.call(token, "preview_monthly_budget", {})
    assert (
        result.is_error
        and "more than their stated monthly net income" in result.content[0].text
    )


async def test_a_savings_target_that_does_not_fit_is_reduced_and_said(m, ana):
    token = m.token(ana)
    await m.call(token, "update_financial_profile", {"monthly_savings_target": 2000})
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    assert preview["savings_allocation"] == "1800.00"  # 2500 − 700 rent
    assert preview["category_allocations"] == [] and preview["flexible_total"] == "0.00"
    assert any("does not fit" in w for w in preview["warnings"])


async def test_how_obligations_are_counted(m, ana, seed):
    token = m.token(ana)
    await m.call(
        token,
        "add_recurring_expense",
        {
            "name": "Gym",
            "amount": 10,
            "category": "other",
            "recurrence": "weekly",
            "weekday": "monday",
            "idempotency_key": new_key(),
        },
    )
    await seed.scheduled(
        ana,
        category="insurance",
        amount=Decimal("240.00"),
        scheduled_date=date(2026, 10, 20),
        recurrence="once",
        merchant="SafeCar",
    )
    await seed.scheduled(
        ana,
        category="insurance",
        amount=Decimal("99.00"),
        scheduled_date=date(2026, 12, 20),
        recurrence="once",
    )
    await seed.scheduled(
        ana,
        category="other",
        amount=Decimal("50.00"),
        scheduled_date=date(2027, 2, 1),
        recurrence="monthly",
    )
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    counted = {
        (o["name"], o["amount"], o["basis"]) for o in preview["fixed_obligations"]
    }
    assert counted == {
        ("Rent", "700.00", "monthly"),
        ("Gym", "40.00", "weekly × 4 Mondays"),  # 5, 12, 19, 26 October
        ("SafeCar", "240.00", "one-time on 2026-10-20"),
    }
    assert preview["fixed_obligations_total"] == "980.00"


async def test_recorded_history_only_adds_warnings(m, ana, seed):
    for month in (7, 8, 9):
        await seed.txn(
            ana,
            "900.00",
            "groceries",
            datetime(2026, month, 10, 12, tzinfo=timezone.utc),
        )
    token = m.token(ana)
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    assert preview["history"] == {
        "months_used": 3,
        "period_start": "2026-07-01",
        "period_end": "2026-09-30",
        "average_monthly_spending": "900.00",
    }
    assert any(
        w.startswith("groceries: recorded average 900.00") for w in preview["warnings"]
    )
    # Same allocations as without history: history never changes the plan.
    engine = allocations_from_profile(
        monthly_income=Decimal("2500"),
        savings_goal=Decimal("400"),
        region="ZZ",
        fixed_expenses={"rent": Decimal("700")},
    )
    assert {
        c["category"]: Decimal(c["amount"]) for c in preview["category_allocations"]
    } == (engine.discretionary)


async def test_preview_is_deterministic(m, ana):
    token = m.token(ana)
    first = structured(await m.call(token, "preview_monthly_budget", {}))
    second = structured(await m.call(token, "preview_monthly_budget", {}))
    assert first == second  # same facts, same clock: same plan and same token


async def test_budget_writes_are_isolated_and_need_the_write_scope(
    m, ana, seed, connection
):
    bob = await seed.user(tz="UTC", currency="USD", income="9000.00")
    bob_plan_before = await plan_rows(connection, bob)
    token = m.token(ana, scopes=["profile:read", "finance:read"])
    preview = structured(
        await m.call(token, "preview_monthly_budget", {})
    )  # read scope suffices
    denied = await m.call(
        token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
    )
    assert denied.structured_content["error"]["category"] == "forbidden"
    full = m.token(ana)
    structured(
        await m.call(
            full, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
    )
    assert await plan_rows(connection, bob) == bob_plan_before
    bob_preview = structured(await m.call(m.token(bob), "preview_monthly_budget", {}))
    assert bob_preview["fixed_obligations"] == []  # Ana's rent is not Bob's
