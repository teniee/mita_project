"""Product analytics and feedback against the real database (migration 0039).

The DatabaseSink writes through the same savepoint-bound session the other
tests use, so everything is rolled back afterwards.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.mcp.analytics import DatabaseSink, user_key
from tests_mcp.conftest import Harness, make_settings, structured

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
SECRET = "a" * 48  # make_settings().analytics_secret


@pytest.fixture
def db_sink(scopes):
    _, write_scope, _ = scopes
    return DatabaseSink(write_scope, background=False)


@pytest.fixture
def m(scopes, db_sink):
    read_scope, write_scope, tool_write_scope = scopes
    from app.mcp.server import build_service

    def factory(settings=None, clock=None):
        return build_service(
            settings or make_settings(),
            session_scope=read_scope,
            write_scope=write_scope,
            tool_write_scope=tool_write_scope,
            analytics_sink=db_sink,
            clock=clock,
        )

    return Harness(factory, make_settings()).at(NOW)


async def events(connection, where="TRUE", params=None):
    result = await connection.execute(
        text(f"SELECT * FROM analytics.events WHERE {where} ORDER BY id"),  # nosec B608
        params or {},
    )
    return result.mappings().all()


def new_key():
    return uuid.uuid4().hex


async def test_events_are_written_pseudonymously_and_only_with_consent(
    m, seed, connection, db_sink
):
    consenting = await seed.user(currency="EUR")
    await seed.profile(consenting, usage_analytics_enabled=True)
    private = await seed.user(currency="EUR")
    await m.call(
        m.token(consenting),
        "add_transaction",
        {
            "amount": "42.17",
            "category": "groceries",
            "merchant": "Lidl",
            "idempotency_key": new_key(),
        },
        meta={"openai/session": "conversation-123", "openai/locale": "bg-BG"},
    )
    await m.call(m.token(private), "get_profile", {})
    await db_sink.flush()

    rows = await events(connection)
    assert [r["event_name"] for r in rows] == [
        "tool_call_succeeded",
        "transaction_created",
        "tool_call_succeeded",
    ]
    linked, created, anonymous = rows
    key = user_key(SECRET, consenting.id)
    assert linked["user_key"] == key == created["user_key"]
    assert linked["session_key"] and linked["session_key"] != "conversation-123"
    assert (
        linked["tool_name"] == "add_transaction" and linked["feature"] == "transactions"
    )
    assert linked["intent_code"] == "create_transaction" and linked["locale"] == "bg-BG"
    assert created["properties"] == {"entry_method": "conversation"}
    assert anonymous["user_key"] is None and anonymous["session_key"] is None
    flat = " ".join(str(dict(r)) for r in rows)
    for secret in (
        "42.17",
        "Lidl",
        "conversation-123",
        str(consenting.id),
        consenting.email,
    ):
        assert secret not in flat
    identity = (
        await connection.execute(
            text("SELECT user_key FROM analytics_identities WHERE user_id = :u"),
            {"u": consenting.id},
        )
    ).scalar_one()
    assert identity == key
    assert (
        await connection.execute(
            text("SELECT count(*) FROM analytics_identities WHERE user_id = :u"),
            {"u": private.id},
        )
    ).scalar_one() == 0


async def test_account_deletion_removes_linked_events_and_feedback(
    m, seed, connection, db_sink
):
    user = await seed.user(currency="EUR")
    await seed.profile(user, usage_analytics_enabled=True)
    token = m.token(user)
    await m.call(token, "get_setup_status", {})
    await m.call(
        token,
        "submit_feedback",
        {
            "type": "bug_report",
            "feature_area": "budget",
            "message": "Totals look off.",
            "idempotency_key": new_key(),
        },
    )
    anonymous_user = await seed.user()
    await m.call(m.token(anonymous_user), "get_profile", {})
    await db_sink.flush()
    key = user_key(SECRET, user.id)
    assert len(await events(connection, "user_key = :k", {"k": key})) >= 3

    await seed.delete_user(user)
    assert await events(connection, "user_key = :k", {"k": key}) == []
    assert (
        await connection.execute(
            text("SELECT count(*) FROM product_feedback WHERE user_id = :u"),
            {"u": user.id},
        )
    ).scalar_one() == 0
    assert (
        len(await events(connection, "user_key IS NULL")) >= 1
    )  # unlinked stats remain


async def test_opting_out_deletes_linked_events_and_unlinks_the_future(
    m, seed, connection, db_sink
):
    user = await seed.user(currency="EUR")
    await seed.profile(user, usage_analytics_enabled=True)
    token = m.token(user)
    await m.call(token, "get_profile", {})
    off = structured(await m.call(token, "set_usage_analytics", {"enabled": False}))
    assert off == {
        "usage_analytics_enabled": False,
        "linked_data_deleted": True,
        "what_is_recorded": off["what_is_recorded"],
    }
    await m.call(token, "get_profile", {})
    await db_sink.flush()
    key = user_key(SECRET, user.id)
    assert await events(connection, "user_key = :k", {"k": key}) == []
    tail = await events(
        connection, "tool_name IN ('set_usage_analytics', 'get_profile')"
    )
    assert tail and all(r["user_key"] is None for r in tail)

    on = structured(await m.call(token, "set_usage_analytics", {"enabled": True}))
    assert on["usage_analytics_enabled"] is True and on["linked_data_deleted"] is False
    await m.call(token, "get_profile", {})
    await db_sink.flush()
    linked = await events(connection, "user_key = :k", {"k": key})
    assert [r["event_name"] for r in linked] == [
        "tool_call_succeeded",
        "usage_analytics_enabled",
        "tool_call_succeeded",
    ]


async def test_feedback_is_stored_but_its_text_never_reaches_analytics(
    m, seed, connection, db_sink
):
    user = await seed.user(currency="EUR")
    await seed.profile(user, usage_analytics_enabled=True)
    token = m.token(user)
    args = {
        "type": "confusing",
        "feature_area": "transactions",
        "message": "  Transaction categorization is confusing — Кафе vs dining?  ",
        "rating": 4,
        "idempotency_key": new_key(),
    }
    sent = structured(await m.call(token, "submit_feedback", args))
    again = structured(await m.call(token, "submit_feedback", args))
    assert (sent["status"], again["status"]) == ("sent", "already_sent")
    row = (
        (
            await connection.execute(
                text("SELECT * FROM product_feedback WHERE user_id = :u"),
                {"u": user.id},
            )
        )
        .mappings()
        .one()
    )
    assert row["message"] == "Transaction categorization is confusing — Кафе vs dining?"
    assert (row["type"], row["feature_area"], row["rating"]) == (
        "confusing",
        "transactions",
        4,
    )
    assert (row["status"], row["source"]) == ("new", "chatgpt") and row[
        "created_at"
    ] == NOW
    await db_sink.flush()
    feedback_events = await events(connection, "event_name = 'feedback_submitted'")
    assert len(feedback_events) == 1
    assert feedback_events[0]["properties"] == {
        "type": "confusing",
        "feature_area": "transactions",
        "rating": 4,
    }
    assert "categorization" not in " ".join(
        str(dict(r)) for r in await events(connection)
    )
    view = (
        (
            await connection.execute(
                text("SELECT * FROM analytics.feedback WHERE id = :i"), {"i": row["id"]}
            )
        )
        .mappings()
        .one()
    )
    assert "user_id" not in view and view["user_key"] == user_key(SECRET, user.id)


@pytest.mark.parametrize(
    "args",
    [
        {"type": "rant", "feature_area": "budget", "message": "x"},
        {"type": "praise", "feature_area": "banking", "message": "x"},
        {"type": "praise", "feature_area": "budget", "message": ""},
        {"type": "praise", "feature_area": "budget", "message": "x" * 2001},
        {"type": "praise", "feature_area": "budget", "message": "x", "rating": 6},
    ],
)
async def test_invalid_feedback_is_refused(m, seed, connection, args):
    user = await seed.user()
    result = await m.call(
        m.token(user), "submit_feedback", {**args, "idempotency_key": new_key()}
    )
    assert result.is_error
    assert (
        await connection.execute(
            text("SELECT count(*) FROM product_feedback WHERE user_id = :u"),
            {"u": user.id},
        )
    ).scalar_one() == 0


async def test_feedback_needs_its_own_scope(m, seed):
    user = await seed.user()
    token = m.token(user, scopes=["profile:read", "finance:read", "finance:write"])
    result = await m.call(
        token,
        "submit_feedback",
        {
            "type": "praise",
            "feature_area": "other",
            "message": "Nice",
            "idempotency_key": new_key(),
        },
    )
    assert result.structured_content["error"]["category"] == "forbidden"


async def test_a_failing_analytics_database_never_fails_a_write(
    scopes, seed, connection
):
    read_scope, write_scope, tool_write_scope = scopes
    from contextlib import asynccontextmanager

    from app.mcp.server import build_service

    @asynccontextmanager
    async def broken_scope():
        raise ConnectionError("analytics database unreachable")
        yield  # pragma: no cover

    sink = DatabaseSink(broken_scope, background=False)
    harness = Harness(
        lambda settings=None, clock=None: build_service(
            settings or make_settings(),
            session_scope=read_scope,
            write_scope=write_scope,
            tool_write_scope=tool_write_scope,
            analytics_sink=sink,
            clock=clock,
        ),
        make_settings(),
    ).at(NOW)
    user = await seed.user(currency="EUR")
    await seed.profile(user, usage_analytics_enabled=True)
    result = await harness.call(
        harness.token(user),
        "add_transaction",
        {"amount": "5.00", "category": "dining", "idempotency_key": new_key()},
    )
    assert structured(result)["status"] == "recorded"
    await sink.flush()
    assert sink.dropped >= 2
    amount = (
        await connection.execute(
            text("SELECT amount FROM transactions WHERE user_id = :u"), {"u": user.id}
        )
    ).scalar_one()
    assert amount == Decimal("5.00")


# --- views -----------------------------------------------------------------------


async def _identity(connection, user, key):
    await connection.execute(
        text("INSERT INTO analytics_identities (user_id, user_key) VALUES (:u, :k)"),
        {"u": user.id, "k": key},
    )


async def _event(
    connection,
    key,
    name,
    ago_days,
    *,
    feature="transactions",
    tool="add_transaction",
    status="ok",
    error=None,
    latency=50,
    session="s1",
    properties="{}",
):
    await connection.execute(
        text(
            "INSERT INTO analytics.events (occurred_at, user_key, session_key, event_name, "
            "feature, tool_name, intent_code, status, error_code, latency_ms, surface, "
            "server_version, tool_contract_version, properties) VALUES "
            "(now() - make_interval(days => :ago), :k, :s, :n, :f, :t, 'x', :st, :e, :l, "
            "'chatgpt', '2.0.0', '2.0', CAST(:p AS jsonb))"
        ),
        {
            "ago": ago_days,
            "k": key,
            "s": session,
            "n": name,
            "f": feature,
            "t": tool,
            "st": status,
            "e": error,
            "l": latency,
            "p": properties,
        },
    )


async def _view(connection, sql, params=None):
    return (await connection.execute(text(sql), params or {})).mappings().all()


async def test_dashboard_views_compute_the_core_metrics(seed, connection):
    alice, bob, cara = [await seed.user() for _ in range(3)]
    keys = {"a": "a" * 32, "b": "b" * 32, "c": "c" * 32}
    for user, key in zip((alice, bob, cara), keys.values()):
        await _identity(connection, user, key)
    # Alice: active today and on 10 other days in the last 30 → ENGAGED.
    await _event(connection, keys["a"], "oauth_connected", 40, feature=None, tool=None)
    await _event(
        connection, keys["a"], "onboarding_completed", 40, feature=None, tool=None
    )
    await _event(connection, keys["a"], "budget_saved", 40, feature=None, tool=None)
    for ago in range(0, 11):
        await _event(
            connection, keys["a"], "tool_call_succeeded", ago, session=f"a{ago}"
        )
    # Bob: one financial call 3 days ago and one failed call today (setup feature).
    await _event(
        connection,
        keys["b"],
        "tool_call_succeeded",
        3,
        feature="history",
        tool="get_spending_history",
    )
    await _event(
        connection,
        keys["b"],
        "tool_call_failed",
        0,
        feature="setup",
        tool="get_setup_status",
        status="error",
        error="validation",
        latency=900,
    )
    # Cara: only active 45 days ago → DORMANT.
    await _event(connection, keys["c"], "tool_call_succeeded", 45)
    # An unlinked call today counts for volume, never for users.
    await _event(connection, None, "tool_call_succeeded", 0, session=None)

    today = await _view(
        connection,
        "SELECT * FROM analytics.activity_daily WHERE day = (now() AT TIME ZONE 'UTC')::date",
    )
    assert len(today) == 1
    row = today[0]
    assert (row["dau"], row["wau"], row["mau"], row["wfau"]) == (2, 2, 2, 2)
    # Bob's only financial call (3 days ago) keeps him in WFAU; his setup failure does not.

    adoption = {
        r["feature"]: r
        for r in await _view(connection, "SELECT * FROM analytics.feature_adoption")
    }
    assert set(adoption) >= {"transactions", "history", "goals", "feedback", "privacy"}
    assert adoption["goals"]["users_used"] == 0 and adoption["goals"]["calls"] == 0
    assert adoption["transactions"]["users_used"] == 1
    assert adoption["transactions"]["calls"] == 12  # 11 of Alice's + the unlinked one
    assert adoption["transactions"]["repeat_percent"] == Decimal("100.0")
    assert adoption["history"]["adoption_percent"] == Decimal("50.0")  # 1 of 2 MAU

    segments = {
        r["user_key"]: r["segment"]
        for r in await _view(connection, "SELECT * FROM analytics.user_segments")
    }
    assert segments[keys["a"]] == "ENGAGED"
    assert segments[keys["c"]] == "DORMANT"
    await connection.execute(
        text(
            "UPDATE analytics.segment_thresholds SET value = 5 WHERE name = 'power_active_days'"
        )
    )
    segments = {
        r["user_key"]: r["segment"]
        for r in await _view(connection, "SELECT * FROM analytics.user_segments")
    }
    assert segments[keys["a"]] == "POWER"  # thresholds are data, not code

    reliability = await _view(
        connection,
        "SELECT * FROM analytics.reliability_daily WHERE tool_name = 'get_setup_status'",
    )
    assert reliability[0]["failures"] == 1 and reliability[0]["validation_errors"] == 1
    assert reliability[0]["p95_latency_ms"] == 900

    firsts = {
        r["user_key"]: r
        for r in await _view(connection, "SELECT * FROM analytics.user_firsts")
    }
    assert firsts[keys["a"]]["budget_saved"] is not None
    assert firsts[keys["b"]]["budget_saved"] is None
    retention = {
        r["user_key"]: r
        for r in await _view(connection, "SELECT * FROM analytics.retention_days")
    }
    assert retention[keys["a"]]["d30_eligible"] is True


async def test_the_reader_views_expose_no_user_ids(seed, connection):
    columns = (
        await connection.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'analytics'"
            )
        )
    ).all()
    assert columns
    for table, column in columns:
        assert column not in {"user_id", "email", "password_hash", "message_raw"}, (
            table,
            column,
        )


async def test_the_report_answers_the_core_questions_without_identities(
    seed, connection
):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "analytics_report",
        Path(__file__).resolve().parents[1] / "scripts/mcp/analytics_report.py",
    )
    report_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report_module)

    alice, bob = [await seed.user() for _ in range(2)]
    ka, kb = "a" * 32, "b" * 32
    await _identity(connection, alice, ka)
    await _identity(connection, bob, kb)
    for name in (
        "oauth_connected",
        "onboarding_started",
        "financial_profile_created",
        "budget_previewed",
        "budget_saved",
        "onboarding_completed",
    ):
        await _event(connection, ka, name, 9, feature=None, tool=None)
    await _event(
        connection,
        ka,
        "transaction_created",
        9,
        feature=None,
        tool=None,
        properties='{"entry_method": "conversation"}',
    )
    await _event(connection, ka, "tool_call_succeeded", 9)
    await _event(connection, ka, "tool_call_succeeded", 2, latency=120)
    await _event(
        connection,
        ka,
        "tool_call_succeeded",
        0,
        feature="history",
        tool="get_spending_history",
        latency=80,
    )
    await _event(connection, kb, "oauth_connected", 1, feature=None, tool=None)
    await _event(
        connection,
        kb,
        "tool_call_failed",
        0,
        feature="budget_plan",
        tool="preview_monthly_budget",
        status="error",
        error="validation",
        latency=30,
    )
    await connection.execute(
        text(
            "INSERT INTO product_feedback (id, user_id, type, feature_area, message, rating) "
            "VALUES (gen_random_uuid(), :u, 'confusing', 'transactions', 'secret words', 3)"
        ),
        {"u": alice.id},
    )

    def run(sync_conn):
        def fetch(sql):
            return [dict(r._mapping) for r in sync_conn.execute(text(sql))]

        return report_module.build_report(fetch)

    report = await connection.run_sync(run)
    assert (report["dau"], report["wau"], report["mau"]) == (2, 2, 2)
    assert report["wfau"] == 1  # Bob's only call today failed
    assert report["calls_per_active_user_today"] == 1.0  # 2 calls / 2 users
    assert report["most_used_feature"] == "transactions"
    assert "goals" in report["least_used_features"]
    assert report["most_failing_tools"][0]["tool_name"] == "preview_monthly_budget"
    assert report["onboarding_completed_percent"] == 50.0  # 1 of 2 users
    assert report["first_budget_saved_percent"] == 50.0
    assert report["first_transaction_percent"] == 50.0
    assert report["history_users_month"] == 1
    assert report["feedback"][0]["feature_area"] == "transactions"
    text_out = report_module.render(report)
    for secret in (ka, kb, "secret words", str(alice.id)):
        assert secret not in text_out
