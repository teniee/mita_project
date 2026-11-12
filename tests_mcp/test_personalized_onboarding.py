"""Personalized onboarding (MITA 2.8, Milestone 1) through the real MCP tools.

docs/chatgpt-app/personalization-2.8.md. Two completely different people
complete onboarding and get different budgets; MITA never budgets a line the
user did not confirm once they said what they spend on (no fuel for someone
without a car, no rent for someone who owns their flat); "none" and "skipped"
are answers and "never asked" is not; an existing user is never sent back
through setup and their figures are computed exactly as in 2.7.0; nothing is
saved without the user's yes; the country is the user's answer, ChatGPT's
approximate location only a question. November 2026, Europe/Sofia, EUR.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests_mcp.conftest import structured

D = Decimal
TZ = "Europe/Sofia"
NOV = "2026-11"
SOFIA_HINT = {
    "openai/userLocation": {
        "city": "Sofia",
        "region": "Sofia City",
        "country": "BG",
        "timezone": "Europe/Sofia",
        "latitude": "42.6977",
        "longitude": "23.3219",
    }
}


def at(day: int, month: int = 11) -> datetime:
    """Noon in Sofia on that date of 2026."""
    return datetime(2026, month, day, 10, 0, tzinfo=timezone.utc)


def key() -> str:
    return uuid.uuid4().hex


async def call(m, token, tool, arguments=None, meta=None):
    return structured(await m.call(token, tool, arguments or {}, meta=meta))


async def error_of(m, token, tool, arguments, meta=None):
    result = await m.call(token, tool, arguments, meta=meta)
    assert result.is_error, (arguments, result.structured_content)
    if result.structured_content and "error" in result.structured_content:
        return result.structured_content["error"]
    return {"message": result.content[0].text}  # refused by the input schema


async def newcomer(mcp, seed):
    """A brand-new ChatGPT account: nothing stated (country ZZ)."""
    m = mcp.at(at(2))
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    return user, m.token(user), m


async def recurring(m, token, name, amount, category, day):
    return await call(
        m,
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


async def preview(m, token, **arguments):
    arguments.setdefault("month", NOV)
    return await call(m, token, "preview_monthly_budget", arguments)


def lines(draft):
    return {a["category"]: a for a in draft["category_allocations"]}


def money_sum(values):
    return sum((D(v) for v in values), D("0.00"))


async def plan_rows(connection, user):
    result = await connection.execute(
        text(
            "SELECT date, category, planned_amount FROM daily_plan "
            "WHERE user_id = :u ORDER BY date, category"
        ),
        {"u": user.id},
    )
    return [tuple(r) for r in result.all()]


async def onboard_sofia_commuter(mcp, seed):
    """A: Sofia, no car, takes the bus, rents, eats out sometimes."""
    user, token, m = await newcomer(mcp, seed)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 1500,
            "currency": "EUR",
            "timezone": TZ,
            "household_size": 1,
            "monthly_savings_target": 100,
            "country": "BG",
            "income_regularity": "regular",
            "pay_frequency": "monthly",
            "pay_days": [25],
        },
        meta=SOFIA_HINT,
    )
    await recurring(m, token, "Rent", 600, "rent", 1)
    await recurring(m, token, "Phone", 15, "utilities", 20)
    await call(
        m,
        token,
        "save_spending_patterns",
        {
            "patterns": [
                {
                    "line": "Groceries",
                    "kind": "planned",
                    "frequency": "weekly",
                    "weekdays": ["saturday"],
                },
                {"line": "dining out", "kind": "flexible"},
            ]
        },
    )
    status = await call(
        m,
        token,
        "update_financial_profile",
        {"setup_answers": [{"topic": "everyday_spending", "answer": "described"}]},
    )
    own = [
        {"label": "Groceries", "amount": 250, "replaces": ["groceries"]},
        {"label": "Public transport", "amount": 26, "replaces": ["transport public"]},
    ]
    return user, token, m, status, own


async def onboard_varna_family(mcp, seed):
    """B: Varna, drives, owns the flat (mortgage), family of three, variable
    income."""
    user, token, m = await newcomer(mcp, seed)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 3000,
            "currency": "EUR",
            "timezone": TZ,
            "household_size": 3,
            "monthly_savings_target": 300,
            "country": "BG",
            "income_regularity": "variable",
            "minimum_monthly_income": 2400,
        },
    )
    await recurring(m, token, "Mortgage", 450, "mortgage", 5)
    await recurring(m, token, "Electricity and water", 120, "utilities", 15)
    await call(
        m,
        token,
        "save_spending_patterns",
        {
            "patterns": [
                {"line": "Fuel", "kind": "planned", "frequency": "weekly"},
                {
                    "line": "Groceries",
                    "kind": "planned",
                    "frequency": "weekly",
                    "weekdays": ["saturday"],
                },
                {"line": "clothing", "kind": "flexible"},
                {"line": "transport public", "kind": "not_applicable"},
            ]
        },
    )
    status = await call(
        m,
        token,
        "update_financial_profile",
        {
            "setup_answers": [
                {"topic": "everyday_spending", "answer": "described"},
                {"topic": "irregular_expenses", "answer": "none"},
            ]
        },
    )
    own = [
        {"label": "Fuel", "amount": 200, "replaces": ["transport gas"]},
        {"label": "Groceries", "amount": 500, "replaces": ["groceries"]},
        {"label": "Kids activities", "amount": 80},
    ]
    return user, token, m, status, own


# --- acceptance: two people, two budgets ------------------------------------------


async def test_two_different_people_get_two_different_budgets(mcp, seed, connection):
    a_user, a_token, a_m, a_status, a_own = await onboard_sofia_commuter(mcp, seed)
    b_user, b_token, b_m, b_status, b_own = await onboard_varna_family(mcp, seed)

    for status in (a_status, b_status):
        assert status["onboarding"]["stage"] == "ready_for_personalized_budget"
        assert status["onboarding"]["budget_readiness"] == "personalized"
    # Optional questions stay open until answered: A never said whether they
    # have irregular expenses; B said none.
    assert a_status["onboarding"]["next_questions"] == ["irregular_expenses"]
    assert b_status["onboarding"]["next_questions"] == []

    a = await preview(a_m, a_token, budget_lines=a_own)
    b = await preview(b_m, b_token, budget_lines=b_own)
    print("A", a["category_allocations"], a["not_included"], a["unallocated"])
    print("B", b["category_allocations"], b["not_included"], b["unallocated"])

    for draft in (a, b):
        assert draft["personalization"] == {
            "level": "personalized",
            "regular_payments": "answered",
            "everyday_spending": "described",
        }
        # Every euro is somewhere: bills + savings + lines + unallocated.
        assert money_sum(
            [draft["fixed_obligations_total"], draft["savings_allocation"]]
            + [x["amount"] for x in draft["category_allocations"]]
            + [draft["unallocated"]]
        ) == D(draft["stated_monthly_income"])
        # A personalized plan budgets only confirmed lines.
        assert {x["line_status"] for x in draft["category_allocations"]} == {
            "user_confirmed"
        }
        assert not any("default draft" in w for w in draft["warnings"])

    a_lines, b_lines = lines(a), lines(b)
    assert set(a_lines) == {"my:Groceries", "my:Public transport", "dining out"}
    assert set(b_lines) == {"my:Fuel", "my:Groceries", "my:Kids activities", "clothing"}
    # A has no car: no fuel line by assumption, and MITA says what it left out.
    assert "transport gas" not in a_lines and not any(
        x["category_label"] == "Fuel" for x in a["category_allocations"]
    )
    assert "transport gas" in {x["category"] for x in a["not_included"]}
    # B owns the flat: no rent anywhere, only their mortgage.
    for draft in (a, b):
        assert "rent" not in lines(draft)
    assert {o["category"] for o in b["fixed_obligations"]} == {"mortgage", "utilities"}
    assert {o["category"] for o in a["fixed_obligations"]} == {"rent", "utilities"}
    # Exact figures, by hand (MITA's default shares at this income: food 13 %
    # — 60 % groceries, 40 % dining out —, transport 15 % — 70 % public, 30 %
    # fuel —, entertainment 6 %, misc 8 % — 60 % clothing, 40 % hobbies —,
    # healthcare 7 % — 60 % insurance, 40 % out of pocket).
    # A: 1500 − bills 615 − own lines 276 − savings 100 = 509 for MITA's lines;
    # dining out 0.4 × 0.13 × 1500 = 78.00; unallocated 509 − 78 = 431.00.
    assert a_lines["dining out"]["amount"] == "78.00"
    assert a["unallocated"] == "431.00"
    assert {x["category"]: x["would_suggest"] for x in a["not_included"]} == {
        "entertainment events": "90.00",
        "clothing": "72.00",
        "transport gas": "67.50",
        "insurance medical": "63.00",
        "hobbies": "48.00",
        "out of pocket medical": "42.00",
    }
    # Nothing was scaled, so all 382.50 stays unallocated (still spendable).
    assert a["not_included_money"] == {
        "total": "382.50",
        "to_other_lines": [],
        "unallocated": "382.50",
    }
    # B: 3000 − 570 − 780 − 300 = 1350; clothing 0.6 × 0.08 × 3000 = 144.00.
    assert b_lines["clothing"]["amount"] == "144.00"
    assert b["unallocated"] == "1206.00"
    assert b["plan_total"] == "1794.00"  # 570 + 300 + 780 + 144
    # The user's amounts exactly; B's public transport stays excluded.
    assert a_lines["my:Public transport"]["amount"] == "26.00"
    assert b_lines["my:Fuel"]["amount"] == "200.00"
    assert [x["category"] for x in b["not_applicable_lines"]] == ["transport public"]
    # Fuel "about once a week" gets proposed dates; groceries real Saturdays.
    fuel = b_lines["my:Fuel"]
    assert fuel["spending_type"] == "planned"
    assert fuel["purchase_dates_stated"] is False
    assert {p["proposed"] for p in fuel["purchases"]} == {True}
    groceries = b_lines["my:Groceries"]
    assert [p["date"] for p in groceries["purchases"]] == [
        "2026-11-07",
        "2026-11-14",
        "2026-11-21",
        "2026-11-28",
    ]
    assert money_sum(p["amount"] for p in groceries["purchases"]) == D("500.00")

    # Different budgets, not just different numbers.
    assert a["plan_total"] != b["plan_total"]
    assert set(a_lines) != set(b_lines)
    # B's income varies: the plan against a month at the stated minimum.
    assert a["variable_income"] is None
    vi = b["variable_income"]
    assert vi["planned_on"] == "3000.00"
    assert vi["minimum_monthly_income"] == "2400.00"
    assert D(vi["committed"]) == D("450.00") + D("120.00") + D("300.00") + D("780.00")
    assert D(vi["shortfall_at_minimum"]) == max(
        D("0.00"), D(b["plan_total"]) - D("2400.00")
    )
    assert vi["committed_exceeds_minimum"] is False

    # Nothing was saved: previews and setup answers write no plan rows.
    assert await plan_rows(connection, a_user) == []
    assert await plan_rows(connection, b_user) == []


async def test_without_the_answer_mita_lines_are_suggestions_not_choices(mcp, seed):
    user, token, m = await newcomer(mcp, seed)
    await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 1500,
            "currency": "EUR",
            "timezone": TZ,
            "monthly_savings_target": 100,
        },
    )
    await recurring(m, token, "Rent", 600, "rent", 1)
    before = await preview(m, token)
    assert before["personalization"]["level"] == "preliminary"
    assert before["personalization"]["everyday_spending"] == "unknown"
    assert before["not_included"] == []
    suggested = lines(before)
    # 2.7.0 behaviour: every MITA line, each marked as MITA's suggestion.
    assert "transport gas" in suggested and "insurance medical" in suggested
    assert {x["line_status"] for x in before["category_allocations"]} == {
        "mita_suggested"
    }
    assert any(a.startswith("Preliminary:") for a in before["assumptions"])

    # "I don't drive, I take the bus and I eat out" + "that's what I spend on".
    await call(
        m,
        token,
        "save_spending_patterns",
        {
            "patterns": [
                {"line": "transport public", "kind": "flexible"},
                {"line": "dining out", "kind": "flexible"},
                {"line": "groceries", "kind": "flexible"},
            ]
        },
    )
    await call(
        m,
        token,
        "update_financial_profile",
        {"setup_answers": [{"topic": "everyday_spending", "answer": "described"}]},
    )
    after = await preview(m, token)
    assert after["personalization"]["level"] == "personalized"
    assert set(lines(after)) == {"transport public", "dining out", "groceries"}
    left_out = {x["category"]: D(x["would_suggest"]) for x in after["not_included"]}
    assert "transport gas" in left_out
    for code, amount in left_out.items():
        assert amount == D(suggested[code]["amount"])  # what MITA had suggested
    # The money MITA did not earmark stays spendable: conserved to the cent.
    money = after["not_included_money"]
    assert D(money["total"]) == sum(left_out.values())
    assert D(money["total"]) == money_sum(
        [x["amount"] for x in money["to_other_lines"]] + [money["unallocated"]]
    )
    assert D(after["unallocated"]) - D(before["unallocated"]) == D(money["unallocated"])
    # Same daily figure: unallocated money is still spending money.
    assert after["daily_flexible_average"] == before["daily_flexible_average"]


async def test_none_and_skipped_are_answers_and_never_asked_is_not(mcp, seed):
    user, token, m = await newcomer(mcp, seed)
    status = await call(m, token, "get_setup_status")
    assert status["onboarding"]["stage"] == "not_started"
    assert status["onboarding"]["budget_readiness"] == "not_ready"

    result = await call(
        m,
        token,
        "update_financial_profile",
        {"monthly_net_income": 2000, "currency": "EUR", "timezone": TZ},
    )
    assert result["onboarding"]["stage"] == "basic_profile_completed"
    assert result["suggested_next_step"] == "ask_about_obligations"
    assert result["onboarding"]["next_questions"][:1] == ["region"]
    assert "regular_payments" in result["onboarding"]["next_questions"]

    draft = await preview(m, token)
    assert any("default draft" in w for w in draft["warnings"])

    result = await call(
        m,
        token,
        "update_financial_profile",
        {"setup_answers": [{"topic": "regular_payments", "answer": "none"}]},
    )
    assert result["updated_fields"] == ["setup_answers"]
    topics = {t["topic"]: t["state"] for t in result["onboarding"]["topics"]}
    assert topics["regular_payments"] == "none"
    assert result["suggested_next_step"] == "describe_spending"
    draft = await preview(m, token)
    assert not any("default draft" in w for w in draft["warnings"])
    assert "The user said they have no regular payments." in draft["assumptions"]
    assert draft["personalization"]["regular_payments"] == "none"

    result = await call(
        m,
        token,
        "update_financial_profile",
        {
            "setup_answers": [
                {"topic": "everyday_spending", "answer": "skipped"},
                {"topic": "region", "answer": "skipped"},
                {"topic": "income_schedule", "answer": "skipped"},
            ]
        },
    )
    assert result["onboarding"]["stage"] == "optional_questions_skipped"
    assert result["onboarding"]["budget_readiness"] == "preliminary"
    assert result["suggested_next_step"] == "build_budget"
    assert result["onboarding"]["next_questions"] == ["irregular_expenses"]
    draft = await preview(m, token)
    assert draft["personalization"]["level"] == "preliminary"
    assert draft["personalization"]["everyday_spending"] == "skipped"

    # A saved payment outranks an earlier "none"; "none" cannot be said over one.
    await recurring(m, token, "Phone", 15, "utilities", 20)
    status = await call(m, token, "get_setup_status")
    topics = {t["topic"]: t["state"] for t in status["onboarding"]["topics"]}
    assert topics["regular_payments"] == "answered"
    error = await error_of(
        m,
        token,
        "update_financial_profile",
        {"setup_answers": [{"topic": "regular_payments", "answer": "none"}]},
    )
    assert "saved regular payment" in error["message"]


async def test_answers_are_validated(mcp, seed):
    user, token, m = await newcomer(mcp, seed)
    cases = [
        ({"setup_answers": [{"topic": "regular_payments", "answer": "described"}]}),
        ({"setup_answers": [{"topic": "region", "answer": "none"}]}),
        (
            {
                "setup_answers": [
                    {"topic": "everyday_spending", "answer": "described"},
                    {"topic": "everyday_spending", "answer": "skipped"},
                ]
            }
        ),
        (
            {
                "country": "BG",
                "setup_answers": [{"topic": "region", "answer": "skipped"}],
            }
        ),
        ({"country": "ZZ"}),
        ({"country": "XX"}),
        ({"minimum_monthly_income": 500}),
        ({"income_regularity": "regular", "minimum_monthly_income": 500}),
        ({"pay_days": [25]}),
        ({"pay_frequency": "weekly", "pay_days": [1]}),
        ({"pay_frequency": "twice_monthly", "pay_days": [15]}),
    ]
    for arguments in cases:
        await error_of(m, token, "update_financial_profile", arguments)
    # An unknown field (a city, say) is refused by the schema itself.
    result = await m.call(token, "update_financial_profile", {"city": "Sofia"})
    assert result.is_error
    status = await call(m, token, "get_setup_status")
    assert status["onboarding"]["stage"] == "not_started"  # nothing was written


async def test_income_schedule_is_kept_as_stated(mcp, seed, connection):
    user, token, m = await newcomer(mcp, seed)
    result = await call(
        m,
        token,
        "update_financial_profile",
        {
            "monthly_net_income": 2000,
            "income_regularity": "variable",
            "minimum_monthly_income": 1200,
            "pay_frequency": "twice_monthly",
            "pay_days": [15, 1],
        },
    )
    assert result["profile"]["income_regularity"] == "variable"
    assert result["profile"]["minimum_monthly_income"] == "1200.00"
    assert result["profile"]["pay_frequency"] == "twice_monthly"
    assert result["profile"]["pay_days"] == [1, 15]
    topics = {t["topic"]: t["state"] for t in result["onboarding"]["topics"]}
    assert topics["income_schedule"] == "answered"
    # Regular income has no minimum: it is cleared, never left behind.
    result = await call(
        m,
        token,
        "update_financial_profile",
        {"income_regularity": "regular", "pay_frequency": "monthly", "pay_days": [25]},
    )
    assert result["profile"]["minimum_monthly_income"] is None
    assert result["profile"]["pay_days"] == [25]
    assert set(result["updated_fields"]) == {
        "income_regularity",
        "minimum_monthly_income",
        "pay_frequency",
        "pay_days",
    }
    row = (
        await connection.execute(
            text(
                "SELECT income_regularity, pay_frequency, pay_days, "
                "minimum_monthly_income FROM mcp_user_profiles WHERE user_id = :u"
            ),
            {"u": user.id},
        )
    ).one()
    assert tuple(row) == ("regular", "monthly", [25], None)


# --- region: the user's answer, never ChatGPT's location by itself -----------------


async def test_chatgpt_location_is_a_question_and_the_answer_is_stored(
    mcp, seed, connection
):
    user, token, m = await newcomer(mcp, seed)
    status = await call(m, token, "get_setup_status", meta=SOFIA_HINT)
    assert status["region"] == {
        "country": None,
        "country_name": None,
        "source": None,
        "regional_context": True,
        "suggestion": {
            "country": "BG",
            "country_name": "Bulgaria",
            "source": "chatgpt_approximate_location",
        },
    }
    assert any("approximate location in Bulgaria" in n for n in status["notes"])
    text_out = repr(status)
    for leaked in ("42.69", "23.32", "Sofia City", "latitude", "longitude"):
        assert leaked not in text_out  # nothing but the country is used
    # Nothing is stored by reading.
    row = (
        await connection.execute(
            text("SELECT country FROM users WHERE id = :u"), {"u": user.id}
        )
    ).one()
    assert row[0] == "ZZ"

    # The user confirms the suggested country.
    result = await call(
        m, token, "update_financial_profile", {"country": "bg"}, meta=SOFIA_HINT
    )
    assert result["updated_fields"] == ["country"]
    assert result["region"]["country"] == "BG"
    assert result["region"]["source"] == "chatgpt_location_confirmed"
    assert result["region"]["suggestion"] is None
    assert result["profile"]["country"] == "BG"

    # Travelling: ChatGPT now says Greece, the user still lives in Bulgaria.
    athens = {"openai/userLocation": {"country": "GR", "city": "Athens"}}
    status = await call(m, token, "get_setup_status", meta=athens)
    assert status["region"]["country"] == "BG"
    assert status["region"]["suggestion"] is None

    # Moving to Germany: stated, not the hint; nothing else changes.
    await call(
        m,
        token,
        "update_financial_profile",
        {"monthly_net_income": 2000, "currency": "EUR", "timezone": TZ},
    )
    result = await call(
        m, token, "update_financial_profile", {"country": "DE"}, meta=athens
    )
    assert result["region"]["source"] == "stated"
    assert result["profile"]["currency"] == "EUR"
    assert any(
        "currency, recorded expenses and saved budgets" in n for n in result["notes"]
    )

    # Turning regional statistics off, then preferring not to say at all.
    result = await call(
        m, token, "update_financial_profile", {"regional_comparisons": False}
    )
    assert result["region"]["regional_context"] is False
    result = await call(
        m,
        token,
        "update_financial_profile",
        {"setup_answers": [{"topic": "region", "answer": "skipped"}]},
        meta=athens,
    )
    assert result["region"]["country"] is None
    assert (
        result["region"]["suggestion"] is None
        or result["region"]["suggestion"]["country"] == "GR"
    )
    stored = (
        await connection.execute(
            text(
                "SELECT u.country, p.country_source, p.country_confirmed_at "
                "FROM users u JOIN mcp_user_profiles p ON p.user_id = u.id "
                "WHERE u.id = :u"
            ),
            {"u": user.id},
        )
    ).one()
    assert tuple(stored) == ("ZZ", None, None)
    topics = {t["topic"]: t["state"] for t in result["onboarding"]["topics"]}
    assert topics["region"] == "skipped"


async def test_a_malformed_or_absent_hint_is_ignored(mcp, seed):
    user, token, m = await newcomer(mcp, seed)
    for meta in (
        None,
        {"openai/userLocation": "BG"},
        {"openai/userLocation": {"country": "Atlantis"}},
        {"openai/userLocation": {"country": "ZZ"}},
        {"openai/userLocation": {"latitude": "42.7", "longitude": "23.3"}},
    ):
        status = await call(m, token, "get_setup_status", meta=meta)
        assert status["region"]["suggestion"] is None
    named = {"openai/userLocation": {"country": "Bulgaria"}}
    status = await call(m, token, "get_setup_status", meta=named)
    assert status["region"]["suggestion"]["country"] == "BG"


async def test_region_text_is_truthful(mcp, seed):
    user, token, m = await newcomer(mcp, seed)
    await call(
        m,
        token,
        "update_financial_profile",
        {"monthly_net_income": 2000, "currency": "EUR", "timezone": TZ},
    )
    draft = await preview(m, token)
    assert any("No region is stated" in a for a in draft["assumptions"])
    await call(m, token, "update_financial_profile", {"country": "BG"})
    draft = await preview(m, token)
    assert any(
        "MITA has no allocation rules specific to BG" in a for a in draft["assumptions"]
    )


# --- existing users: never forced back through setup ------------------------------


async def test_an_existing_user_is_not_sent_back_through_setup(mcp, seed, connection):
    """The owner-like account of 2.7.0: income, savings, three saved payments,
    a saved November with own lines, no patterns, no 2.8 answers."""
    m = mcp.at(at(4))
    user = await seed.user(income="2000.00", currency="EUR", tz=TZ, country="ZZ")
    await seed.profile(
        user,
        household_size=1,
        income_confirmed_at=at(1),
        currency_confirmed_at=at(1),
        timezone_confirmed_at=at(1),
        savings_confirmed_at=at(1),
    )
    token = m.token(user)
    await call(m, token, "update_financial_profile", {"monthly_savings_target": 500})
    await recurring(m, token, "Phone", 30, "utilities", 10)
    await recurring(m, token, "Car loan", 270, "transportation", 15)
    draft = await preview(
        m,
        token,
        budget_lines=[{"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}],
    )
    assert draft["personalization"]["level"] == "preliminary"
    saved = await call(
        m, token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
    )
    assert saved["status"] == "saved"
    rows_before = await plan_rows(connection, user)

    status = await call(m, token, "get_setup_status", meta=SOFIA_HINT)
    assert status["onboarding"]["stage"] == "established"
    assert status["onboarding"]["next_questions"] == []
    assert "everyday_spending" in status["onboarding"]["optional_questions"]
    assert status["suggested_next_step"] in ("record_expenses", "ready")
    assert not any("approximate location" in n for n in status["notes"])
    assert any("returning user" in n for n in status["notes"])

    # The same preview again: the 2.7.0 computation, unchanged.
    again = await preview(
        m,
        token,
        budget_lines=[{"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}],
    )
    assert again["category_allocations"] == draft["category_allocations"]
    assert again["unallocated"] == draft["unallocated"]
    assert again["not_included"] == []

    # Optional answers never touch the saved month.
    result = await call(
        m,
        token,
        "update_financial_profile",
        {
            "country": "BG",
            "income_regularity": "regular",
            "setup_answers": [{"topic": "everyday_spending", "answer": "described"}],
        },
    )
    assert any("saved plan for this month is unchanged" in n for n in result["notes"])
    assert await plan_rows(connection, user) == rows_before
    # Personalizing shows in the next preview only; saving it needs a new yes.
    personal = await preview(
        m,
        token,
        budget_lines=[{"label": "Fuel", "amount": 200, "replaces": ["transport gas"]}],
    )
    assert personal["personalization"]["level"] == "personalized"
    assert set(lines(personal)) == {"my:Fuel"}
    stale = await m.call(
        token, "save_monthly_budget", {"draft_token": draft["draft_token"]}
    )
    assert stale.is_error  # the answers changed since that preview
    assert await plan_rows(connection, user) == rows_before


async def test_setup_survives_a_new_connection_and_stays_per_user(mcp, seed):
    a_user, a_token, a_m, _status, _own = await onboard_sofia_commuter(mcp, seed)
    other, other_token, other_m = await newcomer(mcp, seed)
    fresh = a_m.token(a_user)  # a new ChatGPT connection, same account
    status = await call(a_m, fresh, "get_setup_status")
    assert status["onboarding"]["stage"] == "ready_for_personalized_budget"
    assert status["region"]["country"] == "BG"
    assert status["known"]["pay_days"] == [25]
    # Another account sees none of it.
    theirs = await call(other_m, other_token, "get_setup_status")
    assert theirs["onboarding"]["stage"] == "not_started"
    assert theirs["region"]["country"] is None
    assert theirs["known"]["pay_days"] == []


async def test_the_database_refuses_what_the_tool_refuses(seed, connection):
    """0043's checks hold without the tool: a minimum income needs variable
    income (a CHECK passes on NULL, so the constraint spells IS NOT NULL), a
    country source needs its confirmation time, an answer is one of three."""
    user = await seed.user()
    statements = [
        "INSERT INTO mcp_user_profiles (user_id, usage_analytics_enabled, "
        "created_at, updated_at, minimum_monthly_income) "
        "VALUES (:u, false, now(), now(), 5)",
        "INSERT INTO mcp_user_profiles (user_id, usage_analytics_enabled, "
        "created_at, updated_at, income_regularity, minimum_monthly_income) "
        "VALUES (:u, false, now(), now(), 'regular', 5)",
        "INSERT INTO mcp_user_profiles (user_id, usage_analytics_enabled, "
        "created_at, updated_at, country_source) "
        "VALUES (:u, false, now(), now(), 'stated')",
        "INSERT INTO mcp_setup_answers VALUES (:u, 'regular_payments', 'maybe', now())",
        "INSERT INTO mcp_setup_answers VALUES (:u, 'mood', 'none', now())",
    ]
    for statement in statements:
        nested = await connection.begin_nested()
        with pytest.raises(IntegrityError):
            await connection.execute(text(statement), {"u": user.id})
        await nested.rollback()
    nested = await connection.begin_nested()
    await connection.execute(
        text(
            "INSERT INTO mcp_user_profiles (user_id, usage_analytics_enabled, "
            "created_at, updated_at, income_regularity, minimum_monthly_income) "
            "VALUES (:u, false, now(), now(), 'variable', 0)"
        ),
        {"u": user.id},
    )
    await nested.rollback()
