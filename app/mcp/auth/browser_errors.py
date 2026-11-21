"""A page, not JSON, for a person whose browser lands on a refused
``/authorize`` request.

When the SDK cannot send an error back to ChatGPT — unknown client, a
redirect URI it does not trust — it answers 400 with an OAuth JSON body;
``OAuthEndpointRateLimit`` answers 429 the same way. RFC 6749 §4.1.2.1 says to
inform the resource owner and never redirect to an unverified URI, and a
browser would show them raw ``{"error": "invalid_request", ...}``.

This wrapper changes only the presentation, only for browser navigations
(``Accept`` names ``text/html``) and only for those two statuses with a JSON
body: the status, ``Retry-After`` and every protocol decision stay exactly as
the SDK made them. Redirects (codes and errors for ChatGPT) and every other
path pass through untouched. The page never echoes the request or the SDK's
``error_description`` (it can quote the client id or redirect URI); it names
the error code only if the code is one OAuth defines.
"""

from __future__ import annotations

import json
from typing import Optional

from app.mcp.auth import pages

AUTHORIZE_PATH = "/authorize"
_STATUSES = (400, 429)
_KNOWN_CODES = frozenset(
    {
        "invalid_request",
        "unauthorized_client",
        "access_denied",
        "unsupported_response_type",
        "invalid_scope",
        "server_error",
        "temporarily_unavailable",
        "invalid_target",
        "rate_limited",
    }
)


def _header(headers, name: bytes) -> Optional[bytes]:
    for key, value in headers or ():
        if key.lower() == name:
            return value
    return None


def wants_html(scope) -> bool:
    accept = _header(scope.get("headers"), b"accept") or b""
    return b"text/html" in accept.lower()


def _page(status: int, body: bytes) -> str:
    try:
        code = json.loads(body).get("error")
    except (ValueError, AttributeError):
        code = None
    if code not in _KNOWN_CODES:
        code = None
    if status == 429 or code == "rate_limited":
        return pages.problem_page(
            "Too many connection attempts",
            "Wait a minute, then return to ChatGPT and try connecting MITA again.",
            icon_name="clock",
            reference=code,
        )
    if code in ("server_error", "temporarily_unavailable"):
        return pages.problem_page(
            "MITA is temporarily unavailable",
            "Nothing was connected. Return to ChatGPT and try connecting MITA "
            "again in a moment.",
            icon_name="clock",
            reference=code,
        )
    return pages.problem_page(
        "We couldn’t continue this connection",
        "Please return to ChatGPT and try connecting MITA again.",
        icon_name="info",
        reference=code,
    )


class BrowserAuthorizeErrors:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("path") != AUTHORIZE_PATH
            or not wants_html(scope)
        ):
            await self.app(scope, receive, send)
            return

        held: dict = {}
        chunks: list = []

        async def intercept(message) -> None:
            if message["type"] == "http.response.start":
                content_type = _header(message.get("headers"), b"content-type") or b""
                if message["status"] in _STATUSES and content_type.startswith(
                    b"application/json"
                ):
                    held["start"] = message
                    return
                await send(message)
                return
            if message["type"] == "http.response.body" and "start" in held:
                chunks.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                await self._send_page(send, held["start"], b"".join(chunks))
                return
            await send(message)

        await self.app(scope, receive, intercept)

    @staticmethod
    async def _send_page(send, start, body: bytes) -> None:
        status = start["status"]
        page = _page(status, body).encode()
        headers = [
            (name.lower().encode(), value.encode())
            for name, value in pages.security_headers().items()
        ]
        retry_after = _header(start.get("headers"), b"retry-after")
        if retry_after:
            headers.append((b"retry-after", retry_after))
        headers += [
            (b"content-type", b"text/html; charset=utf-8"),
            (b"content-length", str(len(page)).encode()),
        ]
        await send(
            {"type": "http.response.start", "status": status, "headers": headers}
        )
        await send({"type": "http.response.body", "body": page})
