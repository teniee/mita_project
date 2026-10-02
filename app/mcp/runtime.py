"""Execution of one tool call: identity → scope → rate limit → read-only query.

Every tool goes through ``McpRuntime.execute``. The tool body receives the
authenticated user's ``UserContext`` — derived from the bearer token and the
database, never from tool arguments.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp_types import CallToolResult, TextContent
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session

from app.mcp.auth.tokens import TOKEN_VERSION_CLAIM
from app.mcp.config import McpSettings
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class McpRuntime:
    settings: McpSettings
    session_scope: SessionScope
    tool_limiter: SlidingWindowLimiter
    clock: Callable[[], datetime] = field(default=_utcnow)

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
        return CallToolResult(
            content=[TextContent(type="text", text=error.message)],
            structured_content={
                "error": {"category": error.category.value, "message": error.message}
            },
            is_error=True,
            _meta=meta,
        )

    def _run_query(
        self, session: Session, token: AccessToken, user_id: UUID, body: ToolBody
    ) -> BaseModel:
        ctx = load_user_context(session, user_id, now=self.clock())
        if self.settings.auth_mode == "builtin":
            # users.token_version is bumped by logout-all and password reset;
            # that must end ChatGPT access too. Fails closed.
            claimed = (token.claims or {}).get(TOKEN_VERSION_CLAIM)
            if claimed != ctx.token_version:
                metrics.auth_failure("token_version")
                raise AuthError(
                    "Your MITA session has ended. Reconnect MITA to continue."
                )
        return body(session, ctx)

    async def execute(
        self, tool: str, required_scope: str, body: ToolBody
    ) -> CallToolResult:
        started = time.perf_counter()
        user_id: Optional[UUID] = None
        client: Optional[str] = None
        outcome = "ok"
        try:
            token = get_access_token()
            if token is None or token.subject is None:
                raise AuthError("Connect your MITA account to use this tool.")
            client = token.client_id
            user_id = UUID(token.subject)
            if required_scope not in token.scopes:
                raise ForbiddenError(
                    f"This request needs the '{required_scope}' permission, which was not granted."
                )
            if not self.tool_limiter.allow(str(user_id)):
                raise RateLimitedError(
                    "Too many MITA requests in a short time. Wait a minute and try again."
                )
            async with self.session_scope() as session:
                model = await session.run_sync(
                    lambda sync_session: self._run_query(
                        sync_session, token, user_id, body
                    )
                )
            payload = model.model_dump(mode="json")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text", text=json.dumps(payload, ensure_ascii=False)
                    )
                ],
                structured_content=payload,
            )
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
