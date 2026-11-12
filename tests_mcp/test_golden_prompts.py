"""The golden prompt set stays consistent with the published tools.

The set (``golden_prompts.json``) is reviewer-authored, never built from real
users' prompts. These checks cannot run ChatGPT; they keep the set honest and
pin the trigger language in tool metadata:

* every expected tool exists, and every published tool is covered;
* English, Russian and Bulgarian are all represented, with negative and
  ambiguous cases in each;
* a ``description_mentions`` phrase must appear in an expected tool's
  description, so editing metadata cannot silently drop the trigger.

Model-level selection is checked in ChatGPT developer mode
(``docs/chatgpt-app/staging-acceptance-v2.md``).
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from app.mcp.tools import PUBLISHED_TOOLS

GOLDEN = json.loads((Path(__file__).parent / "golden_prompts.json").read_text())[
    "prompts"
]


@pytest.fixture
async def descriptions(mcp, seed):
    user = await seed.user()
    return {t.name: t.description for t in await mcp.list_tools(mcp.token(user))}


def test_entries_are_well_formed_and_unique():
    ids = [p["id"] for p in GOLDEN]
    assert len(ids) == len(set(ids))
    for item in GOLDEN:
        assert item["language"] in {"en", "ru", "bg"}, item["id"]
        assert item["kind"] in {
            "direct",
            "indirect",
            "follow_up",
            "negative",
            "ambiguous",
        }
        assert item["expect"] in {"call", "clarify", "refuse"}, item["id"]
        assert item["prompt"].strip(), item["id"]
        if item["expect"] in {"refuse"} or item["kind"] in {"negative", "ambiguous"}:
            assert item["expected_tools"] == [] or item["expect"] == "clarify", item[
                "id"
            ]


def test_every_expected_tool_exists_and_every_tool_is_covered():
    named = Counter(t for item in GOLDEN for t in item["expected_tools"])
    assert set(named) <= set(PUBLISHED_TOOLS), set(named) - set(PUBLISHED_TOOLS)
    assert set(PUBLISHED_TOOLS) <= set(named), set(PUBLISHED_TOOLS) - set(named)


def test_three_languages_each_with_negative_and_ambiguous_cases():
    for language in ("en", "ru", "bg"):
        items = [p for p in GOLDEN if p["language"] == language]
        assert len(items) >= 10, language
        assert any(p["kind"] == "negative" for p in items), language
        assert any(p["kind"] == "ambiguous" for p in items), language


def test_no_real_user_data_in_the_set():
    for item in GOLDEN:
        text = item["prompt"]
        for email in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            assert email.endswith("@example.com"), item["id"]
        assert not re.search(r"\d{8,}", text), item["id"]  # no card/account numbers


async def test_trigger_language_is_in_the_tool_metadata(descriptions):
    for item in GOLDEN:
        phrase = item.get("description_mentions")
        if not phrase:
            continue
        assert any(
            phrase.lower() in descriptions[tool].lower()
            for tool in item["expected_tools"]
        ), (item["id"], phrase)
