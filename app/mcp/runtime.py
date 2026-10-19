"""Execution of one tool call: identity → scope → rate limit → query or write.

Every tool goes through ``McpRuntime.execute`` (read) or
``McpRuntime.execute_write``. The tool body receives the authenticated user's
``UserContext`` — derived from the bearer token and the database, never from
tool arguments.

* Read bodies are synchronous ``(Session, UserContext) -> BaseModel`` and run
  inside a ``READ ONLY`` transaction that is always rolled back.
* Write bodies are ``async (AsyncSession, UserContext, WriteCall) -> BaseModel``
  and run in a read-write session from ``write_scope``. The body commits its
  unit of work itself; anything it did not commit is rolled back when the
  scope closes, so a failure can never leave half a write behind.

After the call, one analytics record is queued (``app/mcp/analytics.py``) —
out of band, never able to change the result.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp_types import CallToolResult, TextContent
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import User
from app.mcp.analytics import Analytics, CallTelemetry, bind_call, unbind_call
from app.mcp.auth.fingerprint import (
    CREDENTIAL_CLAIM,
    credential_fingerprint,
    fingerprint_key,
    same_fingerprint,
)
from app.mcp.auth.tokens import TOKEN_VERSION_CLAIM
from app.mcp.config import McpSettings
from app.mcp.crypto import DataKeys
from app.mcp.db import SessionScope
from app.mcp.errors import (
    INTERNAL_MESSAGE,
    UNAVAILABLE_MESSAGE,
    AuthError,
    ErrorCategory,
    ForbiddenError,
    InternalError,
    McpToolError,
    RateLimitedError,
    UnavailableError,
)
from app.mcp.observability import log_tool_call, metrics
from app.mcp.queries.periods import UserContext, load_user_context
from app.mcp.ratelimit import SlidingWindowLimiter

logger = logging.getLogger("app.mcp.tools")

ToolBody = Callable[[Session, UserContext], BaseModel]

# Write sessions get a longer statement budget than reads: a write rebuilds
# the month's plan under the per-user ledger lock.
WRITE_STATEMENT_TIMEOUT_MS = 10000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WriteCall:
    """What a write body may know about the request besides the user."""

    tool: str
    # sha256 of ChatGPT's anonymized conversation id (``_meta["openai/session"]``),
    # or "-" when the client sends none. Scopes idempotency keys; never stored raw.
    session_digest: str
    data_keys: DataKeys
    now: datetime


WriteBody = Callable[[AsyncSession, UserContext, WriteCall], Awaitable[BaseModel]]


def _request_meta(ctx: Any) -> Dict[str, Any]:
    """``_meta`` of the tools/call request (hidden from the model)."""
    try:
        meta = ctx.request_context.meta if ctx is not None else None
    except (AttributeError, ValueError, LookupError):
        return {}
    return dict(meta) if isinstance(meta, dict) else {}


def _session_digest(meta: Dict[str, Any]) -> str:
    raw = meta.get("openai/session")
    if isinstance(raw, str) and 0 < len(raw) <= 256:
        return hashlib.sha256(raw.encode()).hexdigest()
    return "-"


@dataclass
class McpRuntime:
    settings: McpSettings
    session_scope: SessionScope
    tool_limiter: SlidingWindowLimiter
    write_scope: Optional[SessionScope] = None
    analytics: Optional[Analytics] = None
    clock: Callable[[], datetime] = field(default=_utcnow)

    def __post_init__(self) -> None:
        self._fingerprint_key = fingerprint_key(self.settings.grant_fingerprint_secret)
        self.data_keys = DataKeys(self.settings.data_secret)
        if self.analytics is None:
            self.analytics = Analytics(self.settings.analytics_secret)

    def _www_authenticate(
        self, error: str, description: str, scope: Optional[str] = None
    ) -> str:
        parts = [
            f'resource_metadata="{self.settings.resource_metadata_url}"',
            f'error="{error}"',
            f'error_description="{description}"',
        ]
        if scope:
            parts.append(f'scope="{scope}"')
        return "Bearer " + ", ".join(parts)

    def _error_result(
        self, error: McpToolError, *, scope: Optional[str] = None
    ) -> CallToolResult:
        meta = None
        if error.category is ErrorCategory.AUTH:
            meta = {
                "mcp/www_authenticate": [
                    self._www_authenticate("invalid_token", "Reconnect MITA")
                ]
            }
        elif error.category is ErrorCategory.FORBIDDEN:
            meta = {
                "mcp/www_authenticate": [
                    self._www_authenticate(
                        "insufficient_scope",
                        "Additional MITA permission required",
                        scope,
                    )
                ]
            }
        structured: Dict[str, Any] = {
            "error": {"category": error.category.value, "message": error.message}
        }
        if error.details:
            structured["error"]["details"] = error.details
        return CallToolResult(
            content=[TextContent(type="text", text=error.message)],
            structured_content=structured,
            is_error=True,
            _meta=meta,
        )

    def _authorize(
        self, session: Session, token: AccessToken, user_id: UUID
    ) -> UserContext:
        ctx = load_user_context(session, user_id, now=self.clock())
        if self.settings.auth_mode == "builtin":
            # Fail closed on any change to the account's credentials since the
            # grant: token_version (admin revoke, /change-password, reset
            # confirm) and the password itself (any path, see fingerprint.py).
            claims = token.claims or {}
            user = session.get(User, user_id)  # identity map: no extra query
            current = credential_fingerprint(self._fingerprint_key, user.password_hash)
            if claims.get(
                TOKEN_VERSION_CLAIM
            ) != ctx.token_version or not same_fingerprint(
                claims.get(CREDENTIAL_CLAIM), current
            ):
                metrics.auth_failure("revoked_grant")
                raise AuthError(
                    "Your MITA session has ended. Reconnect MITA to continue."
                )
        return ctx

    def _identify(self, required_scope: str):
        token = get_access_token()
        if token is None or token.subject is None:
            raise AuthError("Connect your MITA account to use this tool.")
        user_id = UUID(token.subject)
        if required_scope not in token.scopes:
            raise ForbiddenError(
                f"This request needs the '{required_scope}' permission, which was not granted."
            )
        if not self.tool_limiter.allow(str(user_id)):
            raise RateLimitedError(
                "Too many MITA requests in a short time. Wait a minute and try again."
            )
        return token, user_id

    @staticmethod
    def _success(model: BaseModel) -> CallToolResult:
        payload = model.model_dump(mode="json")
        return CallToolResult(
            content=[
                TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))
            ],
            structured_content=payload,
        )

    async def _run(
        self,
        tool: str,
        required_scope: str,
        work: Callable[
            [AccessToken, UUID, Dict[str, Any], Dict[str, Any]], Awaitable[BaseModel]
        ],
        *,
        ctx: Any,
        intent: Optional[str],
    ) -> CallToolResult:
        started = time.perf_counter()
        user_id: Optional[UUID] = None
        client: Optional[str] = None
        outcome = "ok"
        consent = {"enabled": False}
        meta = _request_meta(ctx)
        telemetry = CallTelemetry(tool=tool, intent=intent)
        binding = bind_call(telemetry)
        try:
            token, user_id = self._identify(required_scope)
            client = token.client_id
            model = await work(token, user_id, meta, consent)
            return self._success(model)
        except McpToolError as exc:
            outcome = exc.category.value
            return self._error_result(exc, scope=required_scope)
        except (
            OperationalError,
            PoolTimeoutError,
            DBAPIError,
            ConnectionError,
            TimeoutError,
        ) as exc:
            outcome = ErrorCategory.UNAVAILABLE.value
            logger.warning(
                "tool unavailable",
                extra={
                    "event": "tool_error",
                    "tool": tool,
                    "reason": type(exc).__name__,
                },
            )
            return self._error_result(UnavailableError(UNAVAILABLE_MESSAGE))
        except (
            Exception
        ) as exc:  # noqa: BLE001 - classified, logged by type, never echoed
            outcome = ErrorCategory.INTERNAL.value
            logger.error(
                "tool internal error",
                extra={
                    "event": "tool_error",
                    "tool": tool,
                    "reason": type(exc).__name__,
                },
            )
            return self._error_result(InternalError(INTERNAL_MESSAGE))
        finally:
            unbind_call(binding)
            duration_ms = (time.perf_counter() - started) * 1000
            metrics.tool_call(tool, outcome, duration_ms)
            log_tool_call(
                logger,
                tool=tool,
                outcome=outcome,
                duration_ms=duration_ms,
                user_id=user_id,
                client=client,
            )
            self.analytics.tool_call(
                telemetry,
                outcome=outcome,
                latency_ms=duration_ms,
                user_id=user_id,
                consent=(
                    telemetry.consent_override
                    if telemetry.consent_override is not None
                    else consent["enabled"]
                ),
                meta=meta,
            )

    async def execute(
        self,
        tool: str,
        required_scope: str,
        body: ToolBody,
        *,
        ctx: Any = None,
        intent: Optional[str] = None,
    ) -> CallToolResult:
        async def work(token, user_id, meta, consent):
            def run(sync_session: Session) -> BaseModel:
                user_ctx = self._authorize(sync_session, token, user_id)
                consent["enabled"] = user_ctx.usage_analytics_enabled
                return body(sync_session, user_ctx)

            async with self.session_scope() as session:
                return await session.run_sync(run)

        return await self._run(tool, required_scope, work, ctx=ctx, intent=intent)

    async def execute_write(
        self,
        tool: str,
        required_scope: str,
        body: WriteBody,
        *,
        ctx: Any = None,
        intent: Optional[str] = None,
    ) -> CallToolResult:
        if self.write_scope is None:  # pragma: no cover - wiring error
            raise RuntimeError("write tools need a write_scope")

        async def work(token, user_id, meta, consent):
            async with self.write_scope() as session:
                if session.get_bind().dialect.name == "postgresql":
                    await session.execute(
                        text(
                            f"SET LOCAL statement_timeout = {WRITE_STATEMENT_TIMEOUT_MS}"
                        )
                    )
                user_ctx = await session.run_sync(
                    lambda s: self._authorize(s, token, user_id)
                )
                consent["enabled"] = user_ctx.usage_analytics_enabled
                call = WriteCall(
                    tool=tool,
                    session_digest=_session_digest(meta),
                    data_keys=self.data_keys,
                    now=self.clock(),
                )
                return await body(session, user_ctx, call)

        return await self._run(tool, required_scope, work, ctx=ctx, intent=intent)
