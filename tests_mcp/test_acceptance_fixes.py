"""Regressions for what the owner's real ChatGPT run (2026-10-13…18) surfaced.

A. The app was described as "Read-only access to my MITA budget…" — the v2 app
   writes. No published surface may describe the whole app as read-only.
B. After creating a goal, ChatGPT offered "set €400 per month toward your
   Emergency Fund" — no MITA tool can. Metadata and results must say so.
D. A mixed receipt (food, beer, gin, brandy) was stored as all groceries — the
   category hint said "groceries for a supermarket". Each line has its own
   category; MITA has no alcohol category (documented, not invented).
E. A detailed budget was built before rent was known — ask about regular
   payments first, and label a preview without them a default draft.
F. Drafts stay savable for 2 hours (integrity never depended on the TTL).
G. "Show me Anna's transactions" searched the user's own expenses — fine, but
   it must never read as access to Anna's data.
"""

import json
import re
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from app.mcp import MCP_SERVER_DESCRIPTION
from app.mcp.auth.scopes import SCOPE_DESCRIPTIONS
from app.mcp.queries import budget_draft
from app.mcp.serializers import MERCHANT_FILTER_NOTE
from app.mcp.server import INSTRUCTIONS
from app.mcp.tools import READ_TOOLS, WRITE_TOOLS
from app.mcp.tools.budget import NO_OBLIGATIONS_WARNING
from app.mcp.tools.common import READ_ONLY_DISCLAIMER
from app.mcp.tools.goals import GOAL_LIMITS
from app.mcp.tools.inputs import CATEGORY_HELP
from tests_mcp.conftest import mcp_client, started, structured
from tests_mcp.test_budget_plan import NOW, seed_ana
from tests_mcp.test_registration import _login_url

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = json.loads((ROOT / "plugin/mita/plugin.template.json").read_text())
SKILL = (ROOT / "plugin/mita/skills/setup/SKILL.md").read_text()
WHOLE_APP_READ_ONLY = re.compile(r"read[- ]only", re.IGNORECASE)


@pytest.fixture
def m(mcp):
    return mcp.at(NOW)


@pytest.fixture
async def ana(m, seed):
    return await seed_ana(m, seed)


def key() -> str:
    return uuid.uuid4().hex


# --- A: no whole-app "read-only" wording -------------------------------------


def _listing_texts():
    interface = PLUGIN["extensions"]["com.openai"]["interface"]
    yield "description", PLUGIN["description"]
    yield "shortDescription", interface["shortDescription"]
    yield "longDescription", interface["longDescription"]
    for item in interface["capabilities"]:
        yield "capability", item
    yield "release_notes", PLUGIN["extensions"]["com.openai"]["publication"][
        "release_notes"
    ]


def test_no_published_surface_calls_the_app_read_only():
    surfaces = list(_listing_texts()) + [
        ("server instructions", INSTRUCTIONS),
        ("server description", MCP_SERVER_DESCRIPTION),
        ("setup skill", SKILL),
    ]
    surfaces += [(f"scope {s}", d) for s, d in SCOPE_DESCRIPTIONS.items()]
    for where, value in surfaces:
        assert not WHOLE_APP_READ_ONLY.search(value), where


def test_server_description_is_the_listing_description():
    assert MCP_SERVER_DESCRIPTION == PLUGIN["description"]
    assert "record and correct expenses" in MCP_SERVER_DESCRIPTION


async def test_initialize_carries_the_description(mcp, seed):
    user = await seed.user()
    service = mcp._build()
    async with started(service):
        async with mcp_client(service, mcp.token(user)) as client:
            server = client.server_info
    assert server.description == MCP_SERVER_DESCRIPTION
    assert server.title == "MITA Finance"


async def test_tool_level_read_only_statements_stay_on_read_tools(mcp, seed):
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    assert set(tools) == set(READ_TOOLS) | set(WRITE_TOOLS)
    for name in READ_TOOLS:
        assert READ_ONLY_DISCLAIMER in tools[name].description, name
    for name in WRITE_TOOLS:
        assert not WHOLE_APP_READ_ONLY.search(tools[name].description), name


async def test_consent_page_lists_the_write_permissions(mcp):
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        page = (await http.get(login_url)).text
    assert not WHOLE_APP_READ_ONLY.search(page)
    assert "record and correct expenses" in page


# --- B: goals cannot be changed after creation --------------------------------


async def test_a_goal_without_a_date_says_nothing_is_set_aside_and_why(m, ana):
    token = m.token(ana)
    request = {
        "title": "Emergency Fund",
        "target_amount": 3000,
        "idempotency_key": key(),
    }
    goal = structured(await m.call(token, "create_savings_goal", request))
    assert goal["status"] == "created"
    assert goal["reserved_in_budget_plan"] is False
    assert goal["required_monthly_contribution"] is None
    assert any(
        "set nothing aside" in n and GOAL_LIMITS in n for n in goal["notes"]
    ), goal["notes"]
    replay = structured(await m.call(token, "create_savings_goal", request))
    assert replay["status"] == "already_created"
    assert any(GOAL_LIMITS in n for n in replay["notes"])


async def test_no_tool_offers_to_change_a_goal_or_set_a_contribution(mcp, seed):
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    for tool in tools.values():
        properties = tool.input_schema.get("properties", {})
        assert not any("contribution" in p for p in properties), tool.name
        assert not re.search(r"goal", tool.name) or tool.name in {
            "get_goals",
            "create_savings_goal",
        }, tool.name
    for name in ("create_savings_goal", "get_goals"):
        assert GOAL_LIMITS in tools[name].description, name
    assert "no MITA tool sets or changes a monthly contribution" in GOAL_LIMITS
    reserved = tools["create_savings_goal"].output_schema["properties"][
        "reserved_in_budget_plan"
    ]["description"]
    assert "Always false for a goal without a target date" in reserved


