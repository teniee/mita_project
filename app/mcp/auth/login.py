"""MITA sign-in, sign-up and consent page for the ChatGPT OAuth flow (``/oauth/login``).

No JavaScript. Two modes on one page: **Sign in** (existing account) and
**Create account** (``?mode=register``). Either one ends by issuing the
authorization code for the pending request to the account just verified or
created. Protections:

* the pending authorization request is HMAC-signed and expires (provider);
* CSRF: a random ``__Host-`` cookie set on GET, and a form token that is an
  HMAC of that cookie and the pending request — a cross-site POST carries
  neither (``SameSite=Strict``);
* sign-in goes through the same lockout as the mobile login
  (``app/services/credential_verification.py``) plus a per-IP rate limit;
* sign-up reuses the API's account rules (``app/core/email_policy.py``,
  ``app/core/password_policy.py``, ``app/services/user_registration.py``),
  is limited per IP per hour, hashes the password BEFORE looking the address
  up (no timing difference between a new and a taken address), and answers a
  taken address with one generic message;
* ``frame-ancestors 'none'`` against clickjacking, ``no-store`` caching,
  ``no-referrer``; all client-supplied text is HTML-escaped; no e-mail
  address, password or token is ever logged.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse

from mcp.server.auth.provider import construct_redirect_uri
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.core.email_policy import normalize_email
from app.core.password_policy import password_policy_violation
from app.core.password_security import hash_password_async
from app.db.models import McpUserProfile, User
from app.mcp.analytics import Analytics
from app.mcp.auth.provider import MitaAuthorizationProvider
from app.mcp.auth.scopes import SCOPE_DESCRIPTIONS
from app.mcp.config import McpSettings
from app.mcp.observability import subject_hash
from app.mcp.ratelimit import SlidingWindowLimiter, client_ip_from_headers
from app.services.credential_verification import verify_login_credentials
from app.services.user_registration import COUNTRY_NOT_STATED, build_password_user

logger = logging.getLogger("app.mcp.oauth")

CSRF_COOKIE = "__Host-mita_oauth_csrf"
MAX_FIELD = 320
REGISTER = "register"

# One message for every sign-in failure: it must not reveal whether an
# account exists or is locked (a lock happens only for real accounts).
GENERIC_FAILURE = (
    "Sign-in failed. Check your e-mail and password. After several failed "
    "attempts sign-in is paused for 30 minutes."
)
# The only sign-up failure that is not about the form itself. Without e-mail
# verification a taken address cannot be hidden completely (the mobile
# /register says so outright); this page does not add detail to that.
REGISTRATION_FAILED = (
    "We could not create an account with these details. If you already have a "
    "MITA account, choose Sign in instead."
)
INVALID_EMAIL = "Enter a valid e-mail address."
PASSWORD_MISMATCH = "The two passwords do not match."
RATE_LIMITED = (
    "Too many sign-in attempts from this network. Wait a minute and try again."
)
REGISTRATION_RATE_LIMITED = (
    "Too many new accounts from this network. Try again later, or sign in to an "
    "existing account."
)
EXPIRED = "This sign-in link has expired. Return to ChatGPT and connect MITA again."

USAGE_STATS_LABEL = (
    "Help improve MITA: record which MITA features I use. MITA never records "
    "my conversations, amounts or merchant names. I can turn this off at any time."
)


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
        *,
        registration_limiter: Optional[SlidingWindowLimiter] = None,
        analytics: Optional[Analytics] = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.limiter = limiter
        self.registration_limiter = registration_limiter or SlidingWindowLimiter(
            settings.registrations_per_hour, window_seconds=3600
        )
        self.session_scope = session_scope
        self.analytics = analytics or Analytics(settings.analytics_secret)
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
        mode: str = "",
        error: Optional[str] = None,
        email: str = "",
        usage_stats: bool = True,
        status_code: int = 200,
    ) -> HTMLResponse:
        e = html.escape
        register = mode == REGISTER
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
        switch_query = urlencode(
            {"req": req, **({} if register else {"mode": REGISTER})}
        )
        if register:
            heading = f"Create a MITA account for {e(client_name)}"
            switch = (
                f'<p class="fine">Already have a MITA account? '
                f'<a href="/oauth/login?{e(switch_query)}">Sign in</a></p>'
            )
            fields = f"""<input type="hidden" name="mode" value="{REGISTER}">
