"""A failed analysis must report that it failed, not invent a finding.

Several AI/behaviour endpoints answered a caught exception with a plausible
payload instead of an empty one. Each of these was a statement about a real
person's money that nothing had computed:

    /api/ai/financial-health-score  -> score 50, grade "C", every component 50
    /api/ai/goal-analysis           -> on_track True
    /api/ai/spending-prediction     -> trend "stable"
    /api/ai/weekly-insights         -> trend "stable"
    /api/behavior/analysis          -> behavioral_score 0.5
    /api/behavior/patterns          -> dominant_pattern "balanced"

The mobile app already guards on null for several of these — for example
insights_screen renders "Add more transactions to calculate your financial
health score" when score/grade are null. These fallbacks were the reason those
guards never fired.

The endpoints must still return 200: the degradation requirement is that a
broken analyzer does not 500 the screen.
"""

import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@localhost:5432/test_mita?sslmode=disable"
)
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("FIREBASE_JSON", "{}")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_min_32_chars_long_for_testing")

dummy = types.ModuleType("firebase_admin")
dummy._apps = []
dummy.credentials = types.SimpleNamespace(
    ApplicationDefault=lambda: None, Certificate=lambda *a, **k: None
)
dummy.initialize_app = lambda cred=None: None
dummy.firestore = types.SimpleNamespace(client=lambda: None)
dummy.messaging = types.SimpleNamespace(
    Message=lambda **kwargs: None, send=lambda message: "mock_message_id"
)
sys.modules.setdefault("firebase_admin", dummy)
sys.modules.setdefault("firebase_admin.credentials", dummy.credentials)
sys.modules.setdefault("firebase_admin.firestore", dummy.firestore)
sys.modules.setdefault("firebase_admin.messaging", dummy.messaging)

from app.api.dependencies import get_current_user  # noqa: E402
from app.core.async_session import get_async_db  # noqa: E402
from app.core.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    return SimpleNamespace(
        id="test_user_verdicts",
        email="verdicts@example.com",
        is_premium=True,
        timezone="UTC",
        monthly_income=5000.0,
    )


@pytest.fixture
def mock_async_db():
    db = Mock()
    db.execute = AsyncMock()
    db.run_sync = AsyncMock(side_effect=lambda fn: fn(Mock()))
    return db


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides = {}


class TestAIVerdicts:
    @pytest.fixture(autouse=True)
    def _overrides(self, mock_user, mock_async_db):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_async_db] = lambda: mock_async_db

    def test_goal_analysis_does_not_claim_on_track(self, client):
        """on_track True told the user a goal was on track after a failure."""
        with patch("app.api.ai.routes.AIFinancialAnalyzer") as analyzer:
            analyzer.side_effect = RuntimeError("analyzer unavailable")
            payload = client.get("/api/ai/goal-analysis").json()["data"]

        assert payload["on_track"] is None
        assert payload["confidence"] == 0.0
        assert "error" in payload

    def test_spending_prediction_reports_no_trend(self, client):
        with patch("app.api.ai.routes.AIFinancialAnalyzer") as analyzer:
            analyzer.side_effect = RuntimeError("analyzer unavailable")
            payload = client.get("/api/ai/spending-prediction").json()["data"]

        assert payload["trend"] is None
        assert payload["predicted_amount"] == 0.0
        assert payload["confidence"] == 0.0

    def test_weekly_insights_reports_no_trend(self, client):
        with patch("app.api.ai.routes.AIFinancialAnalyzer") as analyzer:
            analyzer.side_effect = RuntimeError("analyzer unavailable")
            payload = client.get("/api/ai/weekly-insights").json()["data"]

        assert payload["trend"] is None
        assert payload["recommendations"] == []

    def test_all_degraded_ai_endpoints_still_answer_200(self, client):
        """Degrading must not 500 the screen."""
        for path in (
            "/api/ai/financial-health-score",
            "/api/ai/goal-analysis",
            "/api/ai/spending-prediction",
            "/api/ai/weekly-insights",
        ):
            with patch("app.api.ai.routes.AIFinancialAnalyzer") as analyzer:
                analyzer.side_effect = RuntimeError("analyzer unavailable")
                assert client.get(path).status_code == 200, path


class TestBehaviourVerdicts:
    @pytest.fixture(autouse=True)
    def _overrides(self, mock_user):
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db] = lambda: Mock()

    def test_analysis_does_not_invent_a_behavioural_score(self, client):
        """0.5 read as a real mid-scale measurement of the user."""
        with patch(
            "app.api.behavior.routes.analyze_user_behavior",
            side_effect=RuntimeError("unavailable"),
        ):
            payload = client.get("/api/behavior/analysis").json()["data"]

        assert payload["behavioral_score"] is None
        assert payload["spending_patterns"] == []

    def test_patterns_does_not_name_a_dominant_pattern(self, client):
        """ "balanced" is a verdict on how this person spends."""
        with patch(
            "app.api.behavior.routes.extract_patterns",
            side_effect=RuntimeError("unavailable"),
        ):
            payload = client.get("/api/behavior/patterns").json()["data"]

        assert payload["dominant_pattern"] is None
        assert payload["patterns"] == []
        assert payload["confidence"] == 0.0
