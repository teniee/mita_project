"""The production analytics sink: a background writer on its own pooled connection.

Uses the production session factories (real commits) like the other
real-connection tests, and deletes what it created. Proves the queue/writer
path the service runs, while test_analytics_db.py proves the rows themselves.
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.password_security import hash_password_sync
from app.mcp.analytics import DatabaseSink, user_key
from app.mcp.db import read_only_session, write_session
from app.mcp.server import build_service
from tests_mcp.conftest import PASSWORD, make_settings, mcp_client, mint_token, started

MARKER_LOCALE = "zu-ZA"  # identifies this test's unlinked events for cleanup


@pytest.fixture
async def committed_user():
    from app.core import async_session
    from app.db.models import McpUserProfile, User

    user = User(
        id=uuid.uuid4(),
        email=f"sink_{uuid.uuid4().hex[:10]}@example.test",
        password_hash=hash_password_sync(PASSWORD),
        timezone="UTC",
        currency="EUR",
        token_version=1,
        failed_login_attempts=0,
        has_onboarded=True,
    )
    async with write_session() as session:
        session.add(user)
        await session.flush()
        session.add(McpUserProfile(user_id=user.id, usage_analytics_enabled=True))
    try:
        yield user
    finally:
        async with write_session() as session:
            await session.execute(
                text("DELETE FROM analytics.events WHERE locale = :l"),
                {"l": MARKER_LOCALE},
            )
            await session.execute(
                text("DELETE FROM users WHERE id = :u"), {"u": user.id}
            )
        await async_session.close_database()
        async_session.AsyncSessionLocal = None


async def test_background_writer_commits_events_off_the_request_path(committed_user):
    sink = DatabaseSink(write_session)
    service = build_service(
        make_settings(),
        session_scope=read_only_session,
        write_scope=write_session,
        analytics_sink=sink,
    )
    token = mint_token(service, committed_user)
    async with started(service):
        async with mcp_client(service, token) as client:
            for _ in range(3):
                result = await client.call_tool(
                    "get_profile", {}, meta={"openai/locale": MARKER_LOCALE}
                )
                assert not result.is_error
    await sink.flush()
    key = user_key(make_settings().analytics_secret, committed_user.id)
    async with write_session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT event_name, tool_name FROM analytics.events "
                    "WHERE user_key = :k ORDER BY id"
                ),
                {"k": key},
            )
        ).all()
    assert [tuple(r) for r in rows] == [("tool_call_succeeded", "get_profile")] * 3
    assert sink.dropped == 0
    # Deleting the account (fixture teardown) cascades these rows away.
