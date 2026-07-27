"""TASK-15 regressions: the challenge endpoints answer with valid schemas.

Before the fix every POST here 500'd (adversarial-audit.md N-P2-CHALLENGE):
/eligibility called the DB-backed check_eligibility without its Session,
/check aliased evaluate_challenge to check_eligibility with a calendar as
user_id, and /streak fed (calendar, user_id, log_data) into
run_streak_challenge(user_id, challenge_id, required_days, db). The
leaderboard was also unreachable — declared after /{challenge_id}, FastAPI
matched "leaderboard" as a challenge id.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Challenge, ChallengeParticipation, User

TODAY = datetime.now(timezone.utc).date()
MONTH = TODAY.strftime("%Y-%m")


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db_session():
    import app.core.session as session_module

    gen = session_module.get_db()
    db = next(gen)
    try:
        yield db
    finally:
        gen.close()


@pytest.fixture
def user(db_session):
    u = User(
        id=uuid4(),
        email=f"challenge_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    yield u
    db_session.query(ChallengeParticipation).filter_by(user_id=u.id).delete()
    db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


@pytest.fixture
def challenge(db_session):
    ch = Challenge(
        id=f"contract_streak_{uuid4().hex[:8]}",
        name="Test savings streak",
        description="Integration challenge",
        type="streak",
        duration_days=7,
        reward_points=10,
        difficulty="easy",
        start_month=MONTH,
        end_month=MONTH,
    )
    db_session.add(ch)
    db_session.commit()
    yield ch
    db_session.query(ChallengeParticipation).filter_by(challenge_id=ch.id).delete()
    db_session.query(Challenge).filter_by(id=ch.id).delete()
    db_session.commit()


@pytest.fixture
def authed(client, user):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _calendar(days=31, overspent_day=None):
    first = TODAY.replace(day=1)
    out = []
    for i in range(days):
        d = first + timedelta(days=i)
        if d.month != first.month:
            break
        status = "overspent" if d.day == overspent_day else "within"
        out.append({"date": d.isoformat(), "status": {"food": status}})
    return out


class TestEligibility:
    def test_lists_joinable_challenges(self, authed, user, challenge):
        resp = authed.post(
            "/api/challenge/eligibility",
            json={"user_id": str(user.id), "current_month": MONTH},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["user_id"] == str(user.id)
        assert data["eligible"] is True
        ids = [c["challenge_id"] for c in data["available_challenges"]]
        assert challenge.id in ids

    def test_joined_challenge_not_listed(self, authed, db_session, user, challenge):
        db_session.add(
            ChallengeParticipation(
                user_id=user.id,
                challenge_id=challenge.id,
                month=MONTH,
                status="active",
                started_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()

        resp = authed.post(
            "/api/challenge/eligibility",
            json={"current_month": MONTH},  # user_id is session-bound
        )
        assert resp.status_code == 200, resp.text
        ids = [c["challenge_id"] for c in resp.json()["data"]["available_challenges"]]
        assert challenge.id not in ids

    def test_foreign_user_id_is_403(self, authed, user):
        resp = authed.post(
            "/api/challenge/eligibility",
            json={"user_id": str(uuid4()), "current_month": MONTH},
        )
        assert resp.status_code == 403, resp.text


class TestCheck:
    def test_clean_month_counts_streak(self, authed):
        resp = authed.post(
            "/api/challenge/check",
            json={
                "calendar": _calendar(),
                "today_date": TODAY.isoformat(),
                "challenge_log": {},
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "eligible" in data
        assert data["streak_days"] == TODAY.day

    def test_overspent_day_breaks_streak(self, authed):
        resp = authed.post(
            "/api/challenge/check",
            json={
                "calendar": _calendar(overspent_day=1),
                "today_date": TODAY.isoformat(),
                "challenge_log": {},
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["eligible"] is False
        assert data["streak_days"] == 0


class TestStreak:
    def test_streak_shape_and_identity(self, authed, user):
        resp = authed.post(
            "/api/challenge/streak",
            json={
                "calendar": _calendar(),
                "user_id": str(user.id),
                "log_data": {},
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["user_id"] == str(user.id)
        for key in ("streak_eligible", "claimable", "streak_days", "date"):
            assert key in data

    def test_foreign_user_id_is_403(self, authed):
        resp = authed.post(
            "/api/challenge/streak",
            json={
                "calendar": _calendar(),
                "user_id": str(uuid4()),
                "log_data": {},
            },
        )
        assert resp.status_code == 403, resp.text


class TestRouting:
    def test_leaderboard_is_reachable(self, authed, db_session, user, challenge):
        """Route-ordering regression: /leaderboard must not be captured by
        /{challenge_id}."""
        db_session.add(
            ChallengeParticipation(
                user_id=user.id,
                challenge_id=challenge.id,
                month=MONTH,
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()

        resp = authed.get("/api/challenge/leaderboard")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "top_users" in data and "total_participants" in data
        assert data["total_participants"] >= 1
        assert any(entry["user_id"] == str(user.id) for entry in data["top_users"])

    def test_unknown_challenge_is_404(self, authed):
        resp = authed.get(f"/api/challenge/nonexistent-{uuid4().hex[:6]}")
        assert resp.status_code == 404, resp.text

    def test_join_and_progress_roundtrip(self, authed, db_session, user, challenge):
        resp = authed.post(f"/api/challenge/{challenge.id}/join")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["joined"] is True

        resp = authed.get(f"/api/challenge/{challenge.id}/progress")
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "active"
