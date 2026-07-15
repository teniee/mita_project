"""Phase-1 regressions: the red "Server error" toast root causes.

Production evidence (Railway, 2026-07-14 21:17): a fresh app session's only
non-2xx was POST /api/ai/snapshot -> 500 "TypeError: 'NoneType' object is not
callable" at calendar_service_real.get_calendar_for_user, because
app.core.session.SessionLocal is initialized lazily by get_db() and the
legacy wrapper read it directly. A second, swallowed defect:
GET /api/ai/financial-health-score fell back to canned data because
UserContext.monthly_income arrived as Decimal and Decimal * float raises.

These tests pin:
1. create_sync_session() initializes the lazy sync factory.
2. get_calendar_for_user() works when SessionLocal starts as None.
3. UserContext coerces Decimal income at the boundary.
4. POST /api/errors/report exists, accepts anonymous reports, validates.
"""

import os
import sys
import types
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@localhost:5432/test_mita?sslmode=disable"
)
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("FIREBASE_JSON", "{}")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_min_32_chars_long_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")

dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(
    ApplicationDefault=lambda: None,
    Certificate=lambda *a, **k: None,
)
dummy.initialize_app = lambda cred=None: None
dummy.firestore = types.SimpleNamespace(client=lambda: None)
dummy.messaging = types.SimpleNamespace(
    Message=lambda **kwargs: None,
    send=lambda message: "mock_message_id",
)
sys.modules.setdefault("firebase_admin", dummy)
sys.modules.setdefault("firebase_admin.credentials", dummy.credentials)
sys.modules.setdefault("firebase_admin.firestore", dummy.firestore)
sys.modules.setdefault("firebase_admin.messaging", dummy.messaging)

import app.core.session as core_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.calendar_service_real import get_calendar_for_user  # noqa: E402
from app.services.core.dynamic_threshold_service import (  # noqa: E402
    DynamicThresholdService,
    UserContext,
)


# ---------------------------------------------------------------------------
# 1-2. Lazy sync session initialization
# ---------------------------------------------------------------------------


class _StubSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_create_sync_session_initializes_lazily(monkeypatch):
    """create_sync_session must trigger initialization, not read None."""

    def fake_initialize():
        core_session.SessionLocal = _StubSession

    monkeypatch.setattr(core_session, "SessionLocal", None)
    monkeypatch.setattr(core_session, "_initialize_sync_session", fake_initialize)

    session = core_session.create_sync_session()
    assert isinstance(session, _StubSession)


def test_create_sync_session_raises_clearly_when_unconfigured(monkeypatch):
    monkeypatch.setattr(core_session, "SessionLocal", None)
    monkeypatch.setattr(core_session, "_initialize_sync_session", lambda: None)

    with pytest.raises(RuntimeError, match="not initialized"):
        core_session.create_sync_session()


def test_get_calendar_for_user_survives_uninitialized_sessionlocal(monkeypatch):
    """The exact prod failure: first caller in a worker process where no
    sync get_db() route has run yet. Previously: TypeError 'NoneType' object
    is not callable -> 500 -> global red toast in the app."""
    created = {}

    def fake_initialize():
        def factory():
            created["session"] = _StubSession()
            return created["session"]

        core_session.SessionLocal = factory

    monkeypatch.setattr(core_session, "SessionLocal", None)
    monkeypatch.setattr(core_session, "_initialize_sync_session", fake_initialize)
    monkeypatch.setattr(
        "app.services.calendar_service_real.fetch_calendar",
        lambda db, user_id, year, month: {"2026-07-01": {"food": 10.0}},
    )

    result = get_calendar_for_user("00000000-0000-0000-0000-000000000001", 2026, 7)

    assert result == {"2026-07-01": {"food": 10.0}}
    assert created["session"].closed, "wrapper must close the session it opened"


# ---------------------------------------------------------------------------
# 3. UserContext Decimal boundary
# ---------------------------------------------------------------------------


