#!/usr/bin/env python3
"""Validate and package the MITA ChatGPT plugin (Agent Plugins ZIP).

    # CI: validate the templates with example values (no ZIP)
    python scripts/mcp/build_plugin.py --check

    # Release: every placeholder must be a real HTTPS value; writes the ZIP
    MCP_PUBLIC_URL=https://mcp.mitafinance.com \\
    WEBSITE_URL=https://mitafinance.com SUPPORT_URL=https://mitafinance.com/support \\
    PRIVACY_URL=https://mitafinance.com/privacy TERMS_URL=https://mitafinance.com/terms \\
    SUPPORT_EMAIL=support@mitafinance.com DEVELOPER_NAME="YAKOVLEV LTD" \\
    CATEGORY=Finance DEMO_RECORDING_URL=https://... \\
    python scripts/mcp/build_plugin.py --release

Rules checked (developers.openai.com/plugins/deploy/submission, 2026-10-02):
Agent Plugins schemas (vendored in plugin/schemas), display name and short
description <= 30 chars, long description <= 4000, developer name <= 80,
<= 20 capabilities of <= 120 chars, default prompts <= 128 chars, exactly 5
positive test cases with tools_triggered + expected_behavior and exactly 3
negative ones, every triggered tool exists, icons square >= 48 px and <= 5
MiB, no app references or hooks (not yet submittable), HTTPS URLs.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = ROOT / "plugin" / "mita"
SCHEMA_DIR = ROOT / "plugin" / "schemas"
TOOLS_MODULE = ROOT / "app" / "mcp" / "tools" / "__init__.py"
DIST = ROOT / "dist" / "plugin"

PLACEHOLDERS = (
    "MCP_PUBLIC_URL",
    "WEBSITE_URL",
    "SUPPORT_URL",
    "PRIVACY_URL",
    "TERMS_URL",
    "SUPPORT_EMAIL",
    "DEVELOPER_NAME",
    "CATEGORY",
    "DEMO_RECORDING_URL",
)
URL_PLACEHOLDERS = {
    "MCP_PUBLIC_URL",
    "WEBSITE_URL",
    "SUPPORT_URL",
    "PRIVACY_URL",
    "TERMS_URL",
    "DEMO_RECORDING_URL",
}
CHECK_VALUES = {
    "MCP_PUBLIC_URL": "https://mcp.example.invalid",
    "WEBSITE_URL": "https://www.example.invalid",
    "SUPPORT_URL": "https://www.example.invalid/support",
    "PRIVACY_URL": "https://www.example.invalid/privacy",
    "TERMS_URL": "https://www.example.invalid/terms",
    "SUPPORT_EMAIL": "support@example.invalid",
    "DEVELOPER_NAME": "Example Developer",
    "CATEGORY": "Finance",
    "DEMO_RECORDING_URL": "https://www.example.invalid/demo",
}
# Hosts that must never reach a submitted package: examples, and mita.finance,
# which MITA does not own (docs/chatgpt-app/repository-audit.md §7).
FORBIDDEN_HOSTS = re.compile(r"(^|\.)(example\.(invalid|com|org|test)|mita\.finance)$")

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class PluginError(Exception):
    pass


def published_tools() -> List[str]:
    tree = ast.parse(TOOLS_MODULE.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PUBLISHED_TOOLS" for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise PluginError("PUBLISHED_TOOLS not found in app/mcp/tools/__init__.py")


def render(template: str, values: Dict[str, str]) -> str:
    def sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            raise PluginError(f"no value for placeholder {{{{{key}}}}}")
        return json.dumps(values[key])[1:-1]  # JSON-escape inside the string

    out = re.sub(r"\{\{([A-Z_]+)\}\}", sub, template)
    if "{{" in out:
        raise PluginError("unreplaced placeholder left in template")
    return out


def release_values() -> Dict[str, str]:
    values, problems = {}, []
    for key in PLACEHOLDERS:
        value = os.environ.get(key, "").strip()
        if not value:
            problems.append(f"{key} is not set")
            continue
        if key in URL_PLACEHOLDERS:
            parsed = urlparse(value)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not host:
                problems.append(f"{key} must be an https URL")
            elif FORBIDDEN_HOSTS.search(host):
                problems.append(f"{key} uses a host that cannot be submitted ({host})")
        if key == "MCP_PUBLIC_URL" and urlparse(value).path not in ("", "/"):
            problems.append("MCP_PUBLIC_URL must be an origin (no path)")
        values[key] = value.rstrip("/") if key == "MCP_PUBLIC_URL" else value
    if problems:
        raise PluginError("; ".join(problems))
    return values


def _svg_size(path: Path) -> tuple[float, float]:
    text = path.read_text()
    view_box = re.search(r'viewBox="([\d.\s-]+)"', text)
    if view_box:
        parts = [float(p) for p in view_box.group(1).split()]
        return parts[2], parts[3]
    width = re.search(r'width="([\d.]+)"', text)
    height = re.search(r'height="([\d.]+)"', text)
    if not (width and height):
        raise PluginError(f"{path.name}: SVG needs a viewBox or numeric width/height")
    return float(width.group(1)), float(height.group(1))


def check_image(path: Path, *, square: bool) -> None:
    if not path.is_file():
        raise PluginError(f"missing asset {path.relative_to(PLUGIN_DIR)}")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise PluginError(f"{path.name} exceeds 5 MiB")
    suffix = path.suffix.lower()
    if suffix == ".svg":
        width, height = _svg_size(path)
    elif suffix == ".png":
        header = path.read_bytes()[:24]
        width, height = int.from_bytes(header[16:20], "big"), int.from_bytes(
            header[20:24], "big"
        )
    elif suffix in (".jpg", ".jpeg", ".webp"):
        return  # dimensions checked by the dashboard; size limit enforced above
    else:
        raise PluginError(f"{path.name}: unsupported image type")
    if square and (width != height or width < 48):
        raise PluginError(f"{path.name}: icons must be square and at least 48x48")
    if suffix == ".png" and max(width, height) > 4096:
        raise PluginError(f"{path.name}: raster images must be at most 4096 px")


def validate(plugin: dict, mcp: dict, tools: List[str]) -> None:
    import jsonschema

    for doc, schema in ((plugin, "agent-plugins-plugin"), (mcp, "agent-plugins-mcp")):
        jsonschema.validate(
            doc, json.loads((SCHEMA_DIR / f"{schema}.schema.json").read_text())
        )

    if not re.fullmatch(r"\d+\.\d+\.\d+", plugin.get("version", "")):
        raise PluginError("version must be semantic (x.y.z)")
    ext = plugin["extensions"]["com.openai"]
    if "apps" in ext or "hooks" in ext:
        raise PluginError("app references and hooks cannot currently be submitted")
    ui = ext["interface"]
    limits = {
        "displayName": 30,
        "shortDescription": 30,
        "longDescription": 4000,
        "developerName": 80,
    }
    for key, limit in limits.items():
        if not ui.get(key) or len(ui[key]) > limit:
            raise PluginError(f"interface.{key} must be 1..{limit} characters")
    caps = ui.get("capabilities", [])
    if len(caps) > 20 or any(len(c) > 120 for c in caps):
        raise PluginError("at most 20 capabilities of at most 120 characters")
    if any(len(p) > 128 for p in ui.get("defaultPrompt", [])):
        raise PluginError("default prompts must be at most 128 characters")
    for key in ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL"):
        if urlparse(ui.get(key, "")).scheme != "https":
            raise PluginError(f"interface.{key} must be https")

    review = ext["review"]
    positive = review["test_cases"]["positive"]
    negative = review["test_cases"]["negative"]
    if len(positive) != 5 or len(negative) != 3:
        raise PluginError(
            "OpenAI requires exactly 5 positive and 3 negative test cases"
        )
    for case in positive:
        for field in ("description", "prompt", "tools_triggered", "expected_behavior"):
            if not case.get(field):
                raise PluginError(f"positive case missing {field}")
        if len(case["description"]) > 4000:
            raise PluginError("positive case description over 4000 characters")
        for name in (t.strip() for t in case["tools_triggered"].split(",")):
            if name not in tools:
                raise PluginError(f"tools_triggered names unknown tool {name!r}")
    for case in negative:
        if not case.get("description") or not case.get("prompt"):
            raise PluginError("negative case needs description and prompt")
    if review.get("commerce") is not False:
        raise PluginError("MITA's plugin must declare commerce: false")

    for key, square in (
        ("composerIcon", True),
        ("composerIconDark", True),
        ("logo", True),
        ("logoDark", True),
    ):
        if key in ui:
            check_image(PLUGIN_DIR / ui[key], square=square)
    for shot in ui.get("screenshots", []):
        check_image(PLUGIN_DIR / shot, square=False)

    servers = mcp["mcpServers"]
    if len(servers) != 1:
        raise PluginError("exactly one MCP server expected")
    (server,) = servers.values()
    url = urlparse(server["url"])
    if (
        server["type"] != "streamable-http"
        or url.scheme != "https"
        or url.path != "/mcp"
    ):
        raise PluginError("MCP server must be streamable-http at https://<host>/mcp")


def build(values: Dict[str, str], *, write_zip: bool) -> Path | None:
    plugin = json.loads(
        render((PLUGIN_DIR / "plugin.template.json").read_text(), values)
    )
    mcp = json.loads(render((PLUGIN_DIR / "mcp.template.json").read_text(), values))
    validate(plugin, mcp, published_tools())
    if not write_zip:
        return None
    DIST.mkdir(parents=True, exist_ok=True)
    target = DIST / f"{plugin['name']}-{plugin['version']}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "plugin.json", json.dumps(plugin, indent=2, ensure_ascii=False) + "\n"
        )
        zf.writestr("mcp.json", json.dumps(mcp, indent=2) + "\n")
        for asset in sorted((PLUGIN_DIR / "assets").iterdir()):
            zf.write(asset, f"assets/{asset.name}")
    return target


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check", action="store_true", help="validate with example values"
    )
    mode.add_argument("--release", action="store_true", help="build the submission ZIP")
    args = parser.parse_args(argv)
    try:
        if args.check:
            build(CHECK_VALUES, write_zip=False)
            print("plugin package: valid (example values)")
        else:
            target = build(release_values(), write_zip=True)
            print(f"plugin package written: {target.relative_to(ROOT)}")
    except PluginError as exc:
        print(f"plugin package: INVALID — {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
