"""Database access for MCP tools: one READ ONLY transaction per tool call.

Tools reuse the canonical synchronous domain code through
``AsyncSession.run_sync`` — the same bridge the REST routes use. The
transaction is opened read-only on PostgreSQL before any query and always
rolled back, so no tool can write, even by accident (ADR §3).
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# A callable returning an async context manager that yields a session whose
# transaction is already read-only. Tests substitute one bound to a
# rolled-back connection.
SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]


# A tool query that runs longer than this is cancelled by PostgreSQL and
# reported as "unavailable"; it never holds a pooled connection indefinitely.
STATEMENT_TIMEOUT_MS = 5000


async def make_read_only(session: AsyncSession) -> None:
    if session.get_bind().dialect.name == "postgresql":
        await session.execute(text("SET TRANSACTION READ ONLY"))
        await session.execute(
            text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
        )


@asynccontextmanager
async def read_only_session() -> AsyncIterator[AsyncSession]:
    """Production scope: a fresh session from the shared async engine."""
    from app.core.async_session import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        await session.begin()
        try:
            await make_read_only(session)
            yield session
        finally:
            await session.rollback()


@asynccontextmanager
async def write_session() -> AsyncIterator[AsyncSession]:
    """Read-write scope for the OAuth endpoints only (``mcp_oauth_*`` tables
    and the shared login lockout counters). Never handed to a tool."""
    from app.core.async_session import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
