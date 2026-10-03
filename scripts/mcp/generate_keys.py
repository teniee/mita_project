#!/usr/bin/env python3
"""Generate the MCP service's secrets for the owner to paste into Railway.

    python scripts/mcp/generate_keys.py > /tmp/mita-mcp-secrets.env   # then delete it

Prints, to stdout only:
  MCP_OAUTH_PRIVATE_KEY   RSA-3072 PKCS#8 PEM (newlines escaped as \\n)
  MCP_LOGIN_CSRF_SECRET   64 hex chars
  JWT_SECRET / SECRET_KEY random values that satisfy app.core.config in
                          production. The MCP service never uses them; they
                          must NOT be the API's values (least privilege).
  MCP_METRICS_TOKEN       bearer token for /metrics

Nothing is written to disk or sent anywhere by this script.
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.mcp.auth.keys import generate_private_key_pem  # noqa: E402


def main() -> None:
    pem = generate_private_key_pem(3072).strip().replace("\n", "\\n")
    print(f'MCP_OAUTH_PRIVATE_KEY="{pem}"')
    print(f"MCP_LOGIN_CSRF_SECRET={secrets.token_hex(32)}")
    print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"MCP_METRICS_TOKEN={secrets.token_urlsafe(32)}")


if __name__ == "__main__":
    main()
