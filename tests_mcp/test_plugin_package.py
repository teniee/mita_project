"""The plugin package validates, and the validator rejects what OpenAI rejects."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from app.mcp.tools.calendar import SHOW_DESCRIPTION

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


def test_mcp_json_declares_oauth_with_dynamic_client_registration():
    """The portal reads the server's authentication from mcp.json
    (developers.openai.com/plugins/deploy/submission, "Configure
    authentication for submission"); MITA's authorization server offers DCR."""
    _, mcp = _docs()
    server = mcp["mcpServers"]["mita-finance"]
    assert server["extensions"]["com.openai"]["auth"] == {
        "type": "oauth",
        "client": {"mode": "dcr"},
    }


def test_listing_makes_no_promise_about_the_unreleased_app():
    """mitafinance.com says the MITA app is "Coming soon": the listing, the
    onboarding skill and the tool descriptions must not promise ChatGPT users
    their records "in the MITA app". Change this when the app is in the stores."""
    from app.mcp.tools.transactions import ADD_DESCRIPTION

    plugin, _ = _docs()
    ui = plugin["extensions"]["com.openai"]["interface"]
    skill = (build_plugin.PLUGIN_DIR / "skills/setup/SKILL.md").read_text()
    for where, text in (
        ("longDescription", ui["longDescription"]),
        (
            "release_notes",
            plugin["extensions"]["com.openai"]["publication"]["release_notes"],
        ),
        ("setup skill", skill),
        ("add_transaction", ADD_DESCRIPTION),
    ):
        assert "MITA app" not in text.replace("\n", " "), where


def test_review_cases_cover_the_ui_component():
    """The calendar is the only UI component; review checks UI errors, so a
    positive case exercises it with the calendar starter prompt."""
    plugin, _ = _docs()
    positive = plugin["extensions"]["com.openai"]["review"]["test_cases"]["positive"]
    calendar = [
        c for c in positive if c["tools_triggered"] == "show_financial_calendar"
    ]
    assert len(calendar) == 1
    prompts = plugin["extensions"]["com.openai"]["interface"]["defaultPrompt"]
    assert calendar[0]["prompt"] in prompts


def test_release_notes_describe_the_package_version():
    """OpenAI: release notes summarize the package version being submitted."""
    plugin, _ = _docs()
    notes = plugin["extensions"]["com.openai"]["publication"]["release_notes"]
    assert notes.startswith(plugin["version"] + " ")


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
        # Current submission rules (developers.openai.com, 2026-10-27).
        (lambda p, m: p.update(description="d" * 1025), "1..1024"),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                category="Budgeting"
            ),
            "category",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                brandColor="#FFF0F0"
            ),
            "contrast",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                brandColorDark="#303030"
            ),
            "contrast",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                shortDescription="Budget,\nexpenses"
            ),
            "single line",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                defaultPrompt=["Record an expense.", "Record  an expense."]
            ),
            "unique",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["publication"].update(
                release_notes=" "
            ),
            "release_notes",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["review"].pop(
                "demo_recording_url"
            ),
            "demo_recording_url",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["review"].update(
                test_credentials={"username": "x"}
            ),
            "test_credentials",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["review"]["test_cases"][
                "negative"
            ][0].pop("expected_behavior"),
            "negative case missing expected_behavior",
        ),
        (
            lambda p, m: p["extensions"]["com.openai"]["interface"].update(
                screenshots=["./assets/icon.svg"]
            ),
            "one per starter prompt",
        ),
        (
            lambda p, m: m["mcpServers"]["mita-finance"].pop("extensions"),
            "auth",
        ),
        (
            lambda p, m: m["mcpServers"]["mita-finance"]["extensions"]["com.openai"][
                "auth"
            ].update(type="none"),
            "oauth",
        ),
        (
            lambda p, m: m["mcpServers"]["mita-finance"]["extensions"]["com.openai"][
                "auth"
            ]["client"].update(clientId="mita"),
            "no client id",
        ),
        (
            lambda p, m: m["mcpServers"]["mita-finance"].update(
                headers={"Authorization": "Bearer x"}
            ),
            "headers",
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
    """Set up, record, see: the calendar replaced "How am I doing financially
    this month?" (owner, 2026-10-25) — it answers that question on screen."""
    plugin, _ = _docs()
    assert plugin["extensions"]["com.openai"]["interface"]["defaultPrompt"] == [
        "Set up my monthly budget from scratch.",
        "Record an expense I just made.",
        "Show my financial calendar for this month.",
    ]


def test_the_calendar_starter_prompt_opens_the_interactive_calendar():
    """The starter prompt is a golden prompt routed to the render tool, whose
    description names the request, so ChatGPT shows the calendar component
    rather than a text table."""
    plugin, _ = _docs()
    prompt = plugin["extensions"]["com.openai"]["interface"]["defaultPrompt"][2]
    golden = json.loads((ROOT / "tests_mcp" / "golden_prompts.json").read_text())[
        "prompts"
    ]
    entry = next(g for g in golden if g["prompt"] == prompt)
    assert entry["expected_tools"] == ["show_financial_calendar"]
    assert entry["description_mentions"] in SHOW_DESCRIPTION


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
