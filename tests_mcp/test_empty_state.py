"""A user with no data gets explicit absence — never a default figure."""

from datetime import datetime, timezone

from tests_mcp.conftest import structured

NOW = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)

# Values the codebase has used as placeholders before (CLAUDE.md): monthly
# income defaults, tier averages, /30 daily budgets, neutral scores.
PLACEHOLDERS = ("3000", "1500", "50.00", "173.33", "0.15", '"stable"', '"C"', "75")


def _no_placeholders(text: str):
    for value in PLACEHOLDERS:
        assert value not in text, value


async def test_new_account_has_no_invented_figures(mcp, seed):
    m = mcp.at(NOW)
    user = await seed.user(income=None, onboarded=False, name=None)
    token = m.token(user)

    summary = structured(await m.call(token, "get_financial_summary"))
    assert summary["stated_monthly_income"] is None
    assert summary["plan_status"] == "not_generated"
    assert summary["planned_total"] is None and summary["remaining_total"] is None
    assert summary["spent_total"] == "0.00" and summary["transaction_count"] == 0
    assert summary["top_categories"] == []
    assert any("onboarding" in n for n in summary["notes"])

    status = structured(await m.call(token, "get_budget_status"))
    assert status["plan_status"] == "not_generated"
    assert status["categories"] == []
    assert status["total_planned"] == "0.00" and status["total_spent"] == "0.00"
    assert status["today"] == {
        "date": "2026-03-15",
        "planned": "0.00",
        "spent": "0.00",
        "remaining": "0.00",
    }

    forecast = structured(await m.call(token, "get_budget_forecast"))
    assert forecast["plan_status"] == "not_generated" and forecast["status"] is None
    for key in (
        "total_planned",
        "total_spent",
        "remaining_budget",
        "current_daily_pace",
        "safe_daily_limit",
        "projected_month_end_spend",
        "projected_month_end_balance",
    ):
        assert forecast[key] is None, key
    assert forecast["categories_at_risk"] == []

    assert structured(await m.call(token, "get_goals"))["goals"] == []
    recurring = structured(await m.call(token, "get_recurring_expenses"))
    assert recurring["scheduled_recurring"] == recurring["upcoming_one_time"] == []
    assert recurring["marked_recurring"] == recurring["inferred"] == []
    txns = structured(await m.call(token, "list_transactions"))
    assert txns["transactions"] == [] and txns["matching_total"] == "0.00"

    profile = structured(await m.call(token, "get_profile"))
    assert profile["name"] is None and profile["has_completed_onboarding"] is False

    for tool in ("get_financial_summary", "get_budget_status", "get_budget_forecast"):
        _no_placeholders((await m.call(token, tool)).content[0].text)


async def test_zero_income_is_reported_as_unknown(mcp, seed):
    user = await seed.user(income="0")
    data = structured(await mcp.at(NOW).call(mcp.token(user), "get_financial_summary"))
    assert data["stated_monthly_income"] is None


async def test_onboarded_user_without_this_months_plan(mcp, seed):
    """The month has not been materialized yet (it is created on first app
    open): report it, do not compute a preview, and do not write it."""
    m = mcp.at(NOW)
    user = await seed.user()
    await seed.txn(user, "25.00", "food", datetime(2026, 3, 3, tzinfo=timezone.utc))
    status = structured(await m.call(m.token(user), "get_budget_status"))
    assert status["plan_status"] == "not_generated"
    assert status["total_planned"] == "0.00" and status["total_spent"] == "25.00"
    assert [c["state"] for c in status["categories"]] == ["unplanned_spending"]
    assert any("has not generated a budget plan" in n for n in status["notes"])
    # The read did not materialize the month.
    from sqlalchemy import text

    count = await seed.connection.scalar(
        text("SELECT count(*) FROM daily_plan WHERE user_id = :u"), {"u": user.id}
    )
    assert count == 0


async def test_transaction_only_plan_rows_are_not_a_plan(mcp, seed):
    """rebuild_month_plan creates zero-allocation rows for unplanned spend;
    those must not flip plan_status to generated (month_has_plan semantics)."""
    from datetime import date

    m = mcp.at(NOW)
    user = await seed.user()
    await seed.plan(user, date(2026, 3, 3), {"food": "0.00"})
    status = structured(await m.call(m.token(user), "get_budget_status"))
    assert status["plan_status"] == "not_generated"