<label for="email">E-mail</label>
<input id="email" name="email" type="email" required maxlength="{MAX_FIELD}" value="{e(email)}" autocomplete="username">
<label for="password">Password</label>
<input id="password" name="password" type="password" required maxlength="128" autocomplete="new-password">
<p class="fine">At least 8 characters, with upper- and lower-case letters, a number and a symbol.</p>
<label for="password_confirm">Repeat password</label>
<input id="password_confirm" name="password_confirm" type="password" required maxlength="128" autocomplete="new-password">"""
            allow_label = "Create account and connect"
            allow_value = REGISTER
        else:
            heading = f"Connect MITA to {e(client_name)}"
            switch = (
                f'<p class="fine">New to MITA? '
                f'<a href="/oauth/login?{e(switch_query)}">Create an account</a></p>'
            )
            fields = f"""<label for="email">MITA e-mail</label>
<input id="email" name="email" type="email" required maxlength="{MAX_FIELD}" value="{e(email)}" autocomplete="username">
<label for="password">MITA password</label>
<input id="password" name="password" type="password" required maxlength="{MAX_FIELD}" autocomplete="current-password">"""
            allow_label = "Sign in and connect"
            allow_value = "allow"
        checked = " checked" if usage_stats else ""
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Connect MITA</title>
<style>
:root{{--navy:#193C57;--bg:#FFF8F0;--line:rgba(25,60,87,.18)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--navy);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
main{{max-width:440px;margin:40px auto;padding:0 16px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px}}
h1{{font-size:1.3rem;margin:0 0 8px}}ul{{padding-left:20px}}label{{display:block;margin:14px 0 4px;font-weight:600}}
input[type=email],input[type=password]{{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;font:inherit}}
.check{{display:flex;gap:8px;align-items:flex-start;margin-top:16px;font-weight:400;font-size:.9rem}}
.check input{{margin-top:4px}}
.row{{display:flex;gap:10px;margin-top:20px}}button{{flex:1;padding:11px;border-radius:8px;font:inherit;font-weight:600;border:1px solid var(--navy);cursor:pointer}}
.allow{{background:var(--navy);color:#FFD25F}}.deny{{background:#fff;color:var(--navy)}}
.warn{{background:#fff4d6;padding:10px 12px;border-radius:8px;font-size:.9rem}}
.err{{background:#fdecea;color:#8a1c12;padding:10px 12px;border-radius:8px}}.fine{{font-size:.85rem;opacity:.85}}
</style></head><body><main><div class="card">
<h1>{heading}</h1>
<p><strong>{e(client_name)}</strong> is asking for access to your MITA account. It will be able to:</p>
<ul>{scope_items}</ul>
<p class="fine">MITA cannot move money, make payments or connect to your bank. Your MITA data stays in your MITA account and is available in every future conversation. You can disconnect at any time in ChatGPT. After you continue you will be returned to <strong>{e(redirect_host)}</strong>.</p>
<p class="warn"><strong>Only continue if you just chose to connect MITA in your own ChatGPT account.</strong> If someone sent you this link, press Cancel — approving it could give their ChatGPT access to your MITA data.</p>
{error_html}
<form method="post" action="/oauth/login" autocomplete="on">
<input type="hidden" name="req" value="{e(req)}">
<input type="hidden" name="csrf" value="{e(self._csrf_token(cookie, req))}">
{fields}
<label class="check"><input type="checkbox" name="usage_stats" value="1"{checked}> <span>{e(USAGE_STATS_LABEL)}</span></label>
<div class="row"><button class="deny" type="submit" name="action" value="deny" formnovalidate>Cancel</button>
<button class="allow" type="submit" name="action" value="{allow_value}">{allow_label}</button></div>
</form>{switch}{support}
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

    async def _record_usage_choice(self, session, user_id, enabled: bool) -> None:
        """Store the checkbox answer given on this page for this account."""
        now = datetime.now(timezone.utc)
        profile = await session.get(McpUserProfile, user_id)
        if profile is None:
            session.add(
                McpUserProfile(
                    user_id=user_id,
                    usage_analytics_enabled=enabled,
                    usage_analytics_updated_at=now,
                )
            )
        elif profile.usage_analytics_enabled != enabled:
            profile.usage_analytics_enabled = enabled
            profile.usage_analytics_updated_at = now

    async def _issue_code(self, pending: dict, user: User) -> Response:
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
        mode = REGISTER if request.query_params.get("mode") == REGISTER else ""
        return self._render(
            req=req, pending=pending, client_name=name, cookie=cookie, mode=mode
        )

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

        action = form.get("action")
        if action == "deny":
            return RedirectResponse(
                construct_redirect_uri(
                    pending["redirect_uri"],
                    error="access_denied",
                    state=pending.get("state"),
                ),
                status_code=302,
                headers=self._headers(pending["redirect_uri"]),
            )

        register = action == REGISTER
        raw_email = str(form.get("email", ""))[:MAX_FIELD]
        email = raw_email.strip().lower()
        password = str(form.get("password", ""))[:MAX_FIELD]
        usage_stats = form.get("usage_stats") == "1"

        def fail(message: str, status_code: int) -> HTMLResponse:
            return self._render(
                req=req,
                pending=pending,
                client_name=name,
                cookie=cookie,
                mode=REGISTER if register else "",
                error=message,
                email=email,
                usage_stats=usage_stats,
                status_code=status_code,
            )

        ip = client_ip(request, self.settings.trusted_proxy_hops)
        if not self.limiter.allow(ip):
            logger.warning(
                "oauth login rate limited", extra={"event": "oauth_login_rate_limited"}
            )
            return fail(RATE_LIMITED, 429)

        if register:
            return await self._register(
                pending,
                fail=fail,
                ip=ip,
                email=email,
                password=password,
                password_confirm=str(form.get("password_confirm", ""))[:MAX_FIELD],
                usage_stats=usage_stats,
            )

        if "@" not in email or not password:
            return fail(GENERIC_FAILURE, 400)

        async with self.session_scope() as session:
            check = await verify_login_credentials(session, email, password)
            user = check.user
            if check.ok:
                await self._record_usage_choice(session, user.id, usage_stats)

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

        response = await self._issue_code(pending, user)
        self.analytics.milestone(
            "oauth_connected",
            user_id=user.id,
            consent=usage_stats,
            properties={"new_account": False},
        )
        return response

    async def _register(
        self,
        pending: dict,
        *,
        fail,
        ip: str,
        email: str,
        password: str,
        password_confirm: str,
        usage_stats: bool,
    ) -> Response:
        normalized = normalize_email(email)
        if normalized is None:
            return fail(INVALID_EMAIL, 400)
        problem = password_policy_violation(password)
        if problem:
            return fail(problem + ".", 400)
        if not hmac.compare_digest(password.encode(), password_confirm.encode()):
            return fail(PASSWORD_MISMATCH, 400)
        # Counted only once the form is valid: typos are free, probing is not.
        if not self.registration_limiter.allow(ip):
            logger.warning(
                "oauth registration rate limited",
                extra={"event": "oauth_registration_rate_limited"},
            )
            return fail(REGISTRATION_RATE_LIMITED, 429)

        # Hash first: a taken address must cost the same time as a new one.
        password_hash = await hash_password_async(password)

        user: Optional[User] = None
        try:
            async with self.session_scope() as session:
                taken = await session.scalar(
                    select(User.id).where(User.email == normalized)
                )
                if taken is None:
                    user = build_password_user(
                        email=normalized,
                        password_hash=password_hash,
                        country=COUNTRY_NOT_STATED,
                    )
                    session.add(user)
                    await session.flush()
                    await self._record_usage_choice(session, user.id, usage_stats)
        except IntegrityError:
            user = None  # lost a race with a concurrent sign-up for the same address

        if user is None:
            logger.info(
                "oauth registration refused",
                extra={"event": "oauth_registration_refused", "reason": "taken"},
            )
            return fail(REGISTRATION_FAILED, 400)

        logger.info(
            "oauth account created",
            extra={
                "event": "oauth_account_created",
                "subject_hash": subject_hash(user.id),
            },
        )
        response = await self._issue_code(pending, user)
        self.analytics.milestone(
            "account_created", user_id=user.id, consent=usage_stats
        )
        self.analytics.milestone(
            "oauth_connected",
            user_id=user.id,
            consent=usage_stats,
            properties={"new_account": True},
        )
        return response
