"""Structured logs, request ids and counters for the MCP service.

What is logged: method, path (never the query string), status, latency,
request id, tool name, outcome category, and a one-way hash of the user id.
What is never logged: tokens, authorization codes, passwords, e-mail
addresses, amounts, merchants, categories, descriptions, tool arguments.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import re
import secrets
import sys
import threading
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "mcp_request_id", default="-"
)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# Keys a log record may carry through ``extra=``; everything else is dropped.
_ALLOWED_EXTRA = {
    "event",
    "tool",
    "outcome",
    "category",
    "duration_ms",
    "status",
    "method",
    "path",
    "subject_hash",
    "client",
    "reason",
    "scopes",
}


def subject_hash(user_id: Any) -> str:
    return hashlib.sha256(f"mita-log:{user_id}".encode()).hexdigest()[:12]


# Loggers whose message text is written as-is. Every other logger (the reused
# domain layer, SQLAlchemy, ...) is reduced to logger/level/exception type:
# domain code logs amounts and ids in free text (compute_forecast logs pace,
# safe limit and balance at INFO), and free text cannot be sanitized reliably.
_TRUSTED_MESSAGE_PREFIXES = ("app.mcp", "mcp.", "uvicorn.error", "starlette")
WITHHELD = "[message withheld]"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        trusted = record.name.startswith(_TRUSTED_MESSAGE_PREFIXES)
        payload: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage() if trusted else WITHHELD,
            "request_id": request_id_var.get(),
        }
        if trusted:
            for key in _ALLOWED_EXTRA:
                if key in record.__dict__:
                    payload[key] = record.__dict__[key]
        if record.exc_info and record.exc_info[0] is not None:
            # Type only: exception messages can carry SQL parameters or values.
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Take over the logging tree for the MCP process.

    ``app.core.logging_config`` runs ``dictConfig`` at import time (pulled in
    by the reused domain modules): it gives the ``app`` logger its own text
    and file handlers with ``propagate=False``. Undo that so every record goes
    through one stdout JSON handler, and keep the domain layer at WARNING.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
        existing.close()
    root.addHandler(handler)
    root.setLevel(level)
    for name, logger in list(logging.root.manager.loggerDict.items()):
        if not isinstance(logger, logging.Logger):
            continue
        for existing in list(logger.handlers):
            logger.removeHandler(existing)
            existing.close()
        logger.propagate = True
        logger.disabled = False
        logger.setLevel(logging.NOTSET)
    logging.getLogger("app").setLevel(logging.WARNING)
    logging.getLogger("app.mcp").setLevel(level)
    # The access log would record query strings (/authorize?...); RequestLogMiddleware
    # writes a path-only line instead.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "httpx2", "httpcore", "sqlalchemy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class Metrics:
    """Process-local counters, exposed in Prometheus text format at /metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tool_calls: Counter = Counter()  # (tool, outcome)
        self.tool_latency_ms_sum: Dict[str, float] = defaultdict(float)
        self.tool_latency_count: Counter = Counter()
        self.auth_failures: Counter = Counter()  # reason
        self.http_requests: Counter = Counter()  # (path_group, status_class)

    def tool_call(self, tool: str, outcome: str, duration_ms: float) -> None:
        with self._lock:
            self.tool_calls[(tool, outcome)] += 1
            self.tool_latency_ms_sum[tool] += duration_ms
            self.tool_latency_count[tool] += 1

    def auth_failure(self, reason: str) -> None:
        with self._lock:
            self.auth_failures[reason] += 1

    def http_request(self, path_group: str, status: int) -> None:
        with self._lock:
            self.http_requests[(path_group, f"{status // 100}xx")] += 1

    def render(self) -> str:
        lines = []
        with self._lock:
            lines.append("# TYPE mita_mcp_tool_calls_total counter")
            for (tool, outcome), n in sorted(self.tool_calls.items()):
                lines.append(
                    f'mita_mcp_tool_calls_total{{tool="{tool}",outcome="{outcome}"}} {n}'
                )
            lines.append("# TYPE mita_mcp_tool_latency_ms summary")
            for tool, total in sorted(self.tool_latency_ms_sum.items()):
                lines.append(
                    f'mita_mcp_tool_latency_ms_sum{{tool="{tool}"}} {total:.3f}'
                )
                lines.append(
                    f'mita_mcp_tool_latency_ms_count{{tool="{tool}"}} {self.tool_latency_count[tool]}'
                )
            lines.append("# TYPE mita_mcp_auth_failures_total counter")
            for reason, n in sorted(self.auth_failures.items()):
                lines.append(f'mita_mcp_auth_failures_total{{reason="{reason}"}} {n}')
            lines.append("# TYPE mita_mcp_http_requests_total counter")
            for (group, status), n in sorted(self.http_requests.items()):
                lines.append(
                    f'mita_mcp_http_requests_total{{path="{group}",status="{status}"}} {n}'
                )
        return "\n".join(lines) + "\n"


metrics = Metrics()

_PATH_GROUPS = (
    "/mcp",
    "/.well-known/",
    "/authorize",
    "/token",
    "/register",
    "/revoke",
    "/oauth/login",
    "/health",
    "/metrics",
)


def _path_group(path: str) -> str:
    for prefix in _PATH_GROUPS:
        if path.startswith(prefix):
            return prefix
    return "other"


class RequestLogMiddleware:
    """Assigns a request id, echoes it as ``X-Request-ID``, logs one line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger("app.mcp.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = (
            dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        )
        request_id = (
            incoming if _REQUEST_ID_RE.match(incoming) else secrets.token_hex(8)
        )
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            path = scope.get("path", "")
            metrics.http_request(_path_group(path), status_holder["status"])
            if path != "/health":
                self.logger.info(
                    "request",
                    extra={
                        "event": "http_request",
                        "method": scope.get("method"),
                        "path": path,
                        "status": status_holder["status"],
                        "duration_ms": duration_ms,
                    },
                )
            request_id_var.reset(token)


def log_tool_call(
    logger: logging.Logger,
    *,
    tool: str,
    outcome: str,
    duration_ms: float,
    user_id: Optional[Any],
    client: Optional[str],
) -> None:
    logger.info(
        "tool_call",
        extra={
            "event": "tool_call",
            "tool": tool,
            "outcome": outcome,
            "duration_ms": round(duration_ms, 1),
            "subject_hash": subject_hash(user_id) if user_id else None,
            "client": client,
        },
    )