def test_user_context_coerces_decimal_income():
    """User.monthly_income is Numeric -> Decimal; threshold math multiplies
    by float literals. Prod: financial-health-score returned fallback data
    for every user."""
    ctx = UserContext(monthly_income=Decimal("6000.00"), age=35)

    assert isinstance(ctx.monthly_income, float)
    assert ctx.monthly_income == 6000.0

    thresholds = DynamicThresholdService().get_spending_pattern_thresholds(ctx)
    # 0.5% of 6000 = 30, within [5, 100] clamp
    assert thresholds["small_purchase_threshold"] == pytest.approx(30.0)
    assert thresholds["medium_purchase_threshold"] == pytest.approx(120.0)


def test_user_context_coerces_none_and_decimal_ratios():
    ctx = UserContext(
        monthly_income=None,
        age=30,
        debt_to_income_ratio=Decimal("0.2"),
        current_savings_rate=Decimal("0.1"),
    )
    assert ctx.monthly_income == 0.0
    assert isinstance(ctx.debt_to_income_ratio, float)
    assert isinstance(ctx.current_savings_rate, float)


# ---------------------------------------------------------------------------
# 3b. GPT rating must degrade, not 500, when the SDK is unusable
# ---------------------------------------------------------------------------


def test_financial_rating_falls_back_when_gpt_client_unusable(monkeypatch):
    """Prod (session-5 verify run): openai 1.54.4 passed the removed
    `proxies` kwarg to httpx 0.28 and raised TypeError at client
    construction — before ask()'s own OpenAIError handling — turning
    POST /api/ai/snapshot into a 500. The rating must degrade instead."""
    from app.services.core.engine import ai_personal_finance_profiler as profiler

    class _NoTemplates:
        def __init__(self, db):
            pass

        def get(self, name):
            return None

    def _boom(*args, **kwargs):
        raise TypeError("Client.__init__() got an unexpected keyword argument")

    monkeypatch.setattr(profiler, "AIAdviceTemplateService", _NoTemplates)
    monkeypatch.setattr(profiler, "GPTAgentService", _boom)

    rating = profiler.generate_financial_rating(
        {
            "total_by_category": {"food": 100.0},
            "status_breakdown": {"good": 3},
            "behavior_tags": [],
        },
        db=None,
    )

    assert rating == {
        "rating": "B",
        "risk": "moderate",
        "summary": "User spending is generally steady but occasionally exceeds the budget.",
    }


def test_financial_rating_falls_back_when_api_key_missing(monkeypatch):
    """OpenAI(api_key=None) raises OpenAIError at construction."""
    from app.services.core.engine import ai_personal_finance_profiler as profiler

    class _NoTemplates:
        def __init__(self, db):
            pass

        def get(self, name):
            return None

    monkeypatch.setattr(profiler, "AIAdviceTemplateService", _NoTemplates)
    monkeypatch.setattr(profiler.settings, "OPENAI_API_KEY", None, raising=False)

    rating = profiler.generate_financial_rating(
        {"total_by_category": {}, "status_breakdown": {}, "behavior_tags": []},
        db=None,
    )
    assert rating["rating"] == "B"


@pytest.mark.parametrize("exc_name", ["RateLimitError", "APITimeoutError"])
def test_gpt_ask_degrades_on_api_failures(exc_name):
    """Quota exhaustion and timeouts return the fallback string, not raise."""
    import openai
    from unittest.mock import Mock

    from app.agent.gpt_agent_service import GPTAgentService

    service = GPTAgentService(api_key="sk-test-not-real")

    exc_cls = getattr(openai, exc_name)
    try:
        # Newer SDKs require response/body kwargs; fall back per signature.
        exc = exc_cls("boom", response=Mock(status_code=429, headers={}), body=None)
    except TypeError:
        try:
            exc = exc_cls(request=Mock())
        except TypeError:
            exc = exc_cls("boom")

    service.client = Mock()
    service.client.chat.completions.create.side_effect = exc

    result = service.ask([{"role": "user", "content": "hi"}])
    assert "unavailable" in result.lower()


