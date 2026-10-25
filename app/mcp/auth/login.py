"""MITA sign-in, sign-up and consent page for the ChatGPT OAuth flow (``/oauth/login``).

No JavaScript. Two modes on one page: **Sign in** (existing account) and
**Create account** (``?mode=register``). Either one ends by issuing the
authorization code for the pending request to the account just verified or
created, and redirects straight back to ChatGPT. This module owns the flow;
what the person sees is ``app/mcp/auth/pages.py``. Protections:

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

A database or network failure answers 503 with a page that says so and keeps
the pending request (never a code); only the exception's class is logged,
because a driver error's text can carry the statement's parameters.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode, urlparse

from mcp.server.auth.provider import construct_redirect_uri
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.core.email_policy import normalize_email
from app.core.password_policy import password_policy_violation
from app.core.password_security import hash_password_async
from app.db.models import McpUserProfile, User
from app.mcp.analytics import Analytics
from app.mcp.auth import pages
from app.mcp.auth.pages import MAX_FIELD, REGISTER, UNAVAILABLE, UNAVAILABLE_TITLE
from app.mcp.auth.provider import MitaAuthorizationProvider
from app.mcp.config import McpSettings
from app.mcp.observability import subject_hash
from app.mcp.ratelimit import SlidingWindowLimiter, client_ip_from_headers
from app.services.credential_verification import verify_login_credentials
from app.services.user_registration import COUNTRY_NOT_STATED, build_password_user

logger = logging.getLogger("app.mcp.oauth")

CSRF_COOKIE = "__Host-mita_oauth_csrf"

# One message for every sign-in failure: it must not reveal whether an
# account exists or is locked (a lock happens only for real accounts).
GENERIC_FAILURE = (
    "Sign-in failed. Check your email and password and try again. After "
    "several failed attempts, sign-in is paused for 30 minutes."
)
# The only sign-up failure that is not about the form itself. Without e-mail
# verification a taken address cannot be hidden completely (the mobile
# /register says so outright); this page does not add detail to that.
REGISTRATION_FAILED = (
    "We couldn’t create an account with these details. If you already have a "
    "MITA account, sign in instead."
)
INVALID_EMAIL = "Enter a valid email address."
PASSWORD_MISMATCH = "The passwords do not match. Type the same password twice."
RATE_LIMITED = (
    "Too many sign-in attempts from this network. Wait a minute and try again."
)
REGISTRATION_RATE_LIMITED = (
    "Too many new accounts from this network. Try again later, or sign in to an "
    "existing account."
)
EXPIRED_TITLE = "This sign-in link has expired"
# Failures of the database or the network beneath it, not of the request
# (asyncio timeouts are TimeoutError, an OSError).
UNAVAILABLE_ERRORS = (SQLAlchemyError, OSError)


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
        return pages.security_headers(redirect_uri)

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
        error_field: Optional[str] = None,
        email: str = "",
        usage_stats: bool = False,
        status_code: int = 200,
    ) -> HTMLResponse:
        view = pages.LoginView(
            req=req,
            csrf=self._csrf_token(cookie, req),
            client_name=client_name,
            redirect_host=urlparse(pending["redirect_uri"]).netloc,
            scopes=tuple(pending["scopes"]),
            register=mode == REGISTER,
            email=email,
            error=error,
            error_field=error_field,
            usage_stats=usage_stats,
            support_url=self.settings.support_url,
        )
        response = HTMLResponse(
            pages.login_page(view),
            status_code=status_code,
            headers=self._headers(pending["redirect_uri"]),
        )
        self._set_cookie(response, cookie)
        return response

    def _expired(self) -> HTMLResponse:
        minutes = max(1, self.settings.pending_authorization_ttl_seconds // 60)
        return HTMLResponse(
            pages.problem_page(
                EXPIRED_TITLE,
                f"For your security, MITA sign-in links work for {minutes} minutes "
                "and only in the browser where you opened them. Return to "
                "ChatGPT and connect MITA again.",
                icon_name="clock",
                support_url=self.settings.support_url,
            ),
            status_code=400,
            headers=self._headers(),
        )

    def _unavailable(
        self, exc: BaseException, req: str = "", register: bool = False
    ) -> HTMLResponse:
        logger.error(
            "oauth login unavailable",
            extra={
                "event": "oauth_login_unavailable",
                "error_class": type(exc).__name__,
            },
        )
        retry = None
        if req:
            query = {"req": req, **({"mode": REGISTER} if register else {})}
            retry = f"{pages.LOGIN_PATH}?{urlencode(query)}"
        return HTMLResponse(
            pages.problem_page(
                UNAVAILABLE_TITLE,
                UNAVAILABLE,
                icon_name="clock",
                retry_url=retry,
                support_url=self.settings.support_url,
            ),
            status_code=503,
            headers={**self._headers(), "Retry-After": "30"},
        )

    async def _client_name(self, client_id: str) -> Optional[str]:
        client = await self.provider.get_client(client_id)
        if client is None:
            return None
        return (client.client_name or "ChatGPT")[:100]

    async def _record_usage_choice(
        self, session, user_id, ticked: bool, *, new_account: bool
    ) -> bool:
        """Store this page's usage-statistics answer; return the consent in force.

        The box starts unticked and ticking it is the consent. On sign-in an
        unticked box is not a withdrawal: the account keeps the choice it made
        before, and nothing is deleted (withdrawing is set_usage_analytics(false)
        in ChatGPT, which deletes the linked statistics). A new account that
        leaves it unticked is recorded as "no".
        """
        profile = await session.get(McpUserProfile, user_id)
        if not ticked and not new_account:
            return bool(profile is not None and profile.usage_analytics_enabled)
        now = datetime.now(timezone.utc)
        if profile is None:
            session.add(
                McpUserProfile(
                    user_id=user_id,
                    usage_analytics_enabled=ticked,
                    usage_analytics_updated_at=now,
                )
            )
        elif profile.usage_analytics_enabled != ticked:
            profile.usage_analytics_enabled = ticked
            profile.usage_analytics_updated_at = now
        return ticked

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
        try:
            return await self._get(request)
        except UNAVAILABLE_ERRORS as exc:
            return self._unavailable(
                exc,
                getattr(request.state, "mita_req", ""),
                request.query_params.get("mode") == REGISTER,
            )

    async def post(self, request: Request) -> Response:
        try:
            return await self._post(request)
        except UNAVAILABLE_ERRORS as exc:
            return self._unavailable(
                exc,
                getattr(request.state, "mita_req", ""),
                getattr(request.state, "mita_register", False),
            )

    async def _get(self, request: Request) -> Response:
        req = request.query_params.get("req", "")
        pending = self.provider.pending.decode(req)
        if pending is None:
            return self._expired()
        request.state.mita_req = req  # verified: safe to offer "Try again" with it
        name = await self._client_name(pending["client_id"])
        if name is None:
            return self._expired()
        cookie = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
        mode = REGISTER if request.query_params.get("mode") == REGISTER else ""
        return self._render(
            req=req, pending=pending, client_name=name, cookie=cookie, mode=mode
        )

    async def _post(self, request: Request) -> Response:
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
        request.state.mita_req = req
        request.state.mita_register = form.get("action") == REGISTER
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

        def fail(
            message: str, status_code: int, field: Optional[str] = None
        ) -> HTMLResponse:
            return self._render(
                req=req,
                pending=pending,
                client_name=name,
                cookie=cookie,
                mode=REGISTER if register else "",
                error=message,
                error_field=field,
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
            return fail(GENERIC_FAILURE, 400, "credentials")

        consent = False
        async with self.session_scope() as session:
            check = await verify_login_credentials(session, email, password)
            user = check.user
            if check.ok:
                consent = await self._record_usage_choice(
                    session, user.id, usage_stats, new_account=False
                )

        if not check.ok:
            logger.info(
                "oauth login failed",
                extra={
                    "event": "oauth_login_failed",
                    "reason": check.outcome.value,
                    "subject_hash": subject_hash(user.id) if user else None,
                },
            )
            return fail(GENERIC_FAILURE, 400, "credentials")

        response = await self._issue_code(pending, user)
        self.analytics.milestone(
            "oauth_connected",
            user_id=user.id,
            consent=consent,
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
            return fail(INVALID_EMAIL, 400, "email")
        problem = password_policy_violation(password)
        if problem:
            return fail(problem + ".", 400, "password")
        if not hmac.compare_digest(password.encode(), password_confirm.encode()):
            return fail(PASSWORD_MISMATCH, 400, "password_confirm")
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
                    await self._record_usage_choice(
                        session, user.id, usage_stats, new_account=True
                    )
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
