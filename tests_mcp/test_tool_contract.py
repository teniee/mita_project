"""Every published tool meets OpenAI's and MITA's contract.

Fails if a tool is added without an entry in ``EXPECTED`` (its exact
read/destructive/idempotent semantics), with an input that could select whose
data to read, without a description that states its limits, without an output
schema, or with a name that suggests moving money.
"""

import re

import pytest

from app.mcp.analytics import TOOL_FEATURES
from app.mcp.auth.scopes import (
    FEEDBACK_WRITE,
    FINANCE_READ,
    FINANCE_WRITE,
    PROFILE_READ,
    PROFILE_WRITE,
)
from app.mcp.tools import PUBLISHED_TOOLS, READ_TOOLS, WRITE_TOOLS

IDENTITY_FIELD = re.compile(
    r"(^|_)(user|uid|account|owner|email|customer|member|profile_id|person|tenant|principal|sub)(_|$|id)",
    re.IGNORECASE,
)
# Field names that would let the model pass conversation context "just in case".
CONTEXT_FIELD = re.compile(
    r"(history|transcript|conversation|messages|context|prompt)", re.IGNORECASE
)
# OpenAI: no raw location fields in input schemas.
LOCATION_FIELD = re.compile(
    r"(latitude|longitude|^lat$|^lng$|address|city|postcode|zip|gps|location)",
    re.IGNORECASE,
)

READ = "read"
# tool -> (kind, destructive, idempotent, scope, needs_idempotency_key)
EXPECTED = {
    "get_profile": (READ, False, True, PROFILE_READ, False),
    "get_setup_status": (READ, False, True, PROFILE_READ, False),
    "get_financial_summary": (READ, False, True, FINANCE_READ, False),
    "list_transactions": (READ, False, True, FINANCE_READ, False),
    "get_spending_breakdown": (READ, False, True, FINANCE_READ, False),
    "get_budget_status": (READ, False, True, FINANCE_READ, False),
    "get_budget_forecast": (READ, False, True, FINANCE_READ, False),
    "get_recurring_expenses": (READ, False, True, FINANCE_READ, False),
    "get_goals": (READ, False, True, FINANCE_READ, False),
    "get_spending_history": (READ, False, True, FINANCE_READ, False),
    "get_financial_climate": (READ, False, True, FINANCE_READ, False),
    "preview_monthly_budget": (READ, False, True, FINANCE_READ, False),
    # Overwrites stated values (OpenAI: "delete or overwrite user data").
    "update_financial_profile": ("write", True, True, FINANCE_WRITE, False),
    # Additive; idempotent only because the arguments carry a key.
    "add_transaction": ("write", False, True, FINANCE_WRITE, True),
    "add_transactions": ("write", False, True, FINANCE_WRITE, True),
    "update_transaction": ("write", True, True, FINANCE_WRITE, False),
    "delete_transaction": ("write", True, True, FINANCE_WRITE, False),
    # May replace an existing plan for the month.
    "save_monthly_budget": ("write", True, True, FINANCE_WRITE, False),
    "add_recurring_expense": ("write", False, True, FINANCE_WRITE, True),
    "create_savings_goal": ("write", False, True, FINANCE_WRITE, True),
    "submit_feedback": ("write", False, True, FEEDBACK_WRITE, True),
    # Turning it off deletes the usage data already linked to the user.
    "set_usage_analytics": ("write", True, True, PROFILE_WRITE, False),
}

MONEY_MOVEMENT_LIMIT = (
    "MITA cannot initiate, execute or facilitate payments or money transfers"
)


@pytest.fixture
async def tools(mcp, seed):
    user = await seed.user()
    return await mcp.list_tools(mcp.token(user))


async def test_published_tool_set_is_exactly_the_declared_set(tools):
    assert sorted(t.name for t in tools) == sorted(PUBLISHED_TOOLS)
    assert len({t.name for t in tools}) == len(tools), "tool names must be unique"
    assert set(READ_TOOLS).isdisjoint(WRITE_TOOLS)


async def test_every_published_tool_has_declared_semantics_and_a_feature(tools):
    for tool in tools:
        assert tool.name in EXPECTED, f"{tool.name}: add it to EXPECTED"
        assert tool.name in TOOL_FEATURES, f"{tool.name}: add it to TOOL_FEATURES"
        kind = EXPECTED[tool.name][0]
        assert (tool.name in READ_TOOLS) == (kind == READ), tool.name


async def test_every_tool_has_explicit_accurate_hints(tools):
    for tool in tools:
        a = tool.annotations
        assert a is not None, tool.name
        for hint in (
            "read_only_hint",
            "destructive_hint",
            "open_world_hint",
            "idempotent_hint",
        ):
            assert isinstance(getattr(a, hint), bool), (tool.name, hint)
        kind, destructive, idempotent, _, _ = EXPECTED[tool.name]
        assert a.read_only_hint is (kind == READ), tool.name
        assert a.destructive_hint is destructive, tool.name
        assert a.idempotent_hint is idempotent, tool.name
        assert a.open_world_hint is False, tool.name


async def test_hints_are_serialized_with_the_mcp_wire_names(tools):
    for tool in tools:
        wire = tool.model_dump(by_alias=True, exclude_none=True)["annotations"]
        kind, destructive, idempotent, _, _ = EXPECTED[tool.name]
        assert wire["readOnlyHint"] is (kind == READ)
        assert wire["destructiveHint"] is destructive
        assert wire["idempotentHint"] is idempotent
        assert wire["openWorldHint"] is False