# --- D: receipts categorize per line -------------------------------------------


async def test_a_mixed_receipt_keeps_each_lines_category(m, ana, connection):
    token = m.token(ana)
    recorded = structured(
        await m.call(
            token,
            "add_transactions",
            {
                "expenses": [
                    {
                        "amount": "2.40",
                        "category": "groceries",
                        "merchant": "My Market",
                    },
                    {"amount": "2.99", "category": "shopping", "merchant": "My Market"},
                    {
                        "amount": "4.50",
                        "category": "healthcare",
                        "merchant": "My Market",
                    },
                ],
                "entry_method": "receipt_image",
                "idempotency_key": key(),
            },
        )
    )
    assert [t["category"] for t in recorded["transactions"]] == [
        "groceries",
        "shopping",
        "healthcare",
    ]
    rows = await connection.execute(
        text(
            "SELECT category, amount FROM transactions WHERE user_id = :u "
            "AND deleted_at IS NULL ORDER BY amount"
        ),
        {"u": ana.id},
    )
    assert [(c, str(a)) for c, a in rows.all()] == [
        ("groceries", "2.40"),
        ("shopping", "2.99"),
        ("healthcare", "4.50"),
    ]


async def test_category_guidance_is_by_item_not_by_shop(mcp, seed):
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    many = tools["add_transactions"].description
    assert "Every item has its own category" in many
    assert "not of the shop" in many
    assert "MITA has no alcohol or tobacco category" in many
    assert "Choose by what was bought" in CATEGORY_HELP
    assert "groceries for a supermarket" not in CATEGORY_HELP


# --- E: ask about regular payments before a first budget ------------------------


async def test_obligations_come_before_a_first_budget_but_never_block_it(mcp, seed):
    user = await seed.user(income="0", onboarded=False, name=None, country="ZZ")
    h = mcp.at(NOW)
    token = h.token(user)
    profile = structured(
        await h.call(
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
    assert profile["suggested_next_step"] == "ask_about_obligations"
    status = structured(await h.call(token, "get_setup_status"))
    assert status["suggested_next_step"] == "ask_about_obligations"
    assert any("No regular payments are saved yet" in n for n in status["notes"])

    default = structured(await h.call(token, "preview_monthly_budget", {}))
    assert NO_OBLIGATIONS_WARNING in default["warnings"]  # still allowed, labelled

    structured(
        await h.call(
            token,
            "add_recurring_expense",
            {
                "name": "Rent",
                "amount": 700,
                "category": "rent",
                "recurrence": "monthly",
                "day_of_month": 1,
                "idempotency_key": key(),
            },
        )
    )
    status = structured(await h.call(token, "get_setup_status"))
    assert status["suggested_next_step"] == "build_budget"
    with_rent = structured(await h.call(token, "preview_monthly_budget", {}))
    assert NO_OBLIGATIONS_WARNING not in with_rent["warnings"]


# --- F: draft lifetime ----------------------------------------------------------


async def test_a_reviewed_draft_is_still_savable_after_a_long_pause(mcp, ana):
    assert budget_draft.DRAFT_TTL == timedelta(hours=2)
    first = mcp.at(NOW)
    draft = structured(await first.call(first.token(ana), "preview_monthly_budget", {}))
    later = mcp.at(NOW + timedelta(minutes=90))
    saved = structured(
        await later.call(
            later.token(ana),
            "save_monthly_budget",
            {"draft_token": draft["draft_token"]},
        )
    )
    assert saved["status"] == "saved" and saved["plan_total"] == draft["plan_total"]


async def test_the_draft_token_schema_states_the_real_lifetime(mcp, seed):
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    schema = json.dumps(tools["preview_monthly_budget"].output_schema)
    hours = int(budget_draft.DRAFT_TTL.total_seconds() // 3600)
    assert f"expires after {hours} hours" in schema


# --- G: another person's data is never in scope ---------------------------------


async def test_a_name_filter_searches_only_the_users_own_expenses(m, ana, seed):
    anna = await seed.user(tz="Europe/Sofia", currency="EUR")
    await seed.txn(anna, "99.00", "dining", NOW - timedelta(hours=1), merchant="Anna")
    token = m.token(ana)
    nothing = structured(await m.call(token, "list_transactions", {"merchant": "Anna"}))
    assert nothing["matching_count"] == 0 and nothing["transactions"] == []
    assert MERCHANT_FILTER_NOTE in nothing["notes"]

    structured(
        await m.call(
            token,
            "add_transaction",
            {
                "amount": "40.00",
                "category": "childcare",
                "merchant": "Anna (babysitter)",
                "idempotency_key": key(),
            },
        )
    )
    mine = structured(await m.call(token, "list_transactions", {"merchant": "anna"}))
    assert [(t["merchant"], t["amount"]) for t in mine["transactions"]] == [
        ("Anna (babysitter)", "40.00")
    ]
    assert MERCHANT_FILTER_NOTE in mine["notes"]
    plain = structured(await m.call(token, "list_transactions", {}))
    assert MERCHANT_FILTER_NOTE not in plain["notes"]


async def test_list_metadata_says_a_name_is_not_another_account(mcp, seed):
    user = await seed.user()
    tools = {t.name: t for t in await mcp.list_tools(mcp.token(user))}
    description = tools["list_transactions"].description
    assert "searches only THIS user's own expenses" in description
    assert "never that person's data" in description
