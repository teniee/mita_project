"""The plugin package validates, and the validator rejects what OpenAI rejects."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_plugin", ROOT / "scripts/mcp/build_plugin.py"
)
build_plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_plugin)


def _docs():
    values = build_plugin.CHECK_VALUES
    plugin = json.loads(
        build_plugin.render(
            (build_plugin.PLUGIN_DIR / "plugin.template.json").read_text(), values
        )
    )
    mcp = json.loads(
        build_plugin.render(
            (build_plugin.PLUGIN_DIR / "mcp.template.json").read_text(), values
        )
    )
    return plugin, mcp


def test_package_is_valid():
    assert build_plugin.main(["--check"]) == 0


def test_listing_states_mita_cannot_move_money():
    plugin, _ = _docs()
    listing = plugin["extensions"]["com.openai"]["interface"]["longDescription"]
    assert (
        "MITA cannot initiate, execute or facilitate payments, money transfers or trades"
        in listing
    )


def test_test_cases_reference_only_published_tools():
    from app.mcp.tools import PUBLISHED_TOOLS

    assert build_plugin.published_tools() == list(PUBLISHED_TOOLS)


@pytest.mark.parametrize(
    "mutate,message",
    [
        (
            lambda p, m: p["extensions"]["com.openai"]["review"]["test_cases"][
                "positive"
            ].pop(),
            "exactly 5",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["review"]["test_cases"][
                "negative"
            ].pop(),
            "exactly 5",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                displayName="x" * 31
            ),
            "displayName",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                shortDescription="y" * 31
            ),
            "shortDescription",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"].update(apps="./.app.json"),
            "cannot currently be submitted",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["review"]["test_cases"][
                "positive"
            ][0].update(tools_triggered="transfer_money"),
            "unknown tool",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["review"].update(commerce=True),
            "commerce",
        ),
        (
            lambda p, m: m["mcpServers"]["mita-finance"].update(
                url="http://mcp.example.invalid/mcp"
            ),
            "streamable-http",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                defaultPrompt=["a", "b", "c", "d"]
            ),
            "at most 3 starter prompts",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                defaultPrompt=["Record an expense.", "record an expense."]
            ),
            "unique",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                defaultPrompt=["@MITA how am I doing?"]
            ),
            "@mention",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"].update(
                onboardingSkill="./skills/missing/SKILL.md"
            ),
            "onboardingSkill",
        ),
    ],
)
def test_validator_rejects(mutate, message):
    plugin, mcp = _docs()
    plugin, mcp = copy.deepcopy(plugin), copy.deepcopy(mcp)
    mutate(plugin, mcp)
    with pytest.raises(build_plugin.PluginError, match=message):
        build_plugin.validate(plugin, mcp, build_plugin.published_tools())


def test_release_refuses_placeholders_and_unowned_domain(monkeypatch):
    for key in build_plugin.PLACEHOLDERS:
        monkeypatch.setenv(key, build_plugin.CHECK_VALUES[key])
    with pytest.raises(build_plugin.PluginError, match="cannot be submitted"):
        build_plugin.release_values()
    monkeypatch.setenv("MCP_PUBLIC_URL", "https://mcp.mita.finance")
    with pytest.raises(build_plugin.PluginError, match="mita.finance"):
        build_plugin.release_values()


def test_onboarding_skill_is_declared_valid_and_shipped(tmp_path, monkeypatch):
    plugin, _ = _docs()
    ext = plugin["extensions"]["com.openai"]
    assert ext["onboardingSkill"] == "./skills/setup/SKILL.md"
    meta = build_plugin.skill_frontmatter(
        build_plugin.PLUGIN_DIR / "skills/setup/SKILL.md"
    )
    assert meta["name"] == "setup"
    assert "get_setup_status" in meta["description"]
    monkeypatch.setattr(build_plugin, "DIST", tmp_path)
    target = build_plugin.build(build_plugin.CHECK_VALUES, write_zip=True)
    import zipfile

    names = zipfile.ZipFile(target).namelist()
    assert "skills/setup/SKILL.md" in names and "plugin.json" in names


def test_skill_names_only_published_tools():
    import re

    from app.mcp.tools import PUBLISHED_TOOLS

    text = (build_plugin.PLUGIN_DIR / "skills/setup/SKILL.md").read_text()
    named = set(re.findall(r"`([a-z_]+)`", text)) - {
        "known",
        "missing_fields",
        "draft_token",
        "insufficient_data",
        "category_label",  # a result field
        "ask_about_obligations",  # a suggested_next_step value
    }
    assert named and named <= set(PUBLISHED_TOOLS), named - set(PUBLISHED_TOOLS)


def test_starter_prompts_are_the_planned_three():
    plugin, _ = _docs()
    assert plugin["extensions"]["com.openai"]["interface"]["defaultPrompt"] == [
        "Set up my monthly budget from scratch.",
        "Record an expense I just made.",
        "How am I doing financially this month?",
    ]


def test_listing_advertises_no_pricing_or_premium():
    plugin, _ = _docs()
    ui = plugin["extensions"]["com.openai"]["interface"]
    listing = " ".join(
        [ui["displayName"], ui["shortDescription"], ui["longDescription"]]
        + ui["capabilities"]
        + ui["defaultPrompt"]
        + [plugin["description"]]
    ).lower()
    for word in (
        "free",
        "price",
        "pricing",
        "trial",
        "premium",
        "discount",
        "upgrade",
        "$",
    ):
        assert word not in listing, word
