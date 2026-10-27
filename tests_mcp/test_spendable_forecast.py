"""The safe daily limit counts only money that is there to be spent.

Owner decision (2026-10-23): money the plan sets aside — the Savings line,
savings-goal reservations, investment contributions
(``category_priority.SET_ASIDE_CATEGORIES``) — is not spendable. The safe
daily limit is

    (remaining_budget − savings_set_aside) / days_remaining

where ``savings_set_aside`` is, per set-aside line, what it still holds
(planned minus deposited, never below zero). The month-end projection and the
status are unchanged: they still compare spending with the whole plan.

Engine cases call ``compute_forecast`` directly; the tool cases use a
hand-built plan and ledger (as ``test_finance_accuracy``) and the canonical
preview → save path. October 2026 has 31 days; "today" is Monday 19 October:
19 days elapsed, 12 left.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.core.category_priority import SET_ASIDE_CATEGORIES, is_sacred, is_set_aside
from app.core.financial_constants import FinancialConstants
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    compute_forecast,
)
from app.services.core.engine.calendar_engine import CATEGORY_BEHAVIOR
from app.services.core.engine.goal_budget_sync import GOAL_SAVINGS_CATEGORY
from app.services.monthly_plan_service import SAVINGS_GOAL_CATEGORY
from tests_mcp.conftest import structured
from tests_mcp.test_budget_plan import NOW as ANA_NOW
from tests_mcp.test_budget_plan import seed_ana

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
SPENT = Decimal("1124.60")


def _forecast(rows, day=19, month=10):
    return compute_forecast(
        daily_plans=rows, goals=[], year=2026, month=month, today=date(2026, 10, day)
    )


def _month(spending_plan, spent=SPENT, set_aside=None):
    """One spending line plus set-aside lines {category: (planned, deposited)}."""
    first = date(2026, 10, 1)
    rows = [DailyPlanData(first, "groceries", Decimal(spending_plan), Decimal(spent))]
    for category, (planned, deposited) in (set_aside or {}).items():
        rows.append(
            DailyPlanData(first, category, Decimal(planned), Decimal(deposited))
        )
    return rows


SAVINGS = SAVINGS_GOAL_CATEGORY  # "savings goal based", the reviewed budget's line
GOAL = GOAL_SAVINGS_CATEGORY  # "goal_savings", a goal's daily reservation


# --- the set-aside lines ------------------------------------------------------------


def test_set_aside_lines_are_the_savings_lines_no_expense_can_spend():
    assert GOAL_SAVINGS_CATEGORY in SET_ASIDE_CATEGORIES
    assert SAVINGS_GOAL_CATEGORY in SET_ASIDE_CATEGORIES
    assert all(is_sacred(c) for c in SET_ASIDE_CATEGORIES)
    # No expense can be recorded against them …
    assert not SET_ASIDE_CATEGORIES & set(
        FinancialConstants.VALID_TRANSACTION_CATEGORIES
    )
    # … and the bills that are SACRED but get paid are spendable plan.
    for paid in ("rent", "mortgage", "utilities", "insurance medical"):
        assert is_sacred(paid) and not is_set_aside(paid)
    assert {c for c in CATEGORY_BEHAVIOR if is_set_aside(c)} == {
        "savings goal based",
        "savings emergency",
        "investment contribution",
    }


# --- engine: exact values -------------------------------------------------------------


def test_a_without_savings_the_limit_is_unchanged():
    result = _forecast(_month("2325.00"))
    assert result.remaining_budget == Decimal("1200.40")
    assert result.savings_set_aside == Decimal("0")
    assert result.safe_daily_limit == Decimal("100.03")  # 1200.40 / 12
    assert result.current_daily_pace == Decimal("59.19")  # 1124.60 / 19
    assert result.projected_month_end_balance == Decimal("490.12")
    assert result.status == "on_track"


def test_b_the_savings_line_is_not_spendable():
    result = _forecast(_month("1925.00", set_aside={SAVINGS: ("400.00", "0")}))
    assert result.total_planned == Decimal("2325.00")
    assert result.remaining_budget == Decimal("1200.40")  # whole plan, as before
    assert result.savings_set_aside == Decimal("400.00")
    assert result.safe_daily_limit == Decimal("66.70")  # (1200.40 - 400) / 12
    # Lower than case A by the savings spread over the days left: 400 / 12.
    assert Decimal("100.03") - result.safe_daily_limit == Decimal("33.33")
    assert result.current_daily_pace == Decimal("59.19")
    assert result.projected_month_end_spend == Decimal("1834.88")
    assert result.projected_month_end_balance == Decimal("490.12")  # unchanged
    assert result.status == "on_track"


def test_c_a_goal_reservation_is_not_spendable():
    result = _forecast(_month("2149.00", set_aside={GOAL: ("176.00", "0")}))
    assert result.remaining_budget == Decimal("1200.40")
    assert result.savings_set_aside == Decimal("176.00")
    assert result.safe_daily_limit == Decimal("85.37")  # 1024.40 / 12 = 85.366…


@pytest.mark.parametrize("category", sorted(SET_ASIDE_CATEGORIES))
def test_c_every_set_aside_line_is_left_out_alike(category):
    rows = _month("1925.00") + [
        DailyPlanData(date(2026, 10, 1), category, Decimal("400.00"), Decimal("0"))
    ]
    assert _forecast(rows).safe_daily_limit == Decimal("66.70")


@pytest.mark.parametrize(
    "deposited, still_set_aside, safe",
    [
        ("0", "176.00", "85.37"),
        ("100.00", "76.00", "85.37"),  # part deposited: only the rest held back
        ("176.00", "0.00", "85.37"),  # filled: holds nothing back
        ("250.00", "0.00", "79.20"),  # 74.00 beyond the plan, counted once
    ],
)
def test_d_a_filled_line_holds_nothing_back_and_nothing_counts_twice(
    deposited, still_set_aside, safe
):
    rows = _month("2149.00", set_aside={GOAL: ("176.00", deposited)})
    result = _forecast(rows)
    assert result.total_spent == SPENT + Decimal(deposited)
    assert result.savings_set_aside == Decimal(still_set_aside)
    assert result.safe_daily_limit == Decimal(safe)


def test_e_spending_into_the_savings_turns_the_limit_negative():
    result = _forecast(
        _month("1925.00", spent="2000.00", set_aside={SAVINGS: ("400.00", "0")})
    )
    assert result.remaining_budget == Decimal("325.00")  # still "left" in the plan
    assert result.safe_daily_limit == Decimal("-6.25")  # (325 - 400) / 12
    assert result.projected_month_end_balance == Decimal("-938.12")
    assert result.status == "danger"

    exactly_spent = _forecast(
        _month("1925.00", spent="1925.00", set_aside={SAVINGS: ("400.00", "0")})
    )
    assert exactly_spent.safe_daily_limit == Decimal("0.00")


def test_f_no_days_left_means_no_division():
    rows = _month("1925.00", spent="1900.00", set_aside={SAVINGS: ("400.00", "0")})
    last_day = _forecast(rows, day=31)
    assert last_day.days_remaining == 0
    assert last_day.safe_daily_limit == Decimal("0")
    assert last_day.projected_month_end_balance == Decimal("425.00")
    assert last_day.status == "on_track"
    finished = compute_forecast(
        daily_plans=rows, goals=[], year=2026, month=10, today=date(2026, 11, 5)
    )
    assert (finished.days_remaining, finished.safe_daily_limit) == (0, Decimal("0"))


@pytest.mark.parametrize(
    "spending_plan, set_aside, day, safe",
    [
        ("1224.65", "0", 29, "50.03"),  # 100.05 / 2 = 50.025 → half up
        ("1224.60", "300.00", 28, "33.33"),  # (400.00 - 300.00) / 3
        ("1124.55", "0", 29, "-0.03"),  # -0.05 / 2 = -0.025 → away from zero
    ],
)
def test_g_cents_round_half_up(spending_plan, set_aside, day, safe):
    rows = _month(spending_plan, set_aside={SAVINGS: (set_aside, "0")})
    result = _forecast(rows, day=day)
    assert result.safe_daily_limit == Decimal(safe)
    assert result.safe_daily_limit.as_tuple().exponent == -2


# --- the tools: a hand-built plan and ledger -------------------------------------------


def at(day, hour=10):
    return datetime(2026, 10, day, hour, 0, tzinfo=timezone.utc)


async def _october(seed, *, savings: bool, goal: bool = False):
    """Plan 2,325.00 (rent 700 on the 1st, groceries 30 a day, dining 73.75 on
    four weekends, then 400.00 of Savings at 20.00 a day over 1–20 October —
    or a 400.00 clothing budget, or 176.00 reserved for a goal); spent 1,124.60
    by Monday the 19th, 36.80 of it today."""
    user = await seed.user(currency="EUR", income="2500.00")
    for d in range(1, 32):
        rows = {"groceries": "30.00"}
        if d == 1:
            rows["rent"] = "700.00"
        if d in (3, 10, 17, 24):
            rows["dining out"] = "73.75"
        if savings and d <= 20:
            rows[SAVINGS_GOAL_CATEGORY] = "20.00"
        await seed.plan(user, date(2026, 10, d), rows)
    if goal:
        await seed.plan(user, date(2026, 10, 6), {"clothing": "224.00"})
        target = await seed.goal(user, title="Holiday")
        for d in range(10, 32):
            await seed.plan(
                user, date(2026, 10, d), {"goal_savings": "8.00"}, goal=target
            )
    elif not savings:
        await seed.plan(user, date(2026, 10, 6), {"clothing": "400.00"})
    await seed.txn(user, "700.00", "rent", at(1))
    for day, amount in (
        (2, "52.30"),
        (5, "61.20"),
        (8, "48.90"),
        (12, "70.10"),
        (15, "55.40"),
    ):
        await seed.txn(user, amount, "groceries", at(day))
    await seed.txn(user, "36.80", "groceries", at(19), merchant="Lidl")
    await seed.txn(user, "99.90", "dining", at(10))
    return user


async def test_the_forecast_tool_leaves_the_savings_line_out(mcp, seed):
    user = await _october(seed, savings=True)
    m = mcp.at(NOW)
    data = structured(await m.call(m.token(user), "get_budget_forecast"))
    assert (data["days_elapsed"], data["days_remaining"]) == (19, 12)
    assert data["total_planned"] == "2325.00"
    assert data["total_spent"] == "1124.60"
    assert data["remaining_budget"] == "1200.40"
    assert data["savings_set_aside"] == "400.00"
    assert data["safe_daily_limit"] == "66.70"
    assert data["current_daily_pace"] == "59.19"
    assert data["projected_month_end_spend"] == "1834.88"
    assert data["projected_month_end_balance"] == "490.12"
    assert data["status"] == "on_track"

    status = structured(await m.call(m.token(user), "get_budget_status"))
    assert (status["total_planned"], status["total_remaining"]) == (
        "2325.00",
        "1200.40",
    )
    savings = next(c for c in status["categories"] if c["category_label"] == "Savings")
    assert (savings["planned"], savings["spent"]) == ("400.00", "0.00")
    # Today's 20.00 of Savings is not something to spend today.
    assert status["today"] == {
        "date": "2026-10-19",
        "planned": "30.00",
        "spent": "36.80",
        "remaining": "-6.80",
        # no bill line today: the everyday part is the whole of today (R3)
        "everyday_planned": "30.00",
        "everyday_spent": "36.80",
        "everyday_remaining": "-6.80",
    }


async def test_the_forecast_tool_leaves_a_goal_reservation_out(mcp, seed):
    user = await _october(seed, savings=False, goal=True)
    m = mcp.at(NOW)
    data = structured(await m.call(m.token(user), "get_budget_forecast"))
    assert data["total_planned"] == "2325.00"
    assert data["savings_set_aside"] == "176.00"
    assert data["safe_daily_limit"] == "85.37"
    status = structured(await m.call(m.token(user), "get_budget_status"))
    assert status["today"]["planned"] == "30.00"  # the goal's 8.00 is not spendable


async def test_h_each_account_gets_its_own_figure(mcp, seed):
    saver = await _october(seed, savings=True)
    spender = await _october(seed, savings=False)
    m = mcp.at(NOW)
    saver_data = structured(await m.call(m.token(saver), "get_budget_forecast"))
    spender_data = structured(await m.call(m.token(spender), "get_budget_forecast"))
    assert (saver_data["savings_set_aside"], saver_data["safe_daily_limit"]) == (
        "400.00",
        "66.70",
    )
    assert (spender_data["savings_set_aside"], spender_data["safe_daily_limit"]) == (
        "0.00",
        "100.03",
    )
    assert saver_data["total_spent"] == spender_data["total_spent"] == "1124.60"


async def test_the_reviewed_budget_savings_target_is_not_spendable(mcp, seed):
    """The canonical writer: preview → save puts the user's savings target in
    the plan as the Savings line; the forecast keeps it out (before the fix:
    76.70 a day here, the 400.00 spread over the 20 days left)."""
    m = mcp.at(ANA_NOW)  # 11 October, 12:00 in Sofia: 11 days elapsed, 20 left
    ana = await seed_ana(m, seed)
    token = m.token(ana)
    preview = structured(await m.call(token, "preview_monthly_budget", {}))
    assert preview["savings_allocation"] == "400.00"
    structured(
        await m.call(
            token, "save_monthly_budget", {"draft_token": preview["draft_token"]}
        )
    )
    for amount, category, day in (
        (700, "rent", "2026-10-01"),
        (54.20, "groceries", "2026-10-05"),
        (36.80, "groceries", "2026-10-11"),
    ):
        structured(
            await m.call(
                token,
                "add_transaction",
                {
                    "amount": amount,
                    "category": category,
                    "date": day,
                    "idempotency_key": uuid.uuid4().hex,
                },
            )
        )
    data = structured(await m.call(token, "get_budget_forecast"))
    assert data["total_planned"] == preview["plan_total"] == "2325.00"
    assert data["remaining_budget"] == "1534.00"
    assert data["savings_set_aside"] == "400.00"
    # Rent, the only bill, is recorded, so nothing is held. The reviewed plan's
    # medical insurance line (105.00) is the budget engine's own allowance —
    # Ana never stated insurance — and no expense is ever recorded under it,
    # so it is everyday money, not a bill (R3, r3-bills-reserve.md).
    assert data["commitments_reserved"] == "0.00"
    assert data["safe_daily_limit"] == "56.70"  # (1534.00 - 400.00) / 20