def test_snapshot_rating_falls_back_on_invalid_gpt_response(monkeypatch):
    """Non-JSON GPT output must yield the canned rating dict."""
    from unittest.mock import Mock

    from app.services.core.engine import ai_personal_finance_profiler as profiler

    class _NoTemplates:
        def __init__(self, db):
            pass

        def get(self, name):
            return None

    gpt = Mock()
    gpt.ask.return_value = "Sorry, I'm currently unavailable."

    monkeypatch.setattr(profiler, "AIAdviceTemplateService", _NoTemplates)
    monkeypatch.setattr(profiler, "GPTAgentService", Mock(return_value=gpt))

    rating = profiler.generate_financial_rating(
        {"total_by_category": {}, "status_breakdown": {}, "behavior_tags": []},
        db=None,
    )
    assert rating == {
        "rating": "B",
        "risk": "moderate",
        "summary": "User spending is generally steady but occasionally exceeds the budget.",
    }


# ---------------------------------------------------------------------------
# 4. POST /api/errors/report
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def _report_body(**overrides):
    body = {
        "id": "err_123",
        "timestamp": "2026-07-14T21:17:05.000Z",
        "error": "TypeError: null check operator used on a null value",
        "stackTrace": "#0 main (package:mita/main.dart:1)",
        "severity": "high",
        "category": "ui",
        "context": {"screen": "dashboard"},
        "appVersion": "1.0.0",
        "platform": "android",
        "deviceInfo": "sdk_gphone64_arm64",
        "isConnected": True,
        "userId": None,
    }
    body.update(overrides)
    return body


def test_error_report_accepts_anonymous_client(client):
    """The app reports errors that can occur before login; a 401/404 here
    put the client's retry queue into an endless 2-minute loop."""
    response = client.post("/api/errors/report", json=_report_body())

    assert response.status_code == 202
    assert response.json()["status"] == "received"
    assert response.json()["report_id"] == "err_123"


def test_error_report_requires_error_text(client):
    response = client.post("/api/errors/report", json=_report_body(error=""))
    assert response.status_code == 422


def test_error_report_caps_pathological_sizes(client):
    response = client.post(
        "/api/errors/report", json=_report_body(error="x" * 5000)
    )
    assert response.status_code == 422


def test_error_report_rejects_oversized_body(client):
    # 64KB+ body (content-length guard) — rejected before validation.
    response = client.post(
        "/api/errors/report",
        json=_report_body(context={"blob": "y" * (70 * 1024)}),
    )
    assert response.status_code == 413


def test_error_report_rejects_malformed_json(client):
    response = client.post(
        "/api/errors/report",
        content=b'{"error": not-json',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_error_report_redacts_secrets_from_logs(client, caplog):
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl"
    body = _report_body(
        error=f"401 with Authorization: Bearer {jwt} password=Hunter2!",
        stackTrace=f"frame1 token {jwt}\nframe2 api_key=0123456789abcdef0123456789abcdef",
        context={"authorization": f"Bearer {jwt}"},
    )

    with caplog.at_level("WARNING", logger="client_errors"):
        response = client.post("/api/errors/report", json=body)

    assert response.status_code == 202
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert jwt not in logged
    assert "Hunter2!" not in logged
    assert "0123456789abcdef0123456789abcdef" not in logged
    assert "[REDACTED_JWT]" in logged


def test_error_report_log_is_single_line(client, caplog):
    body = _report_body(
        error="line1\nFAKE-LOG-RECORD [ERROR] injected\nline3"
    )

    with caplog.at_level("WARNING", logger="client_errors"):
        response = client.post("/api/errors/report", json=body)

    assert response.status_code == 202
    report_records = [
        r for r in caplog.records if "Mobile client error" in r.getMessage()
    ]
    assert len(report_records) == 1
    # json.dumps escapes newlines, so the injected text cannot start a new
    # log record.
    assert "\n" not in report_records[0].getMessage()
