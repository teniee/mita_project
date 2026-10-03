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
