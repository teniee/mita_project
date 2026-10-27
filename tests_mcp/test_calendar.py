"""MITA's financial calendar: exact figures, the same figures as the other
tools, the user's own data only, and the component bound to it.

The month (``seed_month``): Europe/Sofia, EUR, "today" Monday 19 October 2026
(19 days begun, 12 left). Hand-built plan, as the canonical writers store it:

    1 Oct  rent 850, groceries 20, Savings 100 (set aside)
    2 Oct  groceries 20, dining out 30
    5 Oct  utilities 120, groceries 20
   14 Oct  groceries 40, Savings 100
   15 Oct  groceries 40
   19 Oct  groceries 30, dining out 25            (today)
   20 Oct  groceries 30
   23 Oct  dining out 45, Savings 100
   31 Oct  groceries 25, insurance 60

    plan 1,655.00 = commitments 1,030.00 (rent 850 + utilities 120 +
    insurance 60, a saved payment's category) + set aside 300.00 (Savings)
    + everyday 325.00 (groceries 225 + dining out 100)

Recorded: 1 Oct rent 850.00 and groceries 18.40; 3 Oct groceries 12.00 (no
plan that day); 14 Oct groceries 52.10; 14 Oct 22:30 UTC dining 15.00 (01:30
on the 15th in Sofia); 19 Oct groceries 22.50; a deleted 999.99 on 2 Oct.

    spent 970.00 (commitments 850.00, everyday 120.00), left 685.00,
    set aside 300.00, held for bills 210.00 (utilities 120 and insurance 60
    not recorded yet; internet 30, a saved payment the plan does not cover)
    -> left to spend 175.00 / 12 days = 14.58 a day

Saved payments: insurance 60.00 monthly from 30 Sep (falls on 30 Oct);
internet 30.00 monthly ("subscriptions") from 27 Oct, a category with no plan
line; a cancelled one and another month's one-time payment, both not shown.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.mcp.config import McpSettings
from app.mcp.queries.calendar import (
    SavedPayment,
    build_calendar,
    counts_in_month,
    occurrences_in_month,
)
from app.mcp.ui import CALENDAR_URI, calendar_html
from app.services.monthly_plan_service import SAVINGS_GOAL_CATEGORY
from tests_mcp.conftest import (
    make_settings,
    mcp_client,
    mint_token,
    started,
    structured,
)

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 19)
SAVINGS = SAVINGS_GOAL_CATEGORY
D = Decimal


def utc(day: int, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


async def seed_month(seed, *, tz="Europe/Sofia"):
    user = await seed.user(tz=tz, currency="EUR", income="3200.00")
    plan = {
        1: {"rent": "850.00", "groceries": "20.00", SAVINGS: "100.00"},
        2: {"groceries": "20.00", "dining out": "30.00"},
        5: {"utilities": "120.00", "groceries": "20.00"},
        14: {"groceries": "40.00", SAVINGS: "100.00"},
        15: {"groceries": "40.00"},
        19: {"groceries": "30.00", "dining out": "25.00"},
        20: {"groceries": "30.00"},
        23: {"dining out": "45.00", SAVINGS: "100.00"},
        31: {"groceries": "25.00", "insurance": "60.00"},
    }
    for day, allocations in plan.items():
        await seed.plan(user, date(2026, 10, day), allocations)
    await seed.txn(user, "850.00", "rent", utc(1, 8), merchant="Landlord")
    await seed.txn(user, "18.40", "groceries", utc(1, 17), merchant="Lidl")
    await seed.txn(user, "12.00", "groceries", utc(3, 10), merchant="Bakery")
    await seed.txn(user, "52.10", "groceries", utc(14, 16), merchant="Kaufland")
    await seed.txn(user, "15.00", "dining", utc(14, 22, 30), merchant="Pizza place")
    await seed.txn(user, "22.50", "groceries", utc(19, 9), merchant="Billa")
    await seed.txn(user, "999.99", "shopping", utc(2, 12), deleted=True)
    await seed.scheduled(
        user,
        category="insurance",
        amount=D("60.00"),
        scheduled_date=date(2026, 9, 30),
        recurrence="monthly",
        merchant="Allianz",
    )
    await seed.scheduled(
        user,
        category="subscriptions",
        amount=D("30.00"),
        scheduled_date=date(2026, 10, 27),
        recurrence="monthly",
        merchant="Home internet",
    )
    await seed.scheduled(
        user,
        category="utilities",
        amount=D("75.00"),
        scheduled_date=date(2026, 10, 25),
        recurrence="monthly",
        status="cancelled",
    )
    await seed.scheduled(
        user,
        category="other",
        amount=D("40.00"),
        scheduled_date=date(2026, 11, 2),
        recurrence=None,
    )
    return user


def by_date(out):
    return {day["date"]: day for day in out["days"]}


# --- exact figures ------------------------------------------------------------------


async def test_the_month_summary_is_exact_and_adds_up_to_the_plan(mcp, seed):
    user = await seed_month(seed)
    out = structured(await mcp.at(NOW).call(mcp.token(user), "get_calendar_month"))
    assert (out["year"], out["month"], out["month_position"]) == (2026, 10, "current")
    assert (out["currency"], out["timezone"], out["today"]) == (
        "EUR",
        "Europe/Sofia",
        "2026-10-19",
    )
    assert out["plan_status"] == "generated"
    assert out["summary"] == {
        "stated_monthly_income": "3200.00",
        "total_planned": "1655.00",
        "commitments_planned": "1030.00",
        "set_aside_planned": "300.00",
        "everyday_planned": "325.00",
        "total_spent": "970.00",
        "commitments_spent": "850.00",
        "everyday_spent": "120.00",
        "total_remaining": "685.00",
        "savings_set_aside": "300.00",
        "left_to_spend": "175.00",  # 685.00 - 300.00 - 210.00
        "average_per_day": "14.58",  # 175.00 / 12
        "days_elapsed": 19,
        "days_remaining": 12,
        # utilities 120 + insurance 60 (planned, not recorded) + internet 30
        # (saved, due on the 27th, no plan line): bills come first
        "commitments_reserved": "210.00",
        # 20 Oct 30.00 + 23 Oct 45.00 + 31 Oct 85.00 (the Savings slices excluded)
        "planned_after_today": "160.00",
        "bills_due_after_today": "90.00",  # internet 30 (27th) + insurance 60 (30th)
    }
    s = out["summary"]
    assert D(s["commitments_planned"]) + D(s["set_aside_planned"]) + D(
        s["everyday_planned"]
    ) == D(s["total_planned"])
    assert D(s["commitments_spent"]) + D(s["everyday_spent"]) == D(s["total_spent"])
    groups = {c["category"]: c["group"] for c in out["categories"]}
    assert groups == {
        "rent": "commitment",
        "utilities": "commitment",
        "insurance": "commitment",  # a saved payment's category
        SAVINGS: "set_aside",
        "groceries": "everyday",
        "dining out": "everyday",
    }
    lines = {c["category"]: c for c in out["categories"]}
    assert lines["dining out"]["category_codes"] == ["dining", "dining out"]
    assert (lines["dining out"]["spent"], lines["groceries"]["spent"]) == (
        "15.00",
        "105.00",
    )
    assert lines["groceries"]["remaining"] == "120.00"


async def test_each_date_shows_its_plan_and_spending_in_the_users_timezone(mcp, seed):
    user = await seed_month(seed)
    days = by_date(
        structured(await mcp.at(NOW).call(mcp.token(user), "get_calendar_month"))
    )
    assert len(days) == 31 and list(days)[0] == "2026-10-01"

    def row(key):
        d = days[key]
        return (
            d["day_kind"],
            d["state"],
            d["planned"],
            d["planned_everyday"],
            d["set_aside"],
            d["spent"],
            d["spent_everyday"],
            d["everyday_left"],
        )

    # Rent planned and paid on the 1st: a commitment, not everyday overspending.
    assert row("2026-10-01") == (
        "past",
        "within",
        "870.00",
        "20.00",
        "100.00",
        "868.40",
        "18.40",
        "1.60",
    )
    # The deleted 999.99 never counts.
    assert row("2026-10-02") == (
        "past",
        "within",
        "50.00",
        "50.00",
        "0.00",
        "0.00",
        "0.00",
        "50.00",
    )
    # Spending on a date with no everyday plan: shown, no verdict.
    assert row("2026-10-03")[:2] == ("past", "unplanned")
    assert row("2026-10-03")[5:] == ("12.00", "12.00", None)
    assert row("2026-10-04")[:2] == ("past", "quiet")
    # Utilities planned on the 5th and not recorded: the everyday plan is met.
    assert row("2026-10-05") == (
        "past",
        "within",
        "140.00",
        "20.00",
        "0.00",
        "0.00",
        "0.00",
        "20.00",
    )
    assert row("2026-10-14") == (
        "past",
        "over",
        "40.00",
        "40.00",
        "100.00",
        "52.10",
        "52.10",
        "-12.10",
    )
    # 22:30 UTC on the 14th is 01:30 on the 15th in Sofia.
    assert row("2026-10-15")[5:] == ("15.00", "15.00", "25.00")
    assert row("2026-10-19") == (
        "today",
        "within",
        "55.00",
        "55.00",
        "0.00",
        "22.50",
        "22.50",
        "32.50",
    )
    # Future dates: the plan, never a forecast and never spending.
    assert row("2026-10-20") == (
        "future",
        "planned",
        "30.00",
        "30.00",
        "0.00",
        None,
        None,
        None,
    )
    assert row("2026-10-23")[:5] == ("future", "planned", "45.00", "45.00", "100.00")
    assert row("2026-10-30")[:3] == ("future", "free", "0.00")
    assert row("2026-10-31")[:4] == ("future", "planned", "85.00", "25.00")
    assert [k for k, d in days.items() if d["state"] == "over"] == ["2026-10-14"]


async def test_saved_payments_fall_on_their_dates_and_say_whether_the_plan_has_them(
    mcp, seed
):
    user = await seed_month(seed)
    out = structured(await mcp.at(NOW).call(mcp.token(user), "get_calendar_month"))
    assert out["bills"] == [
        {
            "date": "2026-10-27",
            "name": "Home internet",
            "category": "subscriptions",
            "category_label": "Subscriptions",
            "amount": "30.00",
            "recurrence": "monthly",
            "in_plan": False,
        },
        {
            "date": "2026-10-30",
            "name": "Allianz",
            "category": "insurance",
            "category_label": "Insurance",
            "amount": "60.00",
            "recurrence": "monthly",
            "in_plan": True,
        },
    ]
    notes = " ".join(out["notes"])
    assert "210.00 EUR is held for bills not recorded as paid yet" in notes
    assert "1 saved payment(s) this month fall on a category with no money" in notes


async def test_the_calendar_reports_the_same_figures_as_status_and_forecast(mcp, seed):
    user = await seed_month(seed)
    token = mcp.token(user)
    at = mcp.at(NOW)
    cal = structured(await at.call(token, "get_calendar_month"))
    status = structured(await at.call(token, "get_budget_status"))
    forecast = structured(await at.call(token, "get_budget_forecast"))
    summary = cal["summary"]
    assert summary["total_planned"] == status["total_planned"] == "1655.00"
    assert summary["total_spent"] == status["total_spent"] == "970.00"
    assert summary["total_remaining"] == status["total_remaining"]
    assert summary["average_per_day"] == forecast["safe_daily_limit"]
    assert summary["savings_set_aside"] == forecast["savings_set_aside"]
    assert summary["days_remaining"] == forecast["days_remaining"]
    assert summary["commitments_reserved"] == forecast["commitments_reserved"]
    assert D(summary["left_to_spend"]) == (
        D(forecast["remaining_budget"])
        - D(forecast["savings_set_aside"])
        - D(forecast["commitments_reserved"])
    )
    today = by_date(cal)["2026-10-19"]
    assert (today["planned"], today["spent"]) == (
        status["today"]["planned"],
        status["today"]["spent"],
    )
    line_totals = {c["category"]: (c["planned"], c["spent"]) for c in cal["categories"]}
    assert line_totals == {
        c["category"]: (c["planned"], c["spent"]) for c in status["categories"]
    }


async def test_a_month_without_a_plan_shows_spending_and_no_plan_figures(mcp, seed):
    user = await seed.user(tz="UTC", currency="EUR")
    await seed.txn(user, "41.20", "groceries", utc(12))
    out = structured(await mcp.at(NOW).call(mcp.token(user), "get_calendar_month"))
    assert out["plan_status"] == "not_generated"
    summary = out["summary"]
    for key in (
        "total_planned",
        "commitments_planned",
        "set_aside_planned",
        "everyday_planned",
        "total_remaining",
        "savings_set_aside",
        "left_to_spend",
        "average_per_day",
        "commitments_reserved",
        "planned_after_today",
    ):
        assert summary[key] is None, key
    assert summary["total_spent"] == "41.20"
    day = by_date(out)["2026-10-12"]
    assert (day["state"], day["planned"], day["spent"]) == (
        "unplanned",
        "0.00",
        "41.20",
    )
    assert any("no saved budget plan" in n for n in out["notes"])


async def test_past_and_future_months(mcp, seed):
    user = await seed_month(seed)
    await seed.plan(user, date(2026, 11, 2), {"groceries": "33.00", SAVINGS: "50.00"})
    await seed.plan(user, date(2026, 9, 7), {"groceries": "20.00"})
    await seed.txn(
        user, "25.00", "groceries", datetime(2026, 9, 7, 9, tzinfo=timezone.utc)
    )
    token = mcp.token(user)
    nov = structured(
        await mcp.at(NOW).call(token, "get_calendar_month", {"year": 2026, "month": 11})
    )
    assert nov["month_position"] == "future"
    assert all(d["day_kind"] == "future" and d["spent"] is None for d in nov["days"])
    # A future month: the safe daily figure over the whole month (30 days).
    assert nov["summary"]["days_remaining"] == 30
    assert nov["summary"]["planned_after_today"] == "33.00"  # every date is ahead
    # The bills come first: insurance 60, internet 30 and the one-time 40
    # (2 Nov) are due in November and the plan holds 33.00 for spending, so
    # the average is negative: (33.00 - 130.00) / 30.
    assert nov["summary"]["commitments_reserved"] == "130.00"
    assert nov["summary"]["average_per_day"] == "-3.23"
    assert [b["date"] for b in nov["bills"]] == [
        "2026-11-02",  # the one-time payment, now in its month
        "2026-11-27",
        "2026-11-30",
    ]
    sep = structured(
        await mcp.at(NOW).call(token, "get_calendar_month", {"year": 2026, "month": 9})
    )
    assert sep["month_position"] == "past"
    assert sep["summary"]["average_per_day"] is None
    assert sep["summary"]["planned_after_today"] is None
    assert sep["summary"]["days_remaining"] == 0
    assert by_date(sep)["2026-09-07"]["state"] == "over"
    assert "The month has ended" in " ".join(sep["notes"])
    # The insurance payment starts on 30 September: never earlier.
    assert [b["date"] for b in sep["bills"]] == ["2026-09-30"]


# --- only the signed-in user's data -------------------------------------------------


async def test_another_users_month_never_appears(mcp, seed):
    user = await seed_month(seed)
    other = await seed.user(tz="Europe/Sofia", currency="EUR")
    await seed.plan(other, date(2026, 10, 19), {"groceries": "500.00"})
    await seed.txn(other, "444.44", "groceries", utc(19, 10))
    await seed.scheduled(other, category="rent", amount=D("2000.00"))
    out = structured(await mcp.at(NOW).call(mcp.token(user), "get_calendar_month"))
    assert out["summary"]["total_planned"] == "1655.00"
    assert out["summary"]["total_spent"] == "970.00"
    assert {b["amount"] for b in out["bills"]} == {"30.00", "60.00"}
    mine = structured(await mcp.at(NOW).call(mcp.token(other), "get_calendar_month"))
    assert mine["summary"]["total_spent"] == "444.44"


async def test_no_argument_selects_whose_calendar(mcp, seed):
    user = await seed_month(seed)
    for args in ({"user_id": str(user.id)}, {"email": user.email}):
        result = await mcp.at(NOW).call(
            mcp.token(user), "show_financial_calendar", args
        )
        assert result.is_error


# --- the render tool and its component ------------------------------------------------


async def test_show_returns_a_short_view_for_the_model_and_the_month_for_the_component(
    mcp, seed
):
    user = await seed_month(seed)
    result = await mcp.at(NOW).call(
        mcp.token(user), "show_financial_calendar", {"category": "groceries"}
    )
    view = structured(result)
    assert (view["year"], view["month"], view["category"]) == (2026, 10, "groceries")
    assert view["summary"]["average_per_day"] == "14.58"
    text = result.content[0].text
    assert text == view["shown"]
    assert text.startswith("MITA's calendar for October 2026 is on screen (EUR).")
    assert (
        "Plan 1655.00, spent 970.00, left 685.00 (300.00 set aside for savings "
        "and 210.00 held for bills not paid yet)." in text
    )
    assert "On average 14.58 a day for the 12 days left" in text
    assert "1 day went over the everyday plan." in text
    assert "Next saved bill: 30.00 on 2026-10-27." in text
    assert "Filtered to Groceries." in text
    # The month itself goes to the component only (``_meta``), not the model.
    payload = result.meta["mita/calendar"]
    assert result.meta["mita/view"] == {"focus_date": None, "category": "groceries"}
    month = payload["month"]
    assert month["summary"] == view["summary"]
    assert len(month["days"]) == 31
    assert payload["day_lines"]["2026-10-01"] == [
        ["rent", "850.00", "850.00"],
        [SAVINGS, "100.00", "0.00"],
        ["groceries", "20.00", "18.40"],
    ]
    assert payload["bill_lines"] == ["subscriptions", "insurance"]
    assert "days" not in view and "Landlord" not in str(view)


async def test_show_opens_on_a_date_and_refuses_a_date_outside_the_month(mcp, seed):
    user = await seed_month(seed)
    token = mcp.token(user)
    view = structured(
        await mcp.at(NOW).call(
            token, "show_financial_calendar", {"focus_date": "2026-11-12"}
        )
    )
    assert (view["year"], view["month"], view["focus_date"]) == (2026, 11, "2026-11-12")
    bad = await mcp.at(NOW).call(
        token,
        "show_financial_calendar",
        {"year": 2026, "month": 10, "focus_date": "2026-11-12"},
    )
    assert bad.is_error and "inside the month" in bad.content[0].text
    unknown = structured(
        await mcp.at(NOW).call(token, "show_financial_calendar", {"category": "Pets"})
    )
    assert unknown["category"] is None
    assert "No budget line called 'Pets' this month" in " ".join(unknown["notes"])


async def test_only_the_render_tool_is_bound_to_the_component(mcp, seed):
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    bound = {
        name
        for name, t in tools.items()
        if (t.meta or {}).get("ui", {}).get("resourceUri")
    }
    assert bound == {"show_financial_calendar"}
    show = tools["show_financial_calendar"].meta
    assert show["ui"]["resourceUri"] == show["openai/outputTemplate"] == CALENDAR_URI
    # What the component may call through the host: read tools only.
    callable_ = {
        name
        for name, t in tools.items()
        if "app" in (t.meta or {}).get("ui", {}).get("visibility", [])
    }
    assert callable_ == {"get_calendar_month", "list_transactions"}
    assert all(tools[name].annotations.read_only_hint for name in callable_)


async def _resources(make_service, settings: McpSettings, user):
    service = make_service(settings)
    async with started(service):
        async with mcp_client(service, mint_token(service, user)) as client:
            listed = (await client.list_resources()).resources
            read = await client.read_resource(CALENDAR_URI)
    return listed, read


async def test_the_component_is_an_mcp_app_resource_that_loads_nothing(
    make_service, seed
):
    user = await seed.user()
    listed, read = await _resources(make_service, make_settings(), user)
    entry = next(r for r in listed if str(r.uri) == CALENDAR_URI)
    assert entry.mime_type == "text/html;profile=mcp-app"
    (content,) = read.contents
    assert content.mime_type == "text/html;profile=mcp-app"
    assert content.text == calendar_html()
    meta = content.meta
    assert meta["ui"]["csp"] == {"connectDomains": [], "resourceDomains": []}
    assert meta["ui"]["prefersBorder"] is True
    assert "domain" not in meta["ui"]
    assert meta["openai/ui"]["availableDisplayModes"] == ["inline", "fullscreen"]
    assert "Do not repeat every figure" in meta["openai/widgetDescription"]


async def test_a_dedicated_widget_origin_is_declared_when_configured(
    make_service, seed
):
    user = await seed.user()
    settings = make_settings(widget_domain="https://mcp.example.test")
    _, read = await _resources(make_service, settings, user)
    assert read.contents[0].meta["ui"]["domain"] == "https://mcp.example.test"


def test_the_component_source_has_no_remote_code_or_html_injection():
    html = calendar_html()
    assert html.lstrip().lower().startswith("<!doctype html>")
    # Nothing to fetch: no external URL, stylesheet, script source or font.
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html, re.I)
    assert "@import" not in html and "url(http" not in html
    assert not re.search(r"\bfetch\(|XMLHttpRequest|WebSocket|EventSource", html)
    # Values from tool results are text, never markup.
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in html, sink
    assert not re.search(r"\beval\(|new Function\(", html)
    # Only MITA's read tools are ever called from the component.
    called = set(re.findall(r"callTool\(\s*[\"']([a-z_]+)[\"']", html))
    assert called <= {"get_calendar_month", "list_transactions"}, called


# --- the pure builder ----------------------------------------------------------------


def test_monthly_payments_keep_their_day_and_land_on_short_months_last_day():
    payment = SavedPayment(
        "rent", D("850.00"), None, anchor=date(2026, 1, 31), recurrence="monthly"
    )
    assert [o.day for o in occurrences_in_month(payment, 2026, 2)] == [
        date(2026, 2, 28)
    ]
    assert [o.day for o in occurrences_in_month(payment, 2026, 4)] == [
        date(2026, 4, 30)
    ]
    assert occurrences_in_month(payment, 2025, 12) == []  # before it starts


def test_weekly_payments_fall_on_every_matching_weekday_from_their_first_date():
    payment = SavedPayment(
        "subscriptions",
        D("9.99"),
        "Gym",
        anchor=date(2026, 10, 8),  # a Thursday
        recurrence="weekly",
    )
    assert [o.day.day for o in occurrences_in_month(payment, 2026, 10)] == [
        8,
        15,
        22,
        29,
    ]
    assert [o.day.day for o in occurrences_in_month(payment, 2026, 11)] == [
        5,
        12,
        19,
        26,
    ]


def test_one_time_payments_fall_only_on_their_date():
    for recurrence in (None, "once"):
        payment = SavedPayment("other", D("40.00"), None, date(2026, 11, 2), recurrence)
        assert occurrences_in_month(payment, 2026, 10) == []
        (only,) = occurrences_in_month(payment, 2026, 11)
        assert (only.day, only.recurrence) == (date(2026, 11, 2), None)


def test_a_bill_paid_on_another_day_than_planned_is_not_everyday_overspending():
    cal = build_calendar(
        year=2026,
        month=10,
        today=TODAY,
        planned={
            (date(2026, 10, 1), "rent"): D("850.00"),
            (date(2026, 10, 3), "groceries"): D("20.00"),
        },
        spent={
            (date(2026, 10, 3), "rent"): D("850.00"),
            (date(2026, 10, 3), "groceries"): D("19.00"),
        },
        plan_generated=True,
    )
    third = cal.days[2]
    assert (third.status, third.spent, third.spent_everyday) == (
        "within",
        D("869.00"),
        D("19.00"),
    )
    assert cal.days[0].status == "quiet"  # nothing everyday planned on the 1st


@pytest.mark.parametrize(
    "category,group",
    [
        ("rent", "commitment"),
        ("mortgage", "commitment"),
        ("utilities", "commitment"),
        # SACRED names no expense is recorded under: never a rebalancing donor,
        # but MITA cannot see them paid, so they are not bills (R3).
        ("debt repayment", "everyday"),
        ("insurance medical", "everyday"),
        ("school fees", "everyday"),
        ("courses online", "everyday"),
        (SAVINGS, "set_aside"),
        ("goal_savings", "set_aside"),
        ("investment contribution", "set_aside"),
        ("groceries", "everyday"),
        ("dining out", "everyday"),
        ("media streaming", "everyday"),
    ],
)
def test_every_line_has_one_group(category, group):
    cal = build_calendar(
        year=2026,
        month=10,
        today=TODAY,
        planned={(date(2026, 10, 1), category): D("10.00")},
        spent={},
        plan_generated=True,
    )
    (line,) = cal.lines
    assert line.group == group


def test_the_exported_image_uses_the_master_logomark():
    """The image carries MITA's mark; the paths are the Figma master vectors
    the sign-in page uses, never a redraw (brand rule: master files only)."""
    import re as _re

    from app.mcp.auth import pages

    master = _re.findall(
        r'<path fill="(#[0-9A-F]{6})" d="([^"]+)"/>',
        pages._MARK_PATHS[0] + "".join(pages._MARK_PATHS[1:]),
    )
    widget = _re.findall(r'\["(#[0-9A-F]{6})", "(M[^"]+)"\]', calendar_html())
    assert widget == master and len(master) == 4


def test_a_running_payment_is_a_commitment_even_when_its_next_date_is_next_month():
    """Saved on 24 October as "kindergarten, monthly on the 5th": the next date
    is 5 November, yet the reviewed October budget counted it
    (budget_draft.obligations_for_month), so October shows its line as a
    commitment — without a bill marker on a date that was never scheduled."""
    kindergarten = SavedPayment(
        "childcare", D("180.00"), "Kindergarten", date(2026, 11, 5), "monthly"
    )
    assert counts_in_month(kindergarten, 2026, 10)
    assert counts_in_month(kindergarten, 2026, 11)
    assert not counts_in_month(kindergarten, 2026, 8)  # not yet running
    cal = build_calendar(
        year=2026,
        month=10,
        today=TODAY,
        planned={(date(2026, 10, 5), "childcare"): D("180.00")},
        spent={(date(2026, 10, 5), "childcare"): D("180.00")},
        payments=[kindergarten],
        plan_generated=True,
    )
    (line,) = cal.lines
    assert line.group == "commitment"
    assert cal.bills == []
    assert cal.days[4].status == "quiet"  # a bill paid, not everyday spending
    one_time = SavedPayment("other", D("40.00"), None, date(2026, 11, 2), None)
    assert counts_in_month(one_time, 2026, 11)
    assert not counts_in_month(one_time, 2026, 10)
