"""Fixtures for the MCP service tests.

Runs in the MCP environment (``requirements-mcp.txt`` + pytest), against a
real PostgreSQL at ``DATABASE_URL`` migrated to head. Every test runs inside
one outer transaction that is rolled back; each tool call / OAuth write gets
its own SAVEPOINT session on that connection, so the read-only scope, the
commit-on-success write scope and the rollback semantics are the real ones.

The service is driven in-process through the MCP SDK's streamable-HTTP client
over an ASGI transport: bearer middleware, transport, tools and serializers
are all exercised; nothing is mocked.
"""

from __future__ import annotations

import os
import time

os.environ["TZ"] = "UTC"
time.tzset()
os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@localhost:5432/test_mita?sslmode=disable"
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only_xxxxxxxx")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_min_32_chars_long_for_testing")

import secrets  # noqa: E402
import uuid  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from datetime import date, datetime, timedelta, timezone  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import Any, Dict, Iterable, List, Optional  # noqa: E402

import httpx2  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from mcp import Client  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.core.password_security import hash_password_sync  # noqa: E402
from app.db.models import (  # noqa: E402
    DailyPlan,
    Goal,
    ScheduledExpense,
    Transaction,
    User,
)
from app.mcp.auth.fingerprint import (  # noqa: E402
    credential_fingerprint,
    fingerprint_key,
)
from app.mcp.auth.keys import generate_private_key_pem  # noqa: E402
from app.mcp.auth.scopes import SUPPORTED_SCOPES  # noqa: E402
from app.mcp.auth.tokens import issue_access_token  # noqa: E402
from app.mcp.config import McpSettings  # noqa: E402
from app.mcp.db import make_read_only  # noqa: E402
from app.mcp.observability import configure_logging  # noqa: E402
from app.mcp.server import McpService, build_service  # noqa: E402

# The same logging tree production gets (``python -m app.mcp``).
configure_logging("INFO")

PUBLIC_URL = "https://mcp.example.test"
PASSWORD = "Correct-Horse-Battery-9"

_PRIVATE_KEY = generate_private_key_pem(2048)
_PASSWORD_HASH = hash_password_sync(PASSWORD)  # bcrypt once, not per seeded user


def _async_url() -> str:
    url = os.environ["DATABASE_URL"]
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url.replace("sslmode=disable", "ssl=disable")


def make_settings(**overrides: Any) -> McpSettings:
    values: Dict[str, Any] = dict(
        environment="test",
        public_url=PUBLIC_URL,
        auth_mode="builtin",
        private_key_pem=_PRIVATE_KEY,
        login_csrf_secret="c" * 48,
        apps_challenge_token="challenge-token-123",
        support_url="https://support.example.test",
        tool_calls_per_minute=1000,
        login_attempts_per_minute=1000,
        metrics_token="metrics-secret",
    )
    values.update(overrides)
    return McpSettings(**values)


@pytest.fixture
def settings() -> McpSettings:
    return make_settings()


@pytest.fixture
async def connection():
    engine = create_async_engine(
        _async_url(), connect_args={"server_settings": {"timezone": "UTC"}}
    )
    async with engine.connect() as conn:
        outer = await conn.begin()
        try:
            yield conn
        finally:
            await outer.rollback()
    await engine.dispose()


@pytest.fixture
def scopes(connection):
    """(read_only_scope, write_scope) bound to the test transaction."""

    @asynccontextmanager
    async def read_scope():
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            await session.begin()
            await make_read_only(session)
            yield session
        finally:
            await session.rollback()
            await session.close()

    @asynccontextmanager
    async def write_scope():
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
        finally:
            await session.close()

    return read_scope, write_scope


@pytest.fixture
def make_service(scopes):
    read_scope, write_scope = scopes

    def factory(settings: Optional[McpSettings] = None, clock=None) -> McpService:
        return build_service(
            settings or make_settings(),
            session_scope=read_scope,
            write_scope=write_scope,
            clock=clock,
        )

    return factory


@pytest.fixture
def service(make_service) -> McpService:
    return make_service()


@asynccontextmanager
async def started(service: McpService):
    """Run the transport's session manager (once per service instance, and in
    the current task — anyio task groups cannot be entered and exited across
    pytest-asyncio's setup/teardown tasks)."""
    async with service.server.session_manager.run():
        yield service


class Harness:
    """Builds a fresh service per interaction; all share the signing key and
    the test transaction, so tokens and data carry across calls."""

    def __init__(self, factory, settings: McpSettings, now: Optional[datetime] = None):
        self.factory = factory
        self.settings = settings
        self.now = now
        self.service = factory(settings)  # for keys / token minting

    def at(self, now: datetime) -> "Harness":
        """Same service, with the user's 'today' derived from this instant."""
        return Harness(self.factory, self.settings, now)

    def _build(self) -> McpService:
        clock = (lambda: self.now) if self.now is not None else None
        return self.factory(self.settings, clock=clock)

    def token(self, user: User, **kwargs) -> str:
        return mint_token(self.service, user, settings=self.settings, **kwargs)

    async def call(
        self, token: Optional[str], tool: str, arguments: Optional[dict] = None
    ):
        service = self._build()
        async with started(service):
            async with mcp_client(service, token) as client:
                return await client.call_tool(tool, arguments or {})

    async def list_tools(self, token: str):
        service = self._build()
        async with started(service):
            async with mcp_client(service, token) as client:
                return (await client.list_tools()).tools

    @asynccontextmanager
    async def http(self, token: Optional[str] = None):
        service = self._build()
        async with started(service):
            async with http_client(service, token) as client:
                client.mita_service = service  # tests reach the provider clock
                yield client


