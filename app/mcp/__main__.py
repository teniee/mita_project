"""Entrypoint: ``python -m app.mcp``.

Never runs migrations — mita-production's start.sh owns ``alembic upgrade``.
Readiness (``/health``) requires the database and the MCP tables (0037's
``mcp_oauth_*``, 0038's profiles and idempotency records), so a deploy that
lands before the migration reports 503 instead of failing requests one by one.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import uvicorn
from sqlalchemy import text

from app.mcp.config import McpConfigError, load_settings
from app.mcp.observability import configure_logging

REQUIRED_TABLES = (
    "mcp_oauth_clients",
    "mcp_oauth_authorization_codes",
    "mcp_oauth_refresh_tokens",
    "mcp_user_profiles",  # 0038
    "mcp_idempotency_keys",  # 0038
    "product_feedback",  # 0039
    "analytics_identities",  # 0039
)


async def database_ready() -> bool:
    from app.core.async_session import get_async_session_factory

    try:
        async with get_async_session_factory()() as session:
            await session.execute(text("SELECT 1"))
            present = await session.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_name = ANY(:names)"
                ),
                {"names": list(REQUIRED_TABLES)},
            )
            return present.scalar_one() == len(REQUIRED_TABLES)
    except Exception:  # noqa: BLE001 - readiness reports, it does not raise
        logging.getLogger("app.mcp").warning(
            "readiness check failed", extra={"event": "readiness_failed"}
        )
        return False


def pin_process_timezone() -> None:
    """Naive datetimes mean UTC across the codebase, and asyncpg encodes a
    naive value bound to a timestamptz parameter with ``astimezone()`` — i.e.
    in the PROCESS's local zone. The image sets TZ=UTC; this makes any other
    way of starting the service (a laptop in Sofia) behave the same instead
    of shifting every date window by the host's UTC offset."""
    os.environ["TZ"] = "UTC"
    time.tzset()


def main() -> None:
    pin_process_timezone()
    try:
        settings = load_settings()
    except McpConfigError as exc:
        # Configuration errors are safe to print: they name variables, not values.
        print(f"mita-mcp: configuration error: {exc}", file=sys.stderr)
        sys.exit(2)

    from app.mcp.server import build_service  # imports the domain layer

    configure_logging(os.environ.get("LOG_LEVEL", "INFO").upper())
    from app.mcp.analytics import DatabaseSink
    from app.mcp.db import write_session

    service = build_service(
        settings,
        readiness_check=database_ready,
        analytics_sink=DatabaseSink(write_session),
    )
    uvicorn.run(
        service.app,
        host="0.0.0.0",  # nosec B104 - container entrypoint behind Railway's proxy
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "*"),
        log_config=None,
        access_log=False,
        timeout_keep_alive=30,
    )


if __name__ == "__main__":
    main()