async def test_no_tool_accepts_an_identity_context_or_location_argument(tools):
    for tool in tools:
        props = (tool.input_schema or {}).get("properties", {})
        for name in props:
            assert not IDENTITY_FIELD.search(name), (tool.name, name)
            assert not CONTEXT_FIELD.search(name), (tool.name, name)
            assert not LOCATION_FIELD.search(name), (tool.name, name)


async def test_create_tools_require_an_idempotency_key(tools):
    for tool in tools:
        needs_key = EXPECTED[tool.name][4]
        schema = tool.input_schema or {}
        has_key = "idempotency_key" in schema.get("properties", {})
        assert has_key is needs_key, tool.name
        if needs_key:
            assert "idempotency_key" in schema.get("required", []), tool.name


async def test_every_tool_declares_its_exact_oauth_scope(tools):
    for tool in tools:
        meta = tool.meta or {}
        schemes = meta.get("securitySchemes")
        assert schemes and schemes[0]["type"] == "oauth2", tool.name
        assert schemes[0]["scopes"] == [EXPECTED[tool.name][3]], tool.name


async def test_profile_tool_is_marked_for_multi_account(tools):
    profile = next(t for t in tools if t.name == "get_profile")
    assert (profile.meta or {}).get("openai/profile") is True
    assert (profile.input_schema or {}).get("properties", {}) == {}
    others = [t.name for t in tools if (t.meta or {}).get("openai/profile")]
    assert others == ["get_profile"]


async def test_descriptions_are_specific_and_state_their_limits(tools):
    for tool in tools:
        assert tool.description and len(tool.description) > 80, tool.name
        assert tool.title, tool.name
        if tool.name in READ_TOOLS:
            assert "Read-only" in tool.description, tool.name
        else:
            assert "Read-only" not in tool.description, tool.name


async def test_every_description_says_mita_cannot_move_money(tools):
    # Real ChatGPT refused "Transfer €200 to Anna" but went on to offer to
    # prepare the transfer elsewhere. The limit is stated as a fact on every
    # tool (OpenAI forbids metadata that steers the model about other services).
    for tool in tools:
        assert MONEY_MOVEMENT_LIMIT in tool.description, tool.name


async def test_server_instructions_state_limits_and_category_names(mcp, seed):
    user = await seed.user()
    instructions = await mcp.instructions(mcp.token(user))
    assert (
        "MITA cannot initiate, execute or facilitate payments, money transfers or trades"
        in instructions
    )
    assert "not connected to any bank or payment account" in instructions
    # Real ChatGPT showed one plan category as "Insurance medical" and "Medical
    # insurance": every category carries MITA's display name, to be kept as is.
    assert "Every category comes with category_label" in instructions
    assert "rather than renaming or merging categories" in instructions
    # "Show me Anna's transactions" must never read as access to Anna's account.
    assert "MITA has no access to anyone else's account" in instructions
    # Real ChatGPT offered to set a goal contribution no tool can set.
    assert "Offer only what a MITA tool can do" in instructions


async def test_summary_metadata_says_top_categories_is_not_a_full_breakdown(tools):
    # Real ChatGPT reported the summary's unlisted 15.99 as "Other expenses"
    # while get_spending_breakdown named it "subscriptions". "other" is itself a
    # MITA category, so a renamed remainder can be mistaken for real data.
    by_name = {t.name: t for t in tools}
    summary = by_name["get_financial_summary"]
    assert "top_categories is not a full breakdown" in summary.description
    assert "get_spending_breakdown lists by name" in summary.description
    top = summary.output_schema["properties"]["top_categories"]["description"]
    assert "Not a full breakdown" in top and "get_spending_breakdown" in top
    for name in ("get_financial_summary", "get_spending_breakdown"):
        category = by_name[name].output_schema["$defs"]["CategorySpendOut"][
            "properties"
        ]["category"]["description"]
        assert "MITA's stored category code" in category, name
        assert "Do not rename it or merge it" in category, name
        label = by_name[name].output_schema["$defs"]["CategorySpendOut"]["properties"][
            "category_label"
        ]["description"]
        assert "never rename or merge categories yourself" in label, name


async def test_every_tool_publishes_an_output_schema(tools):
    for tool in tools:
        assert (
            tool.output_schema and tool.output_schema.get("type") == "object"
        ), tool.name


async def test_no_money_movement_or_generic_tool_names(tools):
    forbidden_words = {
        "transfer",
        "pay",
        "payment",
        "send",
        "buy",
        "sell",
        "trade",
        "withdraw",
        "deposit",
        "invest",
        "execute",
        "run",
        "command",
        "action",
        "operation",
    }
    for tool in tools:
        words = set(tool.name.split("_"))
        assert not words & forbidden_words, tool.name


async def test_status_text_fits_openai_limits(tools):
    for tool in tools:
        meta = tool.meta or {}
        for key in ("openai/toolInvocation/invoking", "openai/toolInvocation/invoked"):
            assert meta.get(key) and len(meta[key]) <= 64, (tool.name, key)


async def test_every_tool_rejects_undeclared_arguments(tools):
    """additionalProperties: false on every input schema and every nested object,
    so identity or anything else cannot be smuggled in alongside real fields."""

    def objects(schema):
        if isinstance(schema, dict):
            if schema.get("type") == "object" or "properties" in schema:
                yield schema
            for value in schema.values():
                yield from objects(value)
        elif isinstance(schema, list):
            for value in schema:
                yield from objects(value)

    for tool in tools:
        found = list(objects(tool.input_schema or {}))
        assert found, tool.name
        for obj in found:
            assert obj.get("additionalProperties") is False, (tool.name, obj)