@pytest.fixture
def mcp(make_service, settings) -> Harness:
    return Harness(make_service, settings)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


@dataclass
class Seeder:
    connection: Any
    users: List[User] = field(default_factory=list)

    async def _add(self, *objects) -> None:
        session = AsyncSession(
            bind=self.connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            session.add_all(objects)
            await session.commit()
        finally:
            await session.close()

    async def user(
        self,
        *,
        tz: str = "UTC",
        currency: str = "USD",
        income: Optional[str] = "5000.00",
        name: Optional[str] = "Test User",
        onboarded: bool = True,
        password: str = PASSWORD,
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            email=f"mcp_{uuid.uuid4().hex[:12]}@example.test",
            password_hash=(
                _PASSWORD_HASH if password == PASSWORD else hash_password_sync(password)
            ),
            timezone=tz,
            currency=currency,
            monthly_income=Decimal(income) if income is not None else None,
            name=name,
            has_onboarded=onboarded,
            token_version=1,
            failed_login_attempts=0,
        )
        await self._add(user)
        self.users.append(user)
        return user

    async def txn(
        self,
        user: User,
        amount: str,
        category: str,
        spent_at: datetime,
        *,
        merchant: Optional[str] = None,
        description: Optional[str] = None,
        deleted: bool = False,
        recurring: bool = False,
        currency: Optional[str] = None,
    ) -> Transaction:
        txn = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            amount=Decimal(amount),
            category=category,
            spent_at=spent_at,
            merchant=merchant,
            description=description,
            location="Secret Street 1",
            notes="private note",
            receipt_url="https://receipts.example.test/r/1.jpg",
            currency=currency or user.currency,
            is_recurring=recurring,
            deleted_at=datetime.now(timezone.utc) if deleted else None,
        )
        await self._add(txn)
        return txn

    async def plan(
        self,
        user: User,
        day: date,
        allocations: Dict[str, str],
        *,
        stale_spent: str = "999.99",
        goal: Optional[Goal] = None,
    ) -> None:
        """Plan rows as the canonical writers store them (midnight UTC of the
        local day). ``spent_amount`` is set to a deliberately wrong cache value:
        the MCP layer must read spend from the ledger, not from this column."""
        rows = [
            DailyPlan(
                id=uuid.uuid4(),
                user_id=user.id,
                date=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
                category=category,
                planned_amount=Decimal(amount),
                daily_budget=Decimal(amount),
                spent_amount=Decimal(stale_spent),
                goal_id=goal.id if goal else None,
            )
            for category, amount in allocations.items()
        ]
        await self._add(*rows)

    async def goal(self, user: User, **kwargs) -> Goal:
        values = dict(
            id=uuid.uuid4(),
            user_id=user.id,
            title="Emergency fund",
            target_amount=Decimal("1000.00"),
            saved_amount=Decimal("250.00"),
            status="active",
            progress=Decimal("25.00"),
        )
        values.update(kwargs)
        goal = Goal(**values)
        await self._add(goal)
        return goal

    async def scheduled(self, user: User, **kwargs) -> ScheduledExpense:
        values = dict(
            id=uuid.uuid4(),
            user_id=user.id,
            category="rent",
            amount=Decimal("1200.00"),
            scheduled_date=date.today() + timedelta(days=5),
            recurrence="monthly",
            status="pending",
        )
        values.update(kwargs)
        item = ScheduledExpense(**values)
        await self._add(item)
        return item

    async def bump_token_version(self, user: User) -> None:
        await self.connection.execute(
            text("UPDATE users SET token_version = token_version + 1 WHERE id = :id"),
            {"id": user.id},
        )

    async def delete_user(self, user: User) -> None:
        await self.connection.execute(
            text("DELETE FROM users WHERE id = :id"), {"id": user.id}
        )


@pytest.fixture
def seed(connection) -> Seeder:
    return Seeder(connection)


# ---------------------------------------------------------------------------
# Tokens and MCP calls
# ---------------------------------------------------------------------------


def mint_token(
    service: McpService,
    user: User,
    *,
    scopes: Iterable[str] = SUPPORTED_SCOPES,
    token_version: Optional[int] = None,
    now: Optional[int] = None,
    settings: Optional[McpSettings] = None,
) -> str:
    effective = settings or service.runtime.settings
    token, _ = issue_access_token(
        service.keys,
        effective,
        user_id=user.id,
        client_id="test-client",
        scopes=scopes,
        token_version=(
            token_version if token_version is not None else int(user.token_version or 1)
        ),
        credential_fingerprint=credential_fingerprint(
            fingerprint_key(effective.login_csrf_secret), user.password_hash
        ),
        now=now,
    )
    return token


def forge_token(
    claims: Dict[str, Any], *, key_pem: str = _PRIVATE_KEY, kid: str = "x"
) -> str:
    return jwt.encode(
        claims, key_pem, algorithm="RS256", headers={"kid": kid, "typ": "at+jwt"}
    )


@asynccontextmanager
async def http_client(service: McpService, token: Optional[str] = None):
    """HTTP client into a service that is already ``started``."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=service.app),
        base_url=PUBLIC_URL,
        headers=headers,
        follow_redirects=False,
    ) as client:
        yield client


@asynccontextmanager
async def mcp_client(service: McpService, token: Optional[str]):
    async with http_client(service, token) as http:
        async with Client(
            streamable_http_client(f"{PUBLIC_URL}/mcp", http_client=http)
        ) as client:
            yield client


def structured(result) -> dict:
    assert not result.is_error, result.content
    return result.structured_content


def random_token() -> str:
    return secrets.token_urlsafe(16)
