#!/usr/bin/env python3
"""Generate every secret the MCP service needs, for one environment.

    python scripts/mcp/generate_keys.py                    # print to stdout
    python scripts/mcp/generate_keys.py --out staging.env  # write a NEW file (0600)

Generates, independently:
  MCP_OAUTH_PRIVATE_KEY         RSA-3072 PKCS#8 PEM (newlines escaped as \\n)
  MCP_LOGIN_CSRF_SECRET         consent-page CSRF / pending-request HMAC key
  MCP_GRANT_FINGERPRINT_SECRET  HMAC key binding grants to the password hash
  JWT_SECRET / SECRET_KEY       required by app.core.config at import in
                                production; unused by the MCP service; never
                                the API's values
  MCP_METRICS_TOKEN             bearer token for /metrics

`--out` refuses to touch an existing file: secrets are never overwritten
silently. Run once per environment (staging and production get different
values). Nothing is sent anywhere.
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.mcp.auth.keys import generate_private_key_pem  # noqa: E402


def generate() -> dict:
    values = {
        "MCP_OAUTH_PRIVATE_KEY": generate_private_key_pem(3072)
        .strip()
        .replace("\n", "\\n"),
        "MCP_LOGIN_CSRF_SECRET": secrets.token_hex(32),
        "MCP_GRANT_FINGERPRINT_SECRET": secrets.token_hex(32),
        "JWT_SECRET": secrets.token_urlsafe(48),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "MCP_METRICS_TOKEN": secrets.token_urlsafe(32),
    }
    assert values["MCP_LOGIN_CSRF_SECRET"] != values["MCP_GRANT_FINGERPRINT_SECRET"]
    return values


def render(values: dict) -> str:
    lines = []
    for key, value in values.items():
        lines.append(
            f'{key}="{value}"' if key == "MCP_OAUTH_PRIVATE_KEY" else f"{key}={value}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MCP service secrets")
    parser.add_argument("--out", help="write to this NEW file (refuses to overwrite)")
    args = parser.parse_args()
    text = render(generate())
    if not args.out:
        sys.stdout.write(text)
        return 0
    path = Path(args.out)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"refusing to overwrite existing {path}", file=sys.stderr)
        return 1
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    print(f"wrote {len(text.splitlines())} secrets to {path} (mode 0600)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
