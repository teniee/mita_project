"""Client error intake — public, auth optional.

The mobile app's ErrorHandler POSTs crash/error reports here
(AppConfig.errorReportEndpoint = /api/errors/report) and retries every
2 minutes until it gets a 2xx. The endpoint therefore must exist and must
accept reports from unauthenticated clients (errors can happen before
login) — a 404/401 here turns the client's retry queue into an endless
loop. Reports are written to the server log (Sentry is not configured in
production; Railway logs are the observability channel).
"""

import json
import logging

from fastapi import APIRouter, Request

from app.api.client_errors.schemas import ClientErrorAck, ClientErrorReport
from app.core.simple_rate_limiter import rate_limiter

logger = logging.getLogger("client_errors")

router = APIRouter(prefix="/errors", tags=["Client Errors"])

# Per-client budget: bursts happen when a broken build loops, but one
# device re-sending its 50-report queue every 2 minutes must not flood.
_RATE_LIMIT = 60
_RATE_WINDOW_SECONDS = 3600


@router.post("/report", response_model=ClientErrorAck, status_code=202)
async def report_client_error(
    report: ClientErrorReport, request: Request
) -> ClientErrorAck:
    await rate_limiter.check_rate_limit(
        request,
        limit=_RATE_LIMIT,
        window_seconds=_RATE_WINDOW_SECONDS,
        endpoint="client_error_report",
    )

    payload = {
        "report_id": report.id,
        "client_timestamp": report.timestamp,
        "error": report.error,
        "severity": report.severity,
        "category": report.category,
        "app_version": report.appVersion,
        "platform": report.platform,
        "device_info": report.deviceInfo,
        "is_connected": report.isConnected,
        "user_id": report.userId,
        "context": report.context,
        "stack_trace": report.stackTrace,
    }
    log = (
        logger.error
        if (report.severity or "").lower() in ("high", "critical", "fatal")
        else logger.warning
    )
    log("Mobile client error: %s", json.dumps(payload, default=str)[:20000])

    return ClientErrorAck(status="received", report_id=report.id)
