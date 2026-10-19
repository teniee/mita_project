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
<= 20 capabilities of <= 120 chars, <= 3 unique starter prompts of <= 128
chars without @mentions, skills/<name>/SKILL.md with name + description and
onboardingSkill pointing at one of them, exactly 5
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
    """``PUBLISHED_TOOLS`` from app/mcp/tools/__init__.py, read without importing
    the service: a literal tuple, or a sum of literal tuples defined above it."""
    tree = ast.parse(TOOLS_MODULE.read_text())
    literals: Dict[str, List[str]] = {}

    def evaluate(node: ast.AST) -> List[str]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return evaluate(node.left) + evaluate(node.right)
        if isinstance(node, ast.Name) and node.id in literals:
            return list(literals[node.id])
        return list(ast.literal_eval(node))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "PUBLISHED_TOOLS" in names:
            return evaluate(node.value)
        try:
            value = evaluate(node.value)
        except ValueError:
            continue
        for name in names:
            literals[name] = value
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


SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def skill_frontmatter(path: Path) -> Dict[str, str]:
    """The YAML front matter of a SKILL.md (simple ``key: value`` lines)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise PluginError(f"{path.relative_to(PLUGIN_DIR)}: missing YAML front matter")
    header, _, body = text[4:].partition("\n---\n")
    if not body.strip():
        raise PluginError(f"{path.relative_to(PLUGIN_DIR)}: empty instructions")
    fields: Dict[str, str] = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields[key.strip()] = value.strip().strip('"')
    return fields


def check_skills(ext: dict) -> List[Path]:
    """Every skills/<name>/SKILL.md has a valid name (= its directory) and a
    description; onboardingSkill, if set, points at one of them."""
    skills_dir = PLUGIN_DIR / "skills"
    found = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []
    names = set()
    for path in found:
        meta = skill_frontmatter(path)
        name = meta.get("name", "")
        if not SKILL_NAME.fullmatch(name) or len(name) > 64:
            raise PluginError(f"skill name {name!r} must be kebab-case, <= 64 chars")
        if name != path.parent.name:
            raise PluginError(f"skill {name!r} must live in skills/{name}/")
        description = meta.get("description", "")
        if not description or len(description) > 1024:
            raise PluginError(f"skill {name!r} needs a description of 1..1024 chars")
        names.add(name)
    onboarding = ext.get("onboardingSkill")
    if onboarding is not None:
        target = (PLUGIN_DIR / onboarding).resolve()
        if not onboarding.startswith("./skills/") or target not in {
            p.resolve() for p in found
        }:
            raise PluginError(
                "onboardingSkill must point to an included skills/<name>/SKILL.md"
            )
    return found


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
    prompts = ui.get("defaultPrompt", [])
    if len(prompts) > 3:
        raise PluginError("at most 3 starter prompts (defaultPrompt)")
    if any(not p or len(p) > 128 for p in prompts):
        raise PluginError("default prompts must be 1..128 characters")
    if len({p.strip().lower() for p in prompts}) != len(prompts):
        raise PluginError("starter prompts must be unique")
    if any("@" in p for p in prompts):
        raise PluginError("starter prompts must not @mention an app")
    check_skills(ext)
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
        for skill in check_skills(plugin["extensions"]["com.openai"]):
            for item in sorted(skill.parent.rglob("*")):
                if item.is_file():
                    zf.write(item, item.relative_to(PLUGIN_DIR).as_posix())
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
