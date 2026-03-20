"""
Tests for velocity_alert_service.py

Uses SQLite in-memory database for realistic SQL query testing.
Mocks the notification layer to avoid external calls.

Coverage:
  TestDeduplication     — cooldown suppresses repeated alerts
  TestNotificationLevel — correct notification method called per level
  TestWinNotifications  — win notifications + deduplication
  TestRealTimeTrigger   — check_velocity_after_transaction entry point
  TestErrorHandling     — non-blocking on errors
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import TypeDecorator, CHAR
import uuid

# ---------------------------------------------------------------------------
# Minimal in-memory schema (mirrors production models)
# ---------------------------------------------------------------------------

Base = declarative_base()


class UUIDType(TypeDecorator):
    """Store UUID as CHAR(36) in SQLite."""
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value)


class User(Base):
    __tablename__ = "users"
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, default="x")
    timezone = Column(String, default="UTC")
    monthly_income = Column(Numeric, default=0)
    notifications_enabled = Column(Boolean, default=True)
    has_onboarded = Column(Boolean, default=True)
    name = Column(String, nullable=True)
    savings_goal = Column(Numeric, default=0)
    budget_method = Column(String, default="50/30/20")
    currency = Column(String(3), default="USD")
    country = Column(String(2), default="US")
    annual_income = Column(Numeric, default=0)
    is_premium = Column(Boolean, default=False)
    token_version = Column(String, default="1")
    failed_login_attempts = Column(String, default="0")
    password_reset_attempts = Column(String, default="0")
    email_verified = Column(Boolean, default=False)
    dark_mode_enabled = Column(Boolean, default=False)


class DailyPlan(Base):
    __tablename__ = "daily_plan"
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUIDType, nullable=False)
    date = Column(DateTime, nullable=False)
    category = Column(String(100), nullable=True)
    planned_amount = Column(Numeric(12, 2), default=0)
    spent_amount = Column(Numeric(12, 2), default=0)
    daily_budget = Column(Numeric(12, 2), nullable=True)
    status = Column(String(20), default="green")
    goal_id = Column(UUIDType, nullable=True)


class Goal(Base):
    __tablename__ = "goals"
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUIDType, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    target_amount = Column(Numeric(10, 2), nullable=False)
    saved_amount = Column(Numeric(10, 2), default=0)
    monthly_contribution = Column(Numeric(10, 2), nullable=True)
    status = Column(String(20), default="active")
    progress = Column(Numeric(5, 2), default=0)
    target_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    priority = Column(String(10), default="medium")


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUIDType, nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), default="info")
    priority = Column(String(20), default="medium")
    image_url = Column(String(500), nullable=True)
    action_url = Column(String(500), nullable=True)
    data = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    channel = Column(String(20), nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(String, default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    category = Column(String(50), nullable=True)
    group_key = Column(String(100), nullable=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def user_id():
    return uuid4()


def _add_daily_plans(db, user_id, category, planned, spent_per_day, days=10,
                     year=2026, month=3):
    """Insert DailyPlan rows with the given planned and spent amounts per row."""
    for d in range(1, days + 1):
        dp = DailyPlan(
            id=uuid4(),
            user_id=user_id,
            date=datetime(year, month, d, 12, 0, 0),
            category=category,
            planned_amount=Decimal(str(planned)),
            spent_amount=Decimal(str(spent_per_day)),
        )
        db.add(dp)
    db.commit()


def _add_daily_plans_at_ratio(db, user_id, category, target_ratio, days=10,
                               year=2026, month=3):
    """
    Insert `days` DailyPlan rows achieving the target velocity_ratio.

    Formula (31-day month, spent_per_row = $10):
        planned_per_row = 31 / target_ratio

    Result:
        monthly_planned   = days * planned_per_row
        planned_per_day   = monthly_planned / 31 = days * planned_per_row / 31
        daily_pace        = (days * 10) / days = 10
        velocity_ratio    = 10 / planned_per_day = 31 / planned_per_row = target_ratio
    """
    from decimal import ROUND_HALF_UP as _RHU
    planned_row = (Decimal("31") / Decimal(str(target_ratio))).quantize(
        Decimal("0.01"), _RHU
    )
    for d in range(1, days + 1):
        dp = DailyPlan(
            id=uuid4(),
            user_id=user_id,
            date=datetime(year, month, d, 12, 0, 0),
            category=category,
            planned_amount=planned_row,
            spent_amount=Decimal("10.00"),
        )
        db.add(dp)
    db.commit()


def _add_notification(db, user_id, group_key, created_at=None):
    n = Notification(
        id=uuid4(),
        user_id=user_id,
        title="test",
        message="test",
        group_key=group_key,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(n)
    db.commit()
    return n


# ---------------------------------------------------------------------------
# Patches — swap production models for test models inside the service
# ---------------------------------------------------------------------------

def _patch_models(monkeypatch, db):
    """Redirect service imports to use in-memory test models."""
    import app.services.velocity_alert_service as svc

    monkeypatch.setattr(svc, "DailyPlan", DailyPlan)
    monkeypatch.setattr(svc, "Goal", Goal)
    monkeypatch.setattr(svc, "Notification", Notification)
    monkeypatch.setattr(svc, "User", User)


def _mock_notifier():
    notifier = MagicMock()
    notifier.notify_velocity_watch = MagicMock()
    notifier.notify_velocity_warning = MagicMock()
    notifier.notify_velocity_critical = MagicMock()
    notifier.notify_spending_win = MagicMock()
    return notifier


# ---------------------------------------------------------------------------
# TestDeduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    """Cooldown window prevents duplicate alerts."""

    def test_no_duplicate_within_24h(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        _add_daily_plans(db, user_id, "dining_out", 10, 30)  # 3× → CRITICAL

        notifier = _mock_notifier()
        today = date(2026, 3, 10)
        group_key = f"velocity_alert:{user_id}:dining_out:2026-03"
        # Pre-insert a recent notification for this group_key
        _add_notification(db, user_id, group_key, created_at=datetime.utcnow())

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)

        notifier.notify_velocity_critical.assert_not_called()

    def test_alert_sent_after_cooldown_expires(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        _add_daily_plans(db, user_id, "gaming", 10, 30)

        notifier = _mock_notifier()
        today = date(2026, 3, 10)
        group_key = f"velocity_alert:{user_id}:gaming:2026-03"
        # Pre-insert an OLD notification (>24 h ago)
        old_time = datetime.utcnow() - timedelta(hours=25)
        _add_notification(db, user_id, group_key, created_at=old_time)

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)

        notifier.notify_velocity_critical.assert_called_once()

    def test_first_alert_always_sent(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        _add_daily_plans(db, user_id, "hobbies", 10, 20)  # 2× → CRITICAL

        notifier = _mock_notifier()
        today = date(2026, 3, 10)

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)

        assert (
            notifier.notify_velocity_critical.called
            or notifier.notify_velocity_warning.called
            or notifier.notify_velocity_watch.called
        )

    def test_different_category_not_suppressed(self, db, user_id, monkeypatch):
        """Cooldown for dining_out doesn't suppress gaming alert."""
        _patch_models(monkeypatch, db)
        _add_daily_plans(db, user_id, "dining_out", 10, 30)
        _add_daily_plans(db, user_id, "gaming", 10, 30)

        notifier = _mock_notifier()
        today = date(2026, 3, 10)
        # Suppress dining_out
        _add_notification(
            db, user_id,
            f"velocity_alert:{user_id}:dining_out:2026-03",
        )

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)

        # gaming should still fire
        notifier.notify_velocity_critical.assert_called()

    def test_win_cooldown_7_days(self, db, user_id, monkeypatch):
        """Win notifications are suppressed within the 7-day window."""
        _patch_models(monkeypatch, db)
        # 10 good days
        for d in range(1, 11):
            dp = DailyPlan(
                id=uuid4(),
                user_id=user_id,
                date=datetime(2026, 3, d, 12, 0, 0),
                category="dining_out",
                planned_amount=Decimal("20.00"),
                spent_amount=Decimal("8.00"),
            )
            db.add(dp)
        db.commit()

        notifier = _mock_notifier()
        today = date(2026, 3, 10)
        group_key = f"spending_win:{user_id}:streak_7:2026-03"
        _add_notification(db, user_id, group_key)

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)

        notifier.notify_spending_win.assert_not_called()


