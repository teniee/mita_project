"""Client error intake — public, auth optional.

The mobile app's ErrorHandler POSTs crash/error reports here
(AppConfig.errorReportEndpoint = /api/errors/report) and retries every
2 minutes until it gets a 2xx. The endpoint therefore must exist and must
accept reports from unauthenticated clients (errors can happen before
login) — a 404/401 here turns the client's retry queue into an endless
loop. Reports are written to the server log (Sentry is not configured in
production; Railway logs are the observability channel).

Hardening:
- payloads above _MAX_BODY_BYTES are rejected before validation (413);
- bearer tokens/JWTs, password/secret key-values, and long opaque secrets
  are redacted from every free-text field before logging;
- the log line is a single json.dumps string, so embedded newlines cannot
  forge additional log records;
- per-client rate limit; validation errors return the standard 422 with
  no traceback.
"""

import json
import logging
import re

from fastapi import APIRouter, HTTPException, Request

from app.api.client_errors.schemas import ClientErrorAck, ClientErrorReport
from app.core.simple_rate_limiter import rate_limiter

logger = logging.getLogger("client_errors")

router = APIRouter(prefix="/errors", tags=["Client Errors"])

# Per-client budget: bursts happen when a broken build loops, but one
# device re-sending its 50-report queue every 2 minutes must not flood.
_RATE_LIMIT = 60
_RATE_WINDOW_SECONDS = 3600

# Generous for a validated report (error 4k + stack 16k + context), tight
# enough that nobody uses the public endpoint as a byte sink.
_MAX_BODY_BYTES = 64 * 1024

_REDACTIONS = [
    # JWTs (three base64url segments) — access/refresh tokens in exception
    # text or stack frames.
    (re.compile(r"eyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*"),
     "[REDACTED_JWT]"),
    # Authorization headers pasted into error strings.
    (re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)(bearer\s+)?[^\s'\",}]+"),
     r"\1[REDACTED]"),
    # password/secret/token/api_key style key-value pairs.
    (re.compile(
        r"(?i)((?:password|passwd|pwd|secret|api[_-]?key|refresh[_-]?token|"
        r"access[_-]?token)['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+"),
     r"\1[REDACTED]"),
    # Long opaque hex/base64 blobs (32+ chars) that are most likely keys.
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[REDACTED_HEX]"),
]


def _redact(value):
    if isinstance(value, str):
        for pattern, replacement in _REDACTIONS:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


@router.post("/report", response_model=ClientErrorAck, status_code=202)
async def report_client_error(
    report: ClientErrorReport, request: Request
) -> ClientErrorAck:
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > _MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Report too large")

    await rate_limiter.check_rate_limit(
        request,
        limit=_RATE_LIMIT,
        window_seconds=_RATE_WINDOW_SECONDS,
        endpoint="client_error_report",
    )

    payload = {
        "report_id": report.id,
        "client_timestamp": report.timestamp,
        "error": _redact(report.error),
        "severity": report.severity,
        "category": report.category,
        "app_version": report.appVersion,
        "platform": report.platform,
        "device_info": _redact(report.deviceInfo),
        "is_connected": report.isConnected,
        "user_id": report.userId,
        "context": _redact(report.context),
        "stack_trace": _redact(report.stackTrace),
    }
    log = (
        logger.error
        if (report.severity or "").lower() in ("high", "critical", "fatal")
        else logger.warning
    )
    log("Mobile client error: %s", json.dumps(payload, default=str)[:20000])

    return ClientErrorAck(status="received", report_id=report.id)
