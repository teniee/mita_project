#!/usr/bin/env python3
"""Does any live variable still hold a value that was committed to git?

The repository is public, so every value in the table below is disclosed.
Only fingerprints are embedded (first 12 hex characters of SHA-256 — the same
scheme as docs/chatgpt-app/security-findings.md). Values are never printed:
not the leaked ones, not the live ones.

Owner-run, because it reads production variables:

    railway variable list --project d44d0580-3476-4e46-bc4c-b2d95dac64cd \\
        --environment production --service mita-production --json \\
      | python3 scripts/mcp/check_leaked_secrets.py --source mita-production

Repeat with ``--service mita-production-db``. Any JSON file on stdin works the
same way (every string in it is checked, e.g. an IDE ``.mcp.json``), and a
file of KEY=VALUE lines with ``--env-file PATH``.

Each value is compared whole, and also by the password inside a URL
(``redis://default:<pw>@host``) and the token inside ``Bearer <token>``.
Output: one line per match — variable name, the committed item it equals, and
whether that item was a real secret or a placeholder. Exit 0: no committed
value in use. Exit 1: at least one match (rotate it; for a placeholder,
replace it). Exit 2: unreadable input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from typing import Dict, Iterable, Iterator, List, NamedTuple, Optional, Tuple
from urllib.parse import urlsplit


class Leak(NamedTuple):
    item: str
    kind: str  # "secret" (real-looking) or "placeholder"


# fingerprint -> what was committed. Derived from every revision of
# .env.production / .env.production.test (bf69fae, 7d3af83, 0881bf7),
# .mcp.json (f83ad16, 3f0bb68) and agent_finance_advisor.py (2f2c1f1).
# Not listed (not secrets): GOOGLE_APPLICATION_CREDENTIALS (a file path),
# RATE_LIMIT_PASSWORD_RESET, the Supabase MCP URL, command paths.
LEAKED: Dict[str, Leak] = {
    # security-findings S-1..S-3
    "825ad855969b": Leak("S-1 Supabase secret key (sb_secret_…), .mcp.json", "secret"),
    "9b824f818673": Leak(
        "S-2 Upstash Redis password (integral-jaybird-23463), .mcp.json", "secret"
    ),
    "04885534e0d0": Leak("S-2 Upstash REDIS_URL (whole URL), .mcp.json", "secret"),
    "86d0921d9661": Leak("S-3 OpenAI key literal, agent_finance_advisor.py", "secret"),
    # S-4: .env.production @ 0881bf7 (2025-09-06), also .env.production.test
    "7d2122790a81": Leak("S-4 JWT_SECRET, .env.production 0881bf7", "secret"),
    "4533279340f8": Leak("S-4 JWT_PREVIOUS_SECRET, .env.production 0881bf7", "secret"),
    "9663211c9f9f": Leak("S-4 SECRET_KEY, .env.production 0881bf7", "secret"),
    "1b5a12cfe5c9": Leak(
        "S-4 DATABASE_URL (whole URL), .env.production 0881bf7", "secret"
    ),
    "4a844b1f918f": Leak(
        "S-4 POSTGRES_PASSWORD / DATABASE_URL password, .env.production 0881bf7",
        "secret",
    ),
    "cb2190673a19": Leak(
        "S-4 REDIS_URL (whole URL), .env.production 0881bf7", "secret"
    ),
    "bca91625a628": Leak(
        "S-4 REDIS_PASSWORD / REDIS_URL password, .env.production 0881bf7", "secret"
    ),
    "4c84d7d9e712": Leak("S-4 OPENAI_API_KEY, .env.production 0881bf7", "placeholder"),
    "c2283908c30d": Leak(
        "APNS_KEY (24 chars; possibly a path), .env.production", "secret"
    ),
    # placeholders committed in the same files: a live variable equal to one of
    # these is a misconfiguration, not a disclosed credential
    "171873b55a60": Leak(
        "UPSTASH_REDIS_REST_TOKEN, .env.production 0881bf7", "placeholder"
    ),
    "fd013641232c": Leak(
        "UPSTASH_REDIS_URL (localhost), .env.production", "placeholder"
    ),
    "9f86d081884c": Leak(
        'the literal "test" (UPSTASH_REDIS_URL password)', "placeholder"
    ),
    "9c7b41779c17": Leak("UPSTASH_AUTH_TOKEN, .env.production.test", "placeholder"),
    "48d63799322b": Leak(
        "DATABASE_URL, .env.production 7d3af83/bf69fae", "placeholder"
    ),
    "60ca04545671": Leak(
        "POSTGRES_PASSWORD, .env.production 7d3af83/bf69fae", "placeholder"
    ),
    "a33fd676e6b6": Leak("JWT_SECRET, .env.production 7d3af83/bf69fae", "placeholder"),
    "e0541c655f08": Leak(
        "JWT_PREVIOUS_SECRET, .env.production 7d3af83/bf69fae", "placeholder"
    ),
    "056b225c077d": Leak("SECRET_KEY, .env.production 7d3af83/bf69fae", "placeholder"),
    "69337f2ddf4b": Leak("REDIS_URL, .env.production 7d3af83/bf69fae", "placeholder"),
    "f8b518ca02e5": Leak(
        "REDIS_PASSWORD, .env.production 7d3af83/bf69fae", "placeholder"
    ),
    "220905a0433a": Leak(
        "OPENAI_API_KEY, .env.production 7d3af83/bf69fae", "placeholder"
    ),
    "cf460ce1b4d9": Leak("SMTP_PASSWORD, .env.production 0881bf7", "placeholder"),
    "152534208628": Leak(
        "SMTP_PASSWORD, .env.production 7d3af83/bf69fae", "placeholder"
    ),
    "3c8f1b7f72c7": Leak("SENTRY_DSN, .env.production", "placeholder"),
    "ab462ead3767": Leak("AWS_ACCESS_KEY_ID, .env.production", "placeholder"),
    "799b9a7e1272": Leak("AWS_SECRET_ACCESS_KEY, .env.production", "placeholder"),
    "e22554ebddf7": Leak("APPSTORE_SHARED_SECRET, .env.production", "placeholder"),
    "775ec3cc2546": Leak("APNS_KEY_ID, .env.production", "placeholder"),
    "5f59d83730d5": Leak(
        "GRAFANA_PASSWORD, .env.production 7d3af83/bf69fae", "placeholder"
    ),
}

# Not secret, but tells whether a live URL points at a leaked Upstash database.
LEAKED_HOSTS = {"integral-jaybird-23463.upstash.io": "S-2 Upstash database"}


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _parts(value: str) -> Iterator[Tuple[str, str]]:
    """(form, candidate) pairs to compare: the whole value, a URL password,
    a bearer token."""
    yield "value", value
    try:
        url = urlsplit(value)
        password = url.password if url.scheme else None
    except ValueError:
        password = None
    if password:
        yield "URL password", password
    scheme, _, token = value.partition(" ")
    if scheme.lower() == "bearer" and token:
        yield "bearer token", token.strip()


def _host(value: str) -> Optional[str]:
    try:
        url = urlsplit(value)
        return url.hostname if url.scheme else None
    except ValueError:
        return None


def check(variables: Iterable[Tuple[str, str]]) -> List[str]:
    """Report lines. Contains variable names and table labels, never values."""
    lines: List[str] = []
    for name, value in variables:
        if not isinstance(value, str) or not value:
            continue
        for form, candidate in _parts(value):
            leak = LEAKED.get(fingerprint(candidate))
            if leak is not None:
                lines.append(f"MATCH   {name} ({form}) = {leak.item} [{leak.kind}]")
        host = _host(value)
        if host in LEAKED_HOSTS:
            lines.append(
                f"HOST    {name} points at {LEAKED_HOSTS[host]} — its password must "
                "differ from the leaked one (no MATCH line above means it does)"
            )
    return lines


def _leaves(data: object, path: str = "") -> Iterator[Tuple[str, str]]:
    """Every string in any JSON shape, named by its key path, so an unexpected
    CLI format cannot turn into a silent "0 matches"."""
    if isinstance(data, dict):
        name = data.get("name") or data.get("key")
        if isinstance(name, str) and isinstance(data.get("value"), str):
            yield name, data["value"]
            return
        for key, value in data.items():
            yield from _leaves(value, f"{path}.{key}" if path else str(key))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _leaves(value, f"{path}[{index}]")
    elif isinstance(data, str):
        yield path or "<root>", data


def _from_json(text: str) -> List[Tuple[str, str]]:
    return list(_leaves(json.loads(text)))


def _from_env_file(path: str) -> List[Tuple[str, str]]:
    pairs = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.removeprefix("export ").strip()
            pairs.append((key, value.strip().strip('"').strip("'")))
    return pairs


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", default="stdin", help="label for the report")
    parser.add_argument("--env-file", help="read KEY=VALUE lines from this file")
    args = parser.parse_args(argv)
    try:
        if args.env_file:
            variables = _from_env_file(args.env_file)
        else:
            variables = _from_json(sys.stdin.read())
    except (OSError, ValueError) as exc:
        # The exception text can quote input; report its type only.
        print(
            f"{args.source}: unreadable input ({type(exc).__name__})", file=sys.stderr
        )
        return 2
    if not variables:
        print(f"{args.source}: no variables found in the input", file=sys.stderr)
        return 2
    lines = check(variables)
    for line in lines:
        print(f"{args.source}: {line}")
    matches = sum(line.startswith("MATCH") for line in lines)
    print(
        f"{args.source}: {len(variables)} variables checked, {matches} match(es) "
        "with committed values"
    )
    return 1 if matches else 0


if __name__ == "__main__":
    sys.exit(main())