# ---------------------------------------------------------------------------
# TestNotificationLevel
# ---------------------------------------------------------------------------

class TestNotificationLevel:
    """Correct notifier method is called for each alert level."""

    def _run_at_ratio(self, db, user_id, monkeypatch, target_ratio, notifier):
        _add_daily_plans_at_ratio(db, user_id, "dining_out", target_ratio)
        today = date(2026, 3, 10)
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)

    def test_watch_level(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        notifier = _mock_notifier()
        # planned_per_row = 31/1.25 = 24.80 → ratio = 1.25 → WATCH
        self._run_at_ratio(db, user_id, monkeypatch, target_ratio=1.25, notifier=notifier)
        notifier.notify_velocity_watch.assert_called_once()
        notifier.notify_velocity_warning.assert_not_called()
        notifier.notify_velocity_critical.assert_not_called()

    def test_warning_level(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        notifier = _mock_notifier()
        # ratio = 1.60 → WARNING
        self._run_at_ratio(db, user_id, monkeypatch, target_ratio=1.60, notifier=notifier)
        notifier.notify_velocity_warning.assert_called_once()
        notifier.notify_velocity_critical.assert_not_called()

    def test_critical_level(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        notifier = _mock_notifier()
        # ratio = 2.50 → CRITICAL
        self._run_at_ratio(db, user_id, monkeypatch, target_ratio=2.50, notifier=notifier)
        notifier.notify_velocity_critical.assert_called_once()

    def test_no_alert_when_on_track(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        notifier = _mock_notifier()
        # ratio = 0.90 → well under WATCH (1.20)
        self._run_at_ratio(db, user_id, monkeypatch, target_ratio=0.90, notifier=notifier)
        notifier.notify_velocity_watch.assert_not_called()
        notifier.notify_velocity_warning.assert_not_called()
        notifier.notify_velocity_critical.assert_not_called()


# ---------------------------------------------------------------------------
# TestWinNotifications
# ---------------------------------------------------------------------------

class TestWinNotifications:
    """Win notifications are sent for genuine streaks."""

    def _add_good_days(self, db, user_id, days=10):
        for d in range(1, days + 1):
            dp = DailyPlan(
                id=uuid4(),
                user_id=user_id,
                date=datetime(2026, 3, d, 12, 0, 0),
                category="dining_out",
                planned_amount=Decimal("20.00"),
                spent_amount=Decimal("8.00"),  # 40% of planned
            )
            db.add(dp)
        db.commit()

    def test_win_notification_sent_for_streak(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        self._add_good_days(db, user_id, days=10)
        notifier = _mock_notifier()
        today = date(2026, 3, 10)
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)
        notifier.notify_spending_win.assert_called_once()

    def test_win_not_sent_for_short_streak(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        self._add_good_days(db, user_id, days=5)
        notifier = _mock_notifier()
        today = date(2026, 3, 5)
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            run_velocity_check_for_user(db=db, user_id=user_id, today=today)
        notifier.notify_spending_win.assert_not_called()

    def test_win_not_sent_from_realtime_trigger(self, db, user_id, monkeypatch):
        """Real-time check_velocity_after_transaction must NOT send wins."""
        _patch_models(monkeypatch, db)
        self._add_good_days(db, user_id, days=10)
        notifier = _mock_notifier()
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import check_velocity_after_transaction
            check_velocity_after_transaction(
                db=db,
                user_id=user_id,
                category="dining_out",
                transaction_date=date(2026, 3, 10),
            )
        notifier.notify_spending_win.assert_not_called()


# ---------------------------------------------------------------------------
# TestRealTimeTrigger
# ---------------------------------------------------------------------------

class TestRealTimeTrigger:
    """check_velocity_after_transaction is the real-time entry point."""

    def test_triggers_alert_for_overpace_category(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        _add_daily_plans(db, user_id, "gaming", 10, 30)  # 3× CRITICAL
        notifier = _mock_notifier()
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import check_velocity_after_transaction
            result = check_velocity_after_transaction(
                db=db,
                user_id=user_id,
                category="gaming",
                transaction_date=date(2026, 3, 10),
            )
        assert result is not None
        assert result.has_alerts()
        notifier.notify_velocity_critical.assert_called_once()

    def test_no_alert_for_on_track_category(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        # ratio = 0.90 → under plan → no alert
        _add_daily_plans_at_ratio(db, user_id, "gaming", 0.90)
        notifier = _mock_notifier()
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import check_velocity_after_transaction
            result = check_velocity_after_transaction(
                db=db,
                user_id=user_id,
                category="gaming",
                transaction_date=date(2026, 3, 10),
            )
        assert not result.has_alerts()

    def test_other_categories_ignored_in_realtime(self, db, user_id, monkeypatch):
        """Real-time only checks the category that was just modified."""
        _patch_models(monkeypatch, db)
        # dining_out is critical but gaming is on track
        _add_daily_plans(db, user_id, "dining_out", 10, 30)  # CRITICAL
        _add_daily_plans(db, user_id, "gaming", 10, 10)      # on track
        notifier = _mock_notifier()
        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import check_velocity_after_transaction
            # Only check gaming — dining_out should not appear
            result = check_velocity_after_transaction(
                db=db,
                user_id=user_id,
                category="gaming",
                transaction_date=date(2026, 3, 10),
            )
        for alert in result.alerts:
            assert alert.category == "gaming"


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Service must be non-blocking even when notifications fail."""

    def test_notification_failure_does_not_crash(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)
        _add_daily_plans(db, user_id, "gaming", 10, 30)

        broken_notifier = MagicMock()
        broken_notifier.notify_velocity_critical.side_effect = RuntimeError("FCM down")

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=broken_notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            # Must not raise
            result = run_velocity_check_for_user(
                db=db, user_id=user_id, today=date(2026, 3, 10)
            )
        # Result is still returned even though notification failed
        assert result is not None

    def test_realtime_trigger_non_blocking(self, db, user_id, monkeypatch):
        _patch_models(monkeypatch, db)

        with patch("app.services.velocity_alert_service._run_velocity_check",
                   side_effect=RuntimeError("DB exploded")):
            from app.services.velocity_alert_service import check_velocity_after_transaction
            result = check_velocity_after_transaction(
                db=db,
                user_id=user_id,
                category="gaming",
                transaction_date=date(2026, 3, 10),
            )
        # Returns None gracefully
        assert result is None

    def test_missing_user_does_not_crash(self, db, monkeypatch):
        """Non-existent user_id → empty plans → graceful empty result."""
        _patch_models(monkeypatch, db)
        notifier = _mock_notifier()
        phantom_id = uuid4()

        with patch("app.services.velocity_alert_service.get_notification_integration",
                   return_value=notifier):
            from app.services.velocity_alert_service import run_velocity_check_for_user
            result = run_velocity_check_for_user(
                db=db, user_id=phantom_id, today=date(2026, 3, 10)
            )
        assert result is not None
        assert not result.has_alerts()
        notifier.notify_velocity_critical.assert_not_called()
