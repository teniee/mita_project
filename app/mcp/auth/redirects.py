"""Redirect-URI policy for dynamic client registration.

Exact matching only. An allowed entry is either a complete URI (matched
character for character) or a base ending in "/" followed by exactly ONE path
segment of ``[A-Za-z0-9_-]`` (ChatGPT's per-connection callback id). Anything
with userinfo, a port, a query, a fragment, percent-encoding, backslashes, dot
segments or extra path segments is refused, so a registered URI can never be
turned into a redirect to another path or host (OAuth 2.0 Security BCP:
exact string matching for redirect URIs).
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlsplit

CALLBACK_SEGMENT = re.compile(r"[A-Za-z0-9_-]{1,128}")
_FORBIDDEN_CHARS = set("%\\@ \t\r\n#?")


def redirect_uri_allowed(uri: str, allowed: Iterable[str]) -> bool:
    if not uri or any(ch in _FORBIDDEN_CHARS for ch in uri):
        return False
    parts = urlsplit(uri)
    if parts.query or parts.fragment or parts.username or parts.password:
        return False
    if "/." in parts.path or "//" in parts.path:
        return False
    for entry in allowed:
        if not entry.endswith("/"):
            if uri == entry:
                return True
            continue
        if uri.startswith(entry) and CALLBACK_SEGMENT.fullmatch(uri[len(entry) :]):
            return True
    return False
