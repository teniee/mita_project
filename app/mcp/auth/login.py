"""MITA sign-in and consent page for the ChatGPT OAuth flow (``/oauth/login``).

No JavaScript. Protections:

* the pending authorization request is HMAC-signed and expires (provider);
* CSRF: a random ``__Host-`` cookie set on GET, and a form token that is an
  HMAC of that cookie and the pending request — a cross-site POST carries
  neither (``SameSite=Strict``);
* credentials go through the same lockout as the mobile login
  (``app/services/credential_verification.py``) plus a per-IP rate limit;
* ``frame-ancestors 'none'`` against clickjacking, ``no-store`` caching,
  ``no-referrer``; all client-supplied text is HTML-escaped.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import logging
import secrets
from typing import Optional
from urllib.parse import urlparse

from mcp.server.auth.provider import construct_redirect_uri
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.mcp.auth.provider import MitaAuthorizationProvider
from app.mcp.auth.scopes import SCOPE_DESCRIPTIONS
from app.mcp.config import McpSettings
from app.mcp.observability import subject_hash
from app.mcp.ratelimit import SlidingWindowLimiter, client_ip_from_headers
from app.services.credential_verification import verify_login_credentials

logger = logging.getLogger("app.mcp.oauth")

CSRF_COOKIE = "__Host-mita_oauth_csrf"
MAX_FIELD = 320

# One message for every failure: it must not reveal whether an account exists
# or is locked (a lock happens only for real accounts).
GENERIC_FAILURE = (
    "Sign-in failed. Check your e-mail and password. After several failed "
    "attempts sign-in is paused for 30 minutes."
)
RATE_LIMITED = (
    "Too many sign-in attempts from this network. Wait a minute and try again."
)
EXPIRED = "This sign-in link has expired. Return to ChatGPT and connect MITA again."


def client_ip(request: Request, trusted_hops: int) -> str:
    return client_ip_from_headers(
        request.headers.get("x-forwarded-for", ""),
        request.client.host if request.client else None,
        trusted_hops,
    )


class ConsentPage:
    def __init__(
        self,
        settings: McpSettings,
        provider: MitaAuthorizationProvider,
        limiter: SlidingWindowLimiter,
        session_scope,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.limiter = limiter
        self.session_scope = session_scope
        self._csrf_key = hashlib.sha256(
            b"mita-mcp-csrf:" + settings.login_csrf_secret.encode()
        ).digest()

    # --- helpers -----------------------------------------------------------

    def _csrf_token(self, cookie: str, req: str) -> str:
        return hmac.new(
            self._csrf_key, f"{cookie}|{req}".encode(), hashlib.sha256
        ).hexdigest()

    def _headers(self, redirect_uri: Optional[str] = None) -> dict:
        form_action = "'self'"
        if redirect_uri:
            parsed = urlparse(redirect_uri)
            form_action += f" {parsed.scheme}://{parsed.netloc}"
        return {
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
                f"form-action {form_action}; frame-ancestors 'none'; base-uri 'none'"
            ),
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
        }

    def _set_cookie(self, response: Response, value: str) -> None:
        response.set_cookie(
            CSRF_COOKIE,
            value,
            max_age=self.settings.pending_authorization_ttl_seconds,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )

    def _render(
        self,
        *,
        req: str,
        pending: dict,
        client_name: str,
        cookie: str,
        error: Optional[str] = None,
        email: str = "",
        status_code: int = 200,
    ) -> HTMLResponse:
        e = html.escape
        redirect_host = urlparse(pending["redirect_uri"]).netloc
        scope_items = "".join(
            f"<li>{e(SCOPE_DESCRIPTIONS.get(s, s))}</li>" for s in pending["scopes"]
        )
        error_html = f'<p class="err" role="alert">{e(error)}</p>' if error else ""
        support = (
            f'<p class="fine">Help: <a href="{e(self.settings.support_url)}">{e(self.settings.support_url)}</a></p>'
            if self.settings.support_url
            else ""
        )
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect MITA</title>
<style>
:root{{--navy:#193C57;--bg:#FFF8F0;--line:rgba(25,60,87,.18)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--navy);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
main{{max-width:420px;margin:40px auto;padding:0 16px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px}}
h1{{font-size:1.3rem;margin:0 0 8px}}ul{{padding-left:20px}}label{{display:block;margin:14px 0 4px;font-weight:600}}
input{{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;font:inherit}}
.row{{display:flex;gap:10px;margin-top:20px}}button{{flex:1;padding:11px;border-radius:8px;font:inherit;font-weight:600;border:1px solid var(--navy);cursor:pointer}}
.allow{{background:var(--navy);color:#FFD25F}}.deny{{background:#fff;color:var(--navy)}}
.warn{{background:#fff4d6;padding:10px 12px;border-radius:8px;font-size:.9rem}}
.err{{background:#fdecea;color:#8a1c12;padding:10px 12px;border-radius:8px}}.fine{{font-size:.85rem;opacity:.8}}
</style></head><body><main><div class="card">
<h1>Connect MITA to {e(client_name)}</h1>
<p><strong>{e(client_name)}</strong> is asking for read-only access to your MITA account. It will be able to:</p>
<ul>{scope_items}</ul>
<p class="fine">It cannot add, change or delete anything, move money or make payments. You can disconnect at any time in ChatGPT. After you continue you will be returned to <strong>{e(redirect_host)}</strong>.</p>
<p class="warn"><strong>Only continue if you just chose to connect MITA in your own ChatGPT account.</strong> If someone sent you this link, press Cancel — approving it could give their ChatGPT access to your MITA data.</p>
{error_html}
<form method="post" action="/oauth/login" autocomplete="on">
<input type="hidden" name="req" value="{e(req)}">
<input type="hidden" name="csrf" value="{e(self._csrf_token(cookie, req))}">
<label for="email">MITA e-mail</label>
<input id="email" name="email" type="email" required maxlength="{MAX_FIELD}" value="{e(email)}" autocomplete="username">
<label for="password">MITA password</label>
<input id="password" name="password" type="password" required maxlength="{MAX_FIELD}" autocomplete="current-password">
<div class="row"><button class="deny" type="submit" name="action" value="deny" formnovalidate>Cancel</button>
<button class="allow" type="submit" name="action" value="allow">Allow read-only access</button></div>
</form>{support}
</div></main></body></html>"""
        response = HTMLResponse(
            body,
            status_code=status_code,
            headers=self._headers(pending["redirect_uri"]),
        )
        self._set_cookie(response, cookie)
        return response

    def _expired(self) -> HTMLResponse:
        return HTMLResponse(
            f"<!doctype html><meta charset=utf-8><title>Connect MITA</title><p>{html.escape(EXPIRED)}</p>",
            status_code=400,
            headers=self._headers(),
        )

    async def _client_name(self, client_id: str) -> Optional[str]:
        client = await self.provider.get_client(client_id)
        if client is None:
            return None
        return (client.client_name or "ChatGPT")[:100]

    # --- handlers ----------------------------------------------------------

    async def get(self, request: Request) -> Response:
        req = request.query_params.get("req", "")
        pending = self.provider.pending.decode(req)
        if pending is None:
            return self._expired()
        name = await self._client_name(pending["client_id"])
        if name is None:
            return self._expired()
        cookie = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
        return self._render(req=req, pending=pending, client_name=name, cookie=cookie)

    async def post(self, request: Request) -> Response:
        form = await request.form()
        req = str(form.get("req", ""))[:4096]
        pending = self.provider.pending.decode(req)
        if pending is None:
            return self._expired()
        cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf = str(form.get("csrf", ""))
        if not cookie or not hmac.compare_digest(csrf, self._csrf_token(cookie, req)):
            logger.warning(
                "oauth csrf rejected", extra={"event": "oauth_csrf_rejected"}
            )
            return self._expired()
        name = await self._client_name(pending["client_id"])
        if name is None:
            return self._expired()

        if form.get("action") == "deny":
            return RedirectResponse(
                construct_redirect_uri(
                    pending["redirect_uri"],
                    error="access_denied",
                    state=pending.get("state"),
                ),
                status_code=302,
                headers=self._headers(pending["redirect_uri"]),
            )

        email = str(form.get("email", "")).strip().lower()[:MAX_FIELD]
        password = str(form.get("password", ""))[:MAX_FIELD]

        def fail(message: str, status_code: int) -> HTMLResponse:
            return self._render(
                req=req,
                pending=pending,
                client_name=name,
                cookie=cookie,
                error=message,
                email=email,
                status_code=status_code,
            )

        if not self.limiter.allow(client_ip(request, self.settings.trusted_proxy_hops)):
            logger.warning(
                "oauth login rate limited", extra={"event": "oauth_login_rate_limited"}
            )
            return fail(RATE_LIMITED, 429)
        if "@" not in email or not password:
            return fail(GENERIC_FAILURE, 400)

        async with self.session_scope() as session:
            check = await verify_login_credentials(session, email, password)
            user = check.user

        if not check.ok:
            logger.info(
                "oauth login failed",
                extra={
                    "event": "oauth_login_failed",
                    "reason": check.outcome.value,
                    "subject_hash": subject_hash(user.id) if user else None,
                },
            )
            return fail(GENERIC_FAILURE, 400)

        code = await self.provider.create_authorization_code(pending, user)
        response = RedirectResponse(
            construct_redirect_uri(
                pending["redirect_uri"], code=code, state=pending.get("state")
            ),
            status_code=302,
            headers=self._headers(pending["redirect_uri"]),
        )
        response.delete_cookie(
            CSRF_COOKIE, path="/", secure=True, httponly=True, samesite="strict"
        )
        return response
