"""Every published tool meets OpenAI's and MITA's contract.

Fails if a tool is added without explicit read/destructive/open-world hints,
with an input that could select whose data to read, without a description
that states it is read-only, or without an output schema.
"""

import re

import pytest

from app.mcp.tools import PUBLISHED_TOOLS

IDENTITY_FIELD = re.compile(
    r"(^|_)(user|uid|account|owner|email|customer|member|profile_id|person|tenant)(_|$|id)",
    re.IGNORECASE,
)
# Field names that would let the model pass conversation context "just in case".
CONTEXT_FIELD = re.compile(
    r"(history|transcript|conversation|messages|context)", re.IGNORECASE
)


@pytest.fixture
async def tools(mcp, seed):
    user = await seed.user()
    return await mcp.list_tools(mcp.token(user))


async def test_published_tool_set_is_exactly_the_read_only_v1_set(tools):
    assert sorted(t.name for t in tools) == sorted(PUBLISHED_TOOLS)
    assert len({t.name for t in tools}) == len(tools), "tool names must be unique"


async def test_every_tool_has_explicit_boolean_hints(tools):
    for tool in tools:
        a = tool.annotations
        assert a is not None, tool.name
        for hint in ("read_only_hint", "destructive_hint", "open_world_hint"):
            assert isinstance(getattr(a, hint), bool), (tool.name, hint)
        assert a.read_only_hint is True, tool.name
        assert a.destructive_hint is False, tool.name
        assert a.open_world_hint is False, tool.name


async def test_hints_are_serialized_with_the_mcp_wire_names(tools):
    for tool in tools:
        wire = tool.model_dump(by_alias=True, exclude_none=True)["annotations"]
        assert wire["readOnlyHint"] is True
        assert wire["destructiveHint"] is False
        assert wire["openWorldHint"] is False


async def test_no_tool_accepts_an_identity_or_context_argument(tools):
    for tool in tools:
        props = (tool.input_schema or {}).get("properties", {})
        for name in props:
            assert not IDENTITY_FIELD.search(name), (tool.name, name)
            assert not CONTEXT_FIELD.search(name), (tool.name, name)


async def test_every_tool_declares_oauth_security_scheme(tools):
    for tool in tools:
        meta = tool.meta or {}
        schemes = meta.get("securitySchemes")
        assert schemes and schemes[0]["type"] == "oauth2", tool.name
        assert set(schemes[0]["scopes"]) <= {"profile:read", "finance:read"}, tool.name


async def test_profile_tool_is_marked_for_multi_account(tools):
    profile = next(t for t in tools if t.name == "get_profile")
    assert (profile.meta or {}).get("openai/profile") is True
    assert (profile.input_schema or {}).get("properties", {}) == {}


async def test_descriptions_are_specific_and_state_read_only(tools):
    for tool in tools:
        assert tool.description and len(tool.description) > 80, tool.name
        assert "Read-only" in tool.description, tool.name
        assert tool.title, tool.name


async def test_every_tool_publishes_an_output_schema(tools):
    for tool in tools:
        assert (
            tool.output_schema and tool.output_schema.get("type") == "object"
        ), tool.name


async def test_no_write_verbs_in_tool_names(tools):
    forbidden = (
        "create",
        "add",
        "update",
        "delete",
        "remove",
        "transfer",
        "pay",
        "send",
        "buy",
        "sell",
        "execute",
        "set",
    )
    for tool in tools:
        first = tool.name.split("_")[0]
        assert first not in forbidden, tool.name
