"""Concurrent refresh of one refresh token, on real pooled connections.

The rest of the suite runs on one connection inside a rolled-back
transaction, which cannot exercise row-level races. This test uses the
production session factories (separate pooled connections, real commits) and
deletes everything it created.

Policy under test: a refresh token can be exchanged at most once. When two
exchanges race, exactly one succeeds; the loser is treated like a replay and
the whole token family is revoked (the winner's new refresh token included),
so a stolen token raced against the legitimate client never yields a
surviving grant. The price is that a client which genuinely double-submits
must re-authorize; for financial data that trade is deliberate.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text

from app.core.password_security import hash_password_sync
from app.mcp.db import read_only_session, write_session
from app.mcp.server import build_service
from tests_mcp.conftest import PASSWORD, http_client, make_settings, started
from tests_mcp.test_oauth_flow import exchange, full_login, refresh


@pytest.fixture
async def committed_user():
    from app.core import async_session
    from app.db.models import User

    user = User(
        id=uuid.uuid4(),
        email=f"race_{uuid.uuid4().hex[:10]}@example.test",
        password_hash=hash_password_sync(PASSWORD),
        timezone="UTC",
        token_version=1,
        failed_login_attempts=0,
        has_onboarded=True,
    )
    async with write_session() as session:
        session.add(user)
    try:
        yield user
    finally:
        async with write_session() as session:
            await session.execute(
                text(
                    "DELETE FROM mcp_oauth_clients WHERE client_id IN ("
                    " SELECT client_id FROM mcp_oauth_refresh_tokens WHERE user_id = :u)"
                ),
                {"u": user.id},
            )
            await session.execute(
                text("DELETE FROM users WHERE id = :u"), {"u": user.id}
            )
        await async_session.close_database()
        async_session.AsyncSessionLocal = None


async def test_concurrent_refresh_yields_at_most_one_grant(committed_user):
    service = build_service(
        make_settings(), session_scope=read_only_session, write_scope=write_session
    )
    async with started(service):
        async with http_client(service) as http:
            client_id, verifier, code, _ = await full_login(http, committed_user)
            tokens = (await exchange(http, client_id, code, verifier)).json()
            first, second = await asyncio.gather(
                refresh(http, client_id, tokens["refresh_token"]),
                refresh(http, client_id, tokens["refresh_token"]),
            )
            statuses = sorted([first.status_code, second.status_code])
            assert statuses == [200, 400], statuses
            winner = first if first.status_code == 200 else second
            # Family revoked by the losing (replayed) presentation.
            follow_up = await refresh(http, client_id, winner.json()["refresh_token"])
            assert follow_up.status_code == 400

    async with write_session() as session:
        live = await session.scalar(
            text(
                "SELECT count(*) FROM mcp_oauth_refresh_tokens "
                "WHERE user_id = :u AND revoked_at IS NULL AND rotated_at IS NULL"
            ),
            {"u": committed_user.id},
        )
    assert live == 0
