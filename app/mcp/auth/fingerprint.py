"""Bind ChatGPT grants to the user's current password.

``users.token_version`` is bumped by /change-password and
/password-reset/confirm, but /reset-password bumps it best-effort after
committing the new password (a failure is logged and ignored), and future
password paths may forget it. The fingerprint closes that class of gap without
touching the mobile auth code: any change to ``users.password_hash`` changes
the fingerprint, and every code, refresh token and access token carries the
fingerprint it was issued under.

HMAC-SHA256 keyed by a key derived from MCP_GRANT_FINGERPRINT_SECRET (used
for nothing else), so the value in a JWT says nothing about the bcrypt hash.
Rotating that secret revokes every ChatGPT grant; rotating the login CSRF
secret does not.
"""

from __future__ import annotations

import hashlib
import hmac

CREDENTIAL_CLAIM = "cfp"


def fingerprint_key(secret: str) -> bytes:
    return hashlib.sha256(b"mita-mcp-credential:" + secret.encode()).digest()


def credential_fingerprint(key: bytes, password_hash: str | None) -> str:
    return hmac.new(key, (password_hash or "").encode(), hashlib.sha256).hexdigest()


def same_fingerprint(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a, b)
