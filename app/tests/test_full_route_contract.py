"""Full-route backend contract suite (TASK-6).

Every mounted FastAPI route is enumerated at collection time and must be
covered here — either by an executable spec (a valid authenticated request
built from seeded data, driven through the REAL async dependency injection
against PostgreSQL) or by an explicit, documented exclusion. A new route that
lands without a spec fails `test_every_mounted_route_is_covered`.

Why this exists (test-gap-analysis.md FC-4): broken endpoints with no mobile
caller (`/analytics/monthly`, `/goals/budget/*`, `/challenge/*`, `/ai/*`)
shipped green because nothing exercised them. This suite is the backstop:
**every supported route must return non-5xx for a valid request**, and the
core financial areas additionally assert response content and DB state.

External boundaries only (OpenAI rating, Firestore drift, SMTP) are stubbed;
sessions, routing, validation and persistence are always real.

Requires: PostgreSQL at DATABASE_URL (test_mita) with migrations at head,
Redis at REDIS_URL (rate limiter + task queue).
"""

import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Route enumeration (collection time)
# ---------------------------------------------------------------------------


def _mounted_routes():
    from app.main import app

    seen = {}
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                seen[(m, r.path)] = True
    return sorted(seen)


MOUNTED = _mounted_routes()

NOW = datetime.now(timezone.utc)
TODAY = NOW.date()
YM = {"year": NOW.year, "month": NOW.month}


def _make_png() -> bytes:
    """A real (Pillow-decodable) PNG for upload endpoints."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (250, 250, 250)).save(buf, format="PNG")
    return buf.getvalue()


_PNG = _make_png()


def _upload(name="receipt.png"):
    return {"file": (name, io.BytesIO(_PNG), "image/png")}


def _engine_calendar(days=31):
    """Calendar shape consumed by the challenge/spend/checkpoint engines."""
    first = TODAY.replace(day=1)
    out = []
    for i in range(days):
        d = first + timedelta(days=i)
        if d.month != first.month:
            break
        out.append(
            {
                "date": d.isoformat(),
                "day": d.day,
                "total": 10.0,
                "planned_budget": {"food": 20.0},
                "actual_spending": {"food": 10.0},
                "limit": 20.0,
                "status": {"food": "within"},
            }
        )
    return out


def _extract_id(resp):
    """Pull the created-resource id out of enveloped or bare responses."""
    body = resp.json()
    data = body
    if isinstance(body, dict) and body.get("success") is True and "data" in body:
        data = body["data"]
    for key in (
        "goal",
        "habit",
        "installment",
        "expense",
        "notification",
        "transaction",
    ):
        if isinstance(data, dict) and isinstance(data.get(key), dict):
            data = data[key]
    assert isinstance(data, dict) and data.get("id"), f"no id in response: {body}"
    return str(data["id"])


class _FakeFirestoreDoc:
    def __init__(self, store, key):
        self.store, self.key = store, key

    def set(self, value):
        self.store[self.key] = value

    def get(self):
        store, key = self.store, self.key

        class _Snap:
            exists = key in store

            def to_dict(self):
                return store.get(key)

        return _Snap()


class _FakeFirestore:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        outer = self

        class _Doc:
            def __init__(self, value):
                self._value = value

            def to_dict(self):
                return self._value

        class _Query:
            def __init__(self, field, value):
                self.field, self.value = field, value

            def stream(self):
                return [
                    _Doc(v)
                    for k, v in outer.data.items()
                    if k.startswith(f"{name}/")
                    and isinstance(v, dict)
                    and v.get(self.field) == self.value
                ]

        class _Coll:
            def document(self, doc_id):
                return _FakeFirestoreDoc(outer.data, f"{name}/{doc_id}")

            def where(self, field, op, value):
                assert op == "=="
                return _Query(field, value)

        return _Coll()


# ---------------------------------------------------------------------------
# Fixtures: one app client, seeded users/resources, switchable auth actor
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="module")
def ctx(client):
    """Seeded context shared by every route spec."""
    import app.core.session as session_module
    from app.api.dependencies import get_current_user
    from app.main import app

    gen = session_module.get_db()
    db = next(gen)

    from app.db.models import User

    user = User(
        id=uuid4(),
        email=f"contract_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=False,
        timezone="UTC",
        is_premium=True,
    )
    admin = User(
        id=uuid4(),
        email=f"contract_admin_{uuid4().hex[:10]}@mita.app",
        password_hash="hashed_password_123",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal("6000.00"),
        is_premium=True,
    )
    db.add_all([user, admin])
    db.commit()
    db.refresh(user)
    db.refresh(admin)
    # Transient auth attributes checked by require_admin_access /
    # require_premium_user (scope checks read instance attributes).
    from app.services.auth_jwt_service import TokenScope

    user._token_scopes = [TokenScope.PREMIUM_FEATURES.value]
    admin._token_scopes = [TokenScope.ADMIN_SYSTEM.value]
    admin.is_admin = True

    holder = {"actor": user, "user": user, "admin": admin, "db": db}
    app.dependency_overrides[get_current_user] = lambda: holder["actor"]

    # --- seed the core journey through the REAL API -------------------------
    r = client.post(
        "/api/onboarding/submit",
        json={
            "income": {"monthly_income": 6000.00, "additional_income": 0},
            "fixed_expenses": {"rent": 1500.00, "utilities": 200.00},
            "spending_habits": {"dining_out_per_month": 4},
            "goals": {"savings_goal_amount_per_month": 400.00},
            "region": "US",
        },
    )
    assert r.status_code == 200, f"seed onboarding failed: {r.status_code} {r.text}"
    db.refresh(user)  # pick up has_onboarded/monthly_income set by the API

    r = client.post(
        "/api/transactions/",
        json={
            "amount": 42.00,
            "category": "food",
            "description": "contract seed txn",
            "spent_at": NOW.isoformat(),
        },
    )
    assert r.status_code in (200, 201), f"seed txn failed: {r.text}"
    holder["txn_id"] = _extract_id(r)

    r = client.post(
        "/api/goals/",
        json={
            "title": "Emergency fund",
            "target_amount": 1000.00,
            "monthly_contribution": 50.00,
        },
    )
    assert r.status_code in (200, 201), f"seed goal failed: {r.text}"
    holder["goal_id"] = _extract_id(r)

    r = client.post("/api/habits/", json={"title": "Log expenses"})
    assert r.status_code in (200, 201), f"seed habit failed: {r.text}"
    holder["habit_id"] = _extract_id(r)

    first_payment = NOW + timedelta(days=7)
    r = client.post(
        "/api/installments/",
        json={
            "item_name": "Laptop",
            "category": "electronics",
            "total_amount": "1200.00",
            "payment_amount": "100.00",
            "total_payments": 12,
            "first_payment_date": first_payment.isoformat(),
            "next_payment_date": first_payment.isoformat(),
        },
    )
    assert r.status_code in (200, 201), f"seed installment failed: {r.text}"
    holder["installment_id"] = _extract_id(r)

    r = client.post(
        "/api/scheduled-expenses/",
        json={
            "category": "utilities",
            "amount": "60.00",
            "scheduled_date": (TODAY + timedelta(days=10)).isoformat(),
            "description": "internet bill",
        },
    )
    assert r.status_code in (200, 201), f"seed scheduled expense failed: {r.text}"
    holder["scheduled_expense_id"] = _extract_id(r)

    r = client.post(
        "/api/notifications/create",
        json={"title": "Contract test", "message": "seeded notification"},
    )
    assert r.status_code in (200, 201), f"seed notification failed: {r.text}"
    holder["notification_id"] = _extract_id(r)

    r = client.post("/api/mood/", json={"date": TODAY.isoformat(), "mood": "happy"})
    assert r.status_code in (200, 201), f"seed mood failed: {r.text}"

    yield holder

    # --- cleanup -------------------------------------------------------------
    app.dependency_overrides.pop(get_current_user, None)
    from sqlalchemy import text

    for uid in (user.id, admin.id):
        for table in (
            "ai_analysis_snapshots",
            "transactions",
            "daily_plan",
            "goals",
            "habits",
            "installments",
            "scheduled_expenses",
            "notifications",
            "moods",
            "user_preferences",
            "budget_advice",
            "push_tokens",
            "notification_logs",
            "challenge_participations",
            "user_profiles",
            "subscriptions",
        ):
            try:
                db.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :uid"),  # nosec B608
                    {"uid": str(uid)},
                )
                db.commit()
            except Exception:
                db.rollback()
        try:
            db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(uid)})
            db.commit()
        except Exception:
            db.rollback()
    gen.close()


@pytest.fixture
def as_actor(ctx):
    """Restore the default actor after each test."""
    yield
    ctx["actor"] = ctx["user"]


# ---------------------------------------------------------------------------
# Spec table
#
# Keys are (METHOD, mounted path template). Values:
#   path    — dict or callable(ctx) -> path params
#   query   — dict or callable(ctx)
#   json    — body, dict/list or callable(ctx)
#   files   — callable() -> files mapping (multipart uploads)
#   actor   — "user" (default) or "admin"
#   expect  — allowed status codes (default (200,)); non-5xx is always enforced
#   check   — callable(body_json, ctx): content assertions
#   patches — list of (import path, attr, value factory) monkeypatches for
#             EXTERNAL boundaries only (never session/route plumbing)
# ---------------------------------------------------------------------------


def _wrapped(body):
    assert body.get("success") is True, f"expected success envelope: {body}"
    return body.get("data")


def _check_dashboard(body, ctx):
    data = _wrapped(body)
    assert float(data["balance"]) == pytest.approx(6000.00 - 42.00)
    assert float(data["spent"]) == pytest.approx(42.00)


def _check_txn_list(body, ctx):
    data = _wrapped(body)
    txns = data.get("transactions", data) if isinstance(data, dict) else data
    assert any(str(t["id"]) == ctx["txn_id"] for t in txns)


def _check_calendar_month(body, ctx):
    data = _wrapped(body)
    days = data.get("calendar", data) if isinstance(data, dict) else data
    assert days, f"empty calendar: {body}"


def _check_monthly_analytics(body, ctx):
    data = _wrapped(body)
    totals = {c["category"]: c["total"] for c in data["categories"]}
    assert totals.get("food") == pytest.approx(42.00)


def _check_goals_budget_allocate(body, ctx):
    data = _wrapped(body)
    assert data["monthly_income"] == pytest.approx(6000.00)
    assert data["existing_expenses"] == pytest.approx(42.00)


def _check_challenge_eligibility(body, ctx):
    data = _wrapped(body)
    assert "eligible" in data and "available_challenges" in data


def _check_challenge_check(body, ctx):
    data = _wrapped(body)
    assert "eligible" in data and "streak_days" in data


def _check_challenge_streak(body, ctx):
    data = _wrapped(body)
    assert data["user_id"] == str(ctx["user"].id)
    assert "streak_eligible" in data and "streak_days" in data


def _check_cohort_income(body, ctx):
    data = _wrapped(body)
    assert data.get("income_classification") or data.get("tier") or data


def _check_budget_spent(body, ctx):
    # BudgetTracker.get_spent() returns a per-category map for the month.
    data = _wrapped(body)
    if float(data.get("food", 0)) != pytest.approx(42.00):
        db = ctx["db"]
        db.expire_all()
        from app.db.models import DailyPlan, Transaction

        plans = (
            db.query(DailyPlan.date, DailyPlan.category, DailyPlan.spent_amount)
            .filter(DailyPlan.user_id == ctx["user"].id)
            .filter(DailyPlan.spent_amount != 0)
            .all()
        )
        txns = (
            db.query(
                Transaction.spent_at,
                Transaction.category,
                Transaction.amount,
                Transaction.deleted_at,
            )
            .filter(Transaction.user_id == ctx["user"].id)
            .all()
        )
        pytest.fail(
            f"budget/spent food != 42: data={data}\n"
            f"nonzero plan rows={plans}\ntxns={txns}"
        )


def _fake_rating(*a, **k):
    return {"rating": "B", "risk": "moderate", "summary": "stubbed"}


def _fresh_habit(ctx, client):
    r = client.post("/api/habits/", json={"title": f"tmp {uuid4().hex[:6]}"})
    assert r.status_code in (200, 201), r.text
    return {"habit_id": _extract_id(r)}


def _fresh_goal(ctx, client):
    r = client.post(
        "/api/goals/", json={"title": f"tmp {uuid4().hex[:6]}", "target_amount": 10.0}
    )
    assert r.status_code in (200, 201), r.text
    return {"goal_id": _extract_id(r)}


def _fresh_installment(ctx, client):
    first_payment = NOW + timedelta(days=7)
    r = client.post(
        "/api/installments/",
        json={
            "item_name": f"tmp {uuid4().hex[:6]}",
            "category": "electronics",
            "total_amount": "100.00",
            "payment_amount": "10.00",
            "total_payments": 10,
            "first_payment_date": first_payment.isoformat(),
            "next_payment_date": first_payment.isoformat(),
        },
    )
    assert r.status_code in (200, 201), r.text
    return {"installment_id": _extract_id(r)}


def _fresh_scheduled_expense(ctx, client):
    r = client.post(
        "/api/scheduled-expenses/",
        json={
            "category": "utilities",
            "amount": "5.00",
            "scheduled_date": (TODAY + timedelta(days=5)).isoformat(),
        },
    )
    assert r.status_code in (200, 201), r.text
    return {"expense_id": _extract_id(r)}


def _fresh_notification(ctx, client):
    r = client.post(
        "/api/notifications/create",
        json={"title": "tmp", "message": f"tmp {uuid4().hex[:6]}"},
    )
    assert r.status_code in (200, 201), r.text
    return {"notification_id": _extract_id(r)}


def _fresh_txn(ctx, client):
    r = client.post(
        "/api/transactions/",
        json={
            "amount": 5.00,
            "category": "entertainment",
            "description": "contract fresh txn",
            "spent_at": NOW.isoformat(),
        },
    )
    assert r.status_code in (200, 201), r.text
    return {"transaction_id": _extract_id(r)}


SPECS = {
    # ---- public infra ------------------------------------------------------
    ("GET", "/"): {},
    ("GET", "/health"): {},
    ("GET", "/health/"): {},
    ("GET", "/health/api-keys"): {"actor": "admin", "expect": (200, 503)},
    ("GET", "/health/api-keys/validate"): {"actor": "admin", "expect": (200, 503)},
    ("GET", "/health/circuit-breakers"): {},
    ("POST", "/health/circuit-breakers/{service_name}/reset"): {
        "actor": "admin",
        "path": {"service_name": "openai"},
        "expect": (200, 404),
    },
    ("GET", "/health/critical-services"): {"actor": "admin", "expect": (200, 503)},
    ("GET", "/health/detailed"): {"actor": "admin", "expect": (200, 503)},
    ("GET", "/health/external-services"): {"actor": "admin", "expect": (200, 503)},
    ("GET", "/health/external-services/validate"): {
        "actor": "admin",
        "expect": (200, 503),
    },
    ("GET", "/health/monitoring/dashboard"): {"actor": "admin", "expect": (200, 503)},
    ("GET", "/health/services/test-connections"): {
        "actor": "admin",
        "expect": (200, 503),
    },
    ("GET", "/health/services/{service_name}"): {
        "actor": "admin",
        "path": {"service_name": "openai"},
        "expect": (200, 404, 503),
    },
    ("GET", "/health/services/{service_name}/test"): {
        "actor": "admin",
        "path": {"service_name": "openai"},
        "expect": (200, 404, 503),
    },
    ("GET", "/metrics"): {"expect": (200, 401, 403, 404)},
    ("GET", "/openapi.json"): {"expect": (200, 404)},
    ("GET", "/privacy-policy"): {},
    ("GET", "/terms-of-service"): {},
    # ---- waitlist (public) ---------------------------------------------------
    ("POST", "/api/waitlist/join"): {
        "json": lambda ctx: {"email": f"wl_{uuid4().hex[:8]}@mita-contract.dev"},
        "expect": (200, 201),
    },
    ("GET", "/api/waitlist/confirm/{token}"): {
        "path": {"token": "not-a-real-token"},
        "expect": (200, 302, 400, 404, 410),
    },
    ("GET", "/api/waitlist/status/{ref_code}"): {
        "path": {"ref_code": "NOPE42"},
        "expect": (200, 404),
    },
    # ---- auth router (real-token flows live in TestRealAuthJourney) ---------
    ("POST", "/api/auth/register"): {
        "json": lambda ctx: {
            "email": f"contract_reg_{uuid4().hex[:8]}@mita.app",
            "password": "Str0ng!passw0rd#2026",
            "country": "US",
        },
        "expect": (200, 201),
    },
    ("POST", "/api/auth/login"): {
        "json": {"email": "nobody@mita-contract.dev", "password": "Wrong!Pass1"},
        "expect": (401,),
    },
    ("POST", "/api/auth/refresh-token"): {
        "json": {"refresh_token": "garbage"},
        "expect": (401,),
    },
    ("POST", "/api/auth/logout"): {
        "json": {"refresh_token": "garbage"},
        "expect": (200, 401),
    },
    ("POST", "/api/auth/google"): {
        "json": {"id_token": "garbage-token"},
        "expect": (400, 401, 422, 503),
    },
    ("GET", "/api/auth/token/validate"): {
        # No real Bearer under the dependency override — 400 "token required";
        # the 200 path is asserted by TestRealAuthJourney with a real token.
        "expect": (200, 400, 401),
    },
    ("POST", "/api/auth/revoke"): {"expect": (200, 400, 401)},
    ("POST", "/api/auth/change-password"): {
        "query": {
            "current_password": "not-the-password",
            "new_password": "N3w!passw0rd#2026",
        },
        "expect": (200, 400, 401, 403),
    },
    ("DELETE", "/api/auth/delete-account"): {
        "query": {"confirmation": "false"},
        "expect": (400, 422),
    },
    ("POST", "/api/auth/forgot-password"): {
        "json": {"email": "nobody@mita-contract.dev"},
        "expect": (200, 202, 429),
    },
    ("POST", "/api/auth/password-reset/request"): {
        "query": {"email": "nobody@mita-contract.dev"},
        "expect": (200, 202, 429),
    },
    ("POST", "/api/auth/password-reset/confirm"): {
        "query": {
            "email": "nobody@mita-contract.dev",
            "token": "garbage",
            "new_password": "N3w!passw0rd#2026",
        },
        "expect": (400, 401, 404, 422),
    },
    ("POST", "/api/auth/reset-password"): {
        "json": {"token": "garbage", "new_password": "N3w!passw0rd#2026"},
        "expect": (400, 401, 404, 422),
    },
    ("GET", "/api/auth/verify-reset-token"): {
        "query": {"token": "garbage"},
        "expect": (200, 400, 401, 404, 422),
    },
    ("POST", "/api/auth/verify-reset-token"): {
        "query": {"token": "garbage"},
        "expect": (200, 400, 401, 404, 422),
    },
    ("GET", "/api/auth/security/password-config"): {
        "actor": "admin",
        "expect": (200, 401, 403),
    },
    ("GET", "/api/auth/security/status"): {
        "actor": "admin",
        "expect": (200, 401, 403),
    },
    ("GET", "/api/auth/admin/blacklist-metrics"): {
        "actor": "admin",
        "expect": (200, 401, 403),
    },
    ("POST", "/api/auth/admin/revoke-token-by-jti"): {
        "actor": "admin",
        "query": {"jti": f"contract-{uuid4().hex[:8]}", "reason": "contract test"},
        # 400: unknown/expired JTI is answered with the intentional 400
        # (previously re-wrapped into a 500 by the broad handler)
        "expect": (200, 400, 401, 403, 404),
    },
    ("POST", "/api/auth/admin/revoke-user-tokens"): {
        "actor": "admin",
        "query": lambda ctx: {
            "user_id": str(ctx["user"].id),
            "reason": "contract test",
        },
        "expect": (200, 401, 403),
    },
    ("GET", "/api/auth/admin/user-blacklisted-tokens/{user_id}"): {
        "actor": "admin",
        "path": lambda ctx: {"user_id": str(ctx["user"].id)},
        "expect": (200, 401, 403),
    },
    # ---- users ---------------------------------------------------------------
    ("GET", "/api/users/me"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("PATCH", "/api/users/me"): {
        "json": {"name": "Contract Tester"},
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/users/{user_id}/premium-features"): {
        "path": lambda ctx: {"user_id": str(ctx["user"].id)},
    },
    ("GET", "/api/users/{user_id}/premium-status"): {
        "path": lambda ctx: {"user_id": str(ctx["user"].id)},
    },
    ("GET", "/api/users/{user_id}/subscription-history"): {
        "path": lambda ctx: {"user_id": str(ctx["user"].id)},
    },
    # ---- onboarding -----------------------------------------------------------
    ("GET", "/api/onboarding/questions"): {},
    ("POST", "/api/onboarding/submit"): {
        # The ctx user already onboarded during seeding — the contract here is
        # the idempotent re-submit (INV-16).
        "json": {
            "income": {"monthly_income": 6000.00},
            "fixed_expenses": {"rent": 1500.00},
            "spending_habits": {},
            "goals": {},
        },
        "check": lambda body, ctx: _wrapped(body),
    },
    # ---- dashboard -------------------------------------------------------------
    ("GET", "/api/dashboard"): {"check": _check_dashboard},
    ("GET", "/api/dashboard/quick-stats"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    # ---- calendar ---------------------------------------------------------------
    ("GET", "/api/calendar/current-month"): {"check": _check_calendar_month},
    ("GET", "/api/calendar/saved/{year}/{month}"): {
        "path": dict(YM),
        "check": _check_calendar_month,
    },
    ("GET", "/api/calendar/day/{year}/{month}/{day}"): {
        "path": {**YM, "day": TODAY.day},
        "check": lambda body, ctx: _wrapped(body),
    },
    ("PATCH", "/api/calendar/day/{year}/{month}/{day}"): {
        "path": {**YM, "day": TODAY.day},
        "json": {"updates": {"food": 25.00}},
        "expect": (200, 400, 422),
    },
    ("POST", "/api/calendar/day_state"): {
        "json": {**YM, "day": TODAY.day},
    },
    ("POST", "/api/calendar/generate"): {
        "json": {
            "calendar_id": f"contract-{uuid4().hex[:6]}",
            "start_date": TODAY.replace(day=1).isoformat(),
            "num_days": 7,
            "budget_plan": {"food": 140.0, "transport": 70.0},
        },
    },
    ("POST", "/api/calendar/redistribute"): {
        # Engine contract: {day: {"total": spent, "limit": cap}}
        "json": {
            "calendar": {
                "1": {"total": 25.0, "limit": 20.0},
                "2": {"total": 5.0, "limit": 20.0},
            },
            "strategy": "balanced",
        },
        "check": lambda body, ctx: _wrapped(body)["updated_calendar"],
    },
    ("POST", "/api/calendar/shell"): {
        "json": {
            "savings_target": 400.0,
            "income": 6000.0,
            "fixed": {"rent": 1500.0},
            "weights": {"food": 0.5, "transport": 0.5},
            **YM,
        },
    },
    # ---- plan ---------------------------------------------------------------
    ("GET", "/api/plan/{year}/{month}"): {
        "path": dict(YM),
        "check": lambda body, ctx: _wrapped(body),
    },
    # ---- transactions ----------------------------------------------------------
    ("POST", "/api/transactions/"): {
        "json": {
            "amount": 7.50,
            "category": "shopping",
            "description": "contract create",
            "spent_at": NOW.isoformat(),
        },
        "expect": (200, 201),
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/transactions/"): {"check": _check_txn_list},
    ("GET", "/api/transactions/{transaction_id}"): {
        "path": lambda ctx: {"transaction_id": ctx["txn_id"]},
        "check": lambda body, ctx: _wrapped(body),
    },
    ("PUT", "/api/transactions/{transaction_id}"): {
        "setup": _fresh_txn,
        "json": {"description": "contract updated"},
        "check": lambda body, ctx: _wrapped(body),
    },
    ("DELETE", "/api/transactions/{transaction_id}"): {
        "setup": _fresh_txn,
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/transactions/by-date"): {
        "query": {
            "start_date": (TODAY - timedelta(days=7)).isoformat(),
            "end_date": TODAY.isoformat(),
        },
    },
    ("GET", "/api/transactions/budget-status"): {},
    ("POST", "/api/transactions/check-affordability"): {
        "json": {"category": "food", "amount": "15.00"},
    },
    ("GET", "/api/transactions/merchants/suggestions"): {
        "query": {"query": "star"},
    },
    ("POST", "/api/transactions/receipt"): {
        "files": _upload,
        "expect": (200, 201, 202, 400, 402, 422, 503),
    },
    ("POST", "/api/transactions/receipt/advanced"): {
        "files": _upload,
        "expect": (200, 201, 202, 400, 402, 422, 503),
    },
    ("POST", "/api/transactions/receipt/batch"): {
        "files": lambda: {"files": ("receipt.png", io.BytesIO(_PNG), "image/png")},
        "expect": (200, 201, 202, 400, 402, 422, 503),
    },
    ("POST", "/api/transactions/receipt/validate"): {
        "json": {"merchant": "Test Store", "amount": 12.34, "category": "food"},
        "expect": (200, 400, 422),
    },
    ("GET", "/api/transactions/receipt/status/{job_id}"): {
        "path": {"job_id": "nonexistent-job"},
        "expect": (200, 404),
    },
    ("GET", "/api/transactions/receipt/{receipt_id}/image"): {
        "path": {"receipt_id": "nonexistent-receipt"},
        "expect": (404,),
    },
    # ---- budget -----------------------------------------------------------------
    ("GET", "/api/budget/spent"): {"check": _check_budget_spent},
    ("GET", "/api/budget/remaining"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/budget/live_status"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/budget/daily"): {},
    ("GET", "/api/budget/forecast"): {},
    ("GET", "/api/budget/mode"): {},
    ("PATCH", "/api/budget/mode"): {"json": {"mode": "flexible"}},
    ("GET", "/api/budget/suggestions"): {},
    ("GET", "/api/budget/adaptations"): {},
    ("GET", "/api/budget/automation_settings"): {},
    ("PATCH", "/api/budget/automation_settings"): {
        "json": {"auto_redistribute": True},
    },
    ("POST", "/api/budget/auto_adapt"): {"expect": (200, 400)},
    ("POST", "/api/budget/monthly"): {"json": dict(YM)},
    ("POST", "/api/budget/behavioral_allocation"): {
        "json": {"total_amount": 3900.0},
        "check": lambda body, ctx: _wrapped(body),
    },
    ("POST", "/api/budget/income_based_recommendations"): {
        "json": {"monthly_income": 6000.0},
        "expect": (200, 400, 422),
    },
    ("GET", "/api/budget/redistribution_history"): {"query": {"limit": 5}},
    ("POST", "/api/budget/alert/ignored"): {
        "json": {"category": "food", "date": TODAY.isoformat()},
        "expect": (200, 201, 400, 422),
    },
    # ---- analytics -------------------------------------------------------------
    ("GET", "/api/analytics/monthly"): {"check": _check_monthly_analytics},
    ("GET", "/api/analytics/trend"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/analytics/behavioral-insights"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/analytics/seasonal-patterns"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("POST", "/api/analytics/aggregate"): {
        "json": {"calendar": _engine_calendar()},
        "expect": (200, 400, 422),
    },
    ("POST", "/api/analytics/anomalies"): {
        "json": {"calendar": _engine_calendar()},
        "expect": (200, 400, 422),
    },
    ("POST", "/api/analytics/feature-usage"): {
        "json": {"feature": "contract_test", "screen": "tests"},
        "expect": (200, 201),
    },
    ("POST", "/api/analytics/feature-access-attempt"): {
        "json": {"feature": "contract_test", "allowed": True},
        "expect": (200, 201),
    },
    ("POST", "/api/analytics/paywall-impression"): {
        "json": {"screen": "tests", "variant": "A"},
        "expect": (200, 201),
    },
    # ---- AI ----------------------------------------------------------------------
    ("GET", "/api/ai/spending-patterns"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/ai/financial-health-score"): {
        "check": lambda body, ctx: (lambda d: (d["score"], d["grade"]))(_wrapped(body)),
    },
    ("GET", "/api/ai/weekly-insights"): {},
    ("GET", "/api/ai/personalized-feedback"): {"query": dict(YM)},
    ("GET", "/api/ai/spending-anomalies"): {},
    ("GET", "/api/ai/savings-optimization"): {},
    ("GET", "/api/ai/day-status-explanation"): {
        "query": {"date": TODAY.isoformat()},
    },
    ("POST", "/api/ai/category-suggestions"): {
        "json": {"description": "coffee at starbucks", "amount": 4.50},
    },
    ("GET", "/api/ai/spending-prediction"): {
        "query": {"category": "food", "days": 7},
    },
    ("GET", "/api/ai/profile"): {"query": dict(YM)},
    ("GET", "/api/ai/financial-profile"): {"query": dict(YM)},
    ("GET", "/api/ai/goal-analysis"): {
        "query": lambda ctx: {"goal_id": ctx["goal_id"]},
    },
    ("GET", "/api/ai/monthly-report"): {"query": dict(YM)},
    ("POST", "/api/ai/assistant"): {
        "json": {"question": "How is my spending this month?"},
    },
    ("POST", "/api/ai/advice"): {
        "json": {"question": "How can I save more?"},
    },
    ("POST", "/api/ai/snapshot"): {
        "query": dict(YM),
        "patches": [
            (
                "app.services.core.engine.ai_snapshot_service",
                "generate_financial_rating",
                lambda: _fake_rating,
            )
        ],
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/ai/latest-snapshots"): {},
    ("GET", "/api/ai/budget-optimization"): {},
    # ---- goals CRUD ------------------------------------------------------------
    ("POST", "/api/goals/"): {
        "json": {"title": "Contract goal", "target_amount": 500.0},
        "expect": (200, 201),
    },
    ("GET", "/api/goals/"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/goals/{goal_id}"): {
        "path": lambda ctx: {"goal_id": ctx["goal_id"]},
    },
    ("PATCH", "/api/goals/{goal_id}"): {
        "path": lambda ctx: {"goal_id": ctx["goal_id"]},
        "json": {"description": "updated by contract suite"},
    },
    ("DELETE", "/api/goals/{goal_id}"): {"setup": _fresh_goal},
    ("POST", "/api/goals/{goal_id}/add_savings"): {
        "path": lambda ctx: {"goal_id": ctx["goal_id"]},
        "json": {"amount": 10.0},
    },
    ("POST", "/api/goals/{goal_id}/auto_transfer"): {
        "path": lambda ctx: {"goal_id": ctx["goal_id"]},
        "json": {"amount": 5.0},
        "expect": (200, 400),
    },
    ("POST", "/api/goals/{goal_id}/complete"): {"setup": _fresh_goal},
    ("POST", "/api/goals/{goal_id}/pause"): {"setup": _fresh_goal},
    ("POST", "/api/goals/{goal_id}/resume"): {
        "setup": lambda ctx, client: (
            lambda ids: (
                client.post(f"/api/goals/{ids['goal_id']}/pause"),
                ids,
            )[1]
        )(_fresh_goal(ctx, client)),
        "expect": (200, 400),
    },
    ("GET", "/api/goals/{goal_id}/health"): {
        "path": lambda ctx: {"goal_id": ctx["goal_id"]},
    },
    ("GET", "/api/goals/statistics"): {},
    ("GET", "/api/goals/adjustments/suggestions"): {},
    ("GET", "/api/goals/smart_recommendations"): {},
    ("GET", "/api/goals/income_based_suggestions"): {},
    ("GET", "/api/goals/opportunities/detect"): {},
    # ---- goals-budget integration (§2-D) ------------------------------------------
    ("GET", "/api/goals/budget/allocate"): {
        "query": dict(YM),
        "check": _check_goals_budget_allocate,
    },
    ("GET", "/api/goals/budget/progress"): {"query": dict(YM)},
    ("GET", "/api/goals/budget/adjustment_suggestions"): {},
    # ---- legacy goal progress router ------------------------------------------
    ("POST", "/api/goal/calendar-progress"): {
        "json": {
            "calendar": [
                {"savings": 15.0},
                {"savings": 25.0},
            ],
            "target": 400.0,
        },
        "check": lambda body, ctx: (
            # 40 saved of 400 target -> 10.0 percent
            _wrapped(body)["progress"] == pytest.approx(10.0)
            or pytest.fail(f"wrong progress: {body}")
        ),
    },
    ("POST", "/api/goal/state-progress"): {
        "json": {
            "income": 6000.0,
            "fixed_expenses": 1700.0,
            "goal": 400.0,
            "saved": 100.0,
        },
    },
    ("POST", "/api/goal/user-progress"): {
        "json": dict(YM),
    },
    # ---- challenges (TASK-15 contract) ---------------------------------------------
    ("POST", "/api/challenge/eligibility"): {
        "json": lambda ctx: {
            "user_id": str(ctx["user"].id),
            "current_month": TODAY.strftime("%Y-%m"),
        },
        "check": _check_challenge_eligibility,
    },
    ("POST", "/api/challenge/check"): {
        "json": {
            "calendar": _engine_calendar(),
            "today_date": TODAY.isoformat(),
            "challenge_log": {},
        },
        "check": _check_challenge_check,
    },
    ("POST", "/api/challenge/streak"): {
        "json": lambda ctx: {
            "calendar": _engine_calendar(),
            "user_id": str(ctx["user"].id),
            "log_data": {},
        },
        "check": _check_challenge_streak,
    },
    ("GET", "/api/challenge/available"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/challenge/active"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/challenge/stats"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/challenge/leaderboard"): {
        # Must be served by the leaderboard handler, not the /{challenge_id}
        # catch-all (route-ordering regression).
        "check": lambda body, ctx: (
            lambda d: d["top_users"] is not None and d["total_participants"] >= 0
        )(_wrapped(body)),
    },
    ("GET", "/api/challenge/{challenge_id}"): {
        "path": {"challenge_id": "nonexistent-challenge"},
        "expect": (200, 404),
    },
    ("GET", "/api/challenge/{challenge_id}/progress"): {
        "path": {"challenge_id": "nonexistent-challenge"},
        "check": lambda body, ctx: (lambda d: d["status"] == "not_started")(
            _wrapped(body)
        ),
    },
    ("POST", "/api/challenge/{challenge_id}/join"): {
        "path": {"challenge_id": "nonexistent-challenge"},
        "expect": (200, 404),
    },
    ("POST", "/api/challenge/{challenge_id}/leave"): {
        "path": {"challenge_id": "nonexistent-challenge"},
        "expect": (200, 404),
    },
    ("PATCH", "/api/challenge/{challenge_id}/progress"): {
        "path": {"challenge_id": "nonexistent-challenge"},
        "json": {"days_completed": 1},
        "expect": (200, 404),
    },
    # ---- cohort ------------------------------------------------------------------
    ("GET", "/api/cohort/income_classification"): {"check": _check_cohort_income},
    ("GET", "/api/cohort/insights"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("GET", "/api/cohort/peer_comparison"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    ("POST", "/api/cohort/assign"): {
        "json": {
            "profile": {
                "income": 6000.0,
                "region": "US",
                "behavior": "balanced",
                "categories": {"food": 500.0},
            }
        },
    },
    ("POST", "/api/cohort/drift"): {"json": {}, "expect": (200, 400, 422, 501)},
    # ---- behavior ------------------------------------------------------------------
    ("GET", "/api/behavior/analysis"): {},
    ("GET", "/api/behavior/anomalies"): {},
    ("GET", "/api/behavior/patterns"): {},
    ("GET", "/api/behavior/predictions"): {},
    ("GET", "/api/behavior/preferences"): {},
    ("PATCH", "/api/behavior/preferences"): {
        "json": {"notifications": True},
    },
    ("GET", "/api/behavior/notification_settings"): {},
    ("PATCH", "/api/behavior/notification_settings"): {
        "json": {"budget_alerts": True},
    },
    ("GET", "/api/behavior/progress"): {"query": {"months": 3}},
    ("GET", "/api/behavior/recommendations"): {},
    ("GET", "/api/behavior/triggers"): {},
    ("GET", "/api/behavior/warnings"): {},
    ("GET", "/api/behavior/cluster"): {},
    ("GET", "/api/behavior/category/{category}"): {
        "path": {"category": "food"},
    },
    # DEFERRED (TASK-15 policy): no implementation ever matched this contract.
    ("POST", "/api/behavior/calendar"): {
        "json": {
            **YM,
            "profile": {"income": 6000.0},
            "mood_log": {},
            "challenge_log": {},
            "calendar_log": {},
        },
        "expect": (501,),
    },
    ("POST", "/api/behavior/expense_suggestions"): {
        "json": {"category": "food"},
        "expect": (200, 400, 422),
    },
    # ---- habits ---------------------------------------------------------------------
    ("POST", "/api/habits/"): {
        "json": {"title": "Contract habit"},
        "expect": (200, 201),
    },
    ("GET", "/api/habits/"): {},
    ("PATCH", "/api/habits/{habit_id}"): {
        "path": lambda ctx: {"habit_id": ctx["habit_id"]},
        "json": {"title": "Renamed habit"},
    },
    ("DELETE", "/api/habits/{habit_id}"): {"setup": _fresh_habit},
    ("POST", "/api/habits/{habit_id}/complete"): {
        "path": lambda ctx: {"habit_id": ctx["habit_id"]},
        "query": {"date": TODAY.isoformat()},
    },
    ("DELETE", "/api/habits/{habit_id}/complete"): {
        "path": lambda ctx: {"habit_id": ctx["habit_id"]},
        "json": {"date": TODAY.isoformat()},
        "expect": (200, 404),
    },
    ("GET", "/api/habits/{habit_id}/progress"): {
        "path": lambda ctx: {"habit_id": ctx["habit_id"]},
        "query": {
            "start_date": (TODAY - timedelta(days=7)).isoformat(),
            "end_date": TODAY.isoformat(),
        },
    },
    # ---- mood ------------------------------------------------------------------------
    ("POST", "/api/mood/"): {
        "json": {"date": TODAY.isoformat(), "mood": "content"},
        "expect": (200, 201),
    },
    ("GET", "/api/mood/"): {},
    # ---- insights ---------------------------------------------------------------------
    ("GET", "/api/insights/"): {},
    ("GET", "/api/insights/history"): {},
    ("GET", "/api/insights/income_based_tips"): {},
    # ---- installments -----------------------------------------------------------------
    ("POST", "/api/installments/"): {
        "json": {
            "item_name": "Contract phone",
            "category": "electronics",
            "total_amount": "600.00",
            "payment_amount": "50.00",
            "total_payments": 12,
            "first_payment_date": (NOW + timedelta(days=3)).isoformat(),
            "next_payment_date": (NOW + timedelta(days=3)).isoformat(),
        },
        "expect": (200, 201),
    },
    ("GET", "/api/installments/"): {},
    ("GET", "/api/installments/{installment_id}"): {
        "path": lambda ctx: {"installment_id": ctx["installment_id"]},
    },
    ("PATCH", "/api/installments/{installment_id}"): {
        "path": lambda ctx: {"installment_id": ctx["installment_id"]},
        "json": {"notes": "updated by contract suite"},
    },
    ("DELETE", "/api/installments/{installment_id}"): {
        "setup": _fresh_installment,
        "expect": (200, 204),
    },
    ("GET", "/api/installments/achievements"): {},
    ("GET", "/api/installments/calendar/{year}/{month}"): {"path": dict(YM)},
    ("POST", "/api/installments/calculator"): {
        "json": {
            "purchase_amount": "600.00",
            "category": "electronics",
            "num_payments": 12,
            "monthly_income": "6000.00",
        },
    },
    ("GET", "/api/installments/profile"): {"expect": (200, 404)},
    ("POST", "/api/installments/profile"): {
        "json": {
            "monthly_income": "6000.00",
            "current_balance": "2000.00",
            "age_group": "25-34",
        },
        "expect": (200, 201, 422),
    },
    # ---- scheduled expenses -------------------------------------------------------------
    ("POST", "/api/scheduled-expenses/"): {
        "json": {
            "category": "subscriptions",
            "amount": "9.99",
            "scheduled_date": (TODAY + timedelta(days=14)).isoformat(),
        },
        "expect": (200, 201),
    },
    ("GET", "/api/scheduled-expenses/"): {},
    ("GET", "/api/scheduled-expenses/{expense_id}"): {
        "path": lambda ctx: {"expense_id": ctx["scheduled_expense_id"]},
    },
    ("DELETE", "/api/scheduled-expenses/{expense_id}"): {
        "setup": _fresh_scheduled_expense,
    },
    ("GET", "/api/scheduled-expenses/impact"): {},
    # ---- notifications --------------------------------------------------------------------
    ("POST", "/api/notifications/create"): {
        "json": {"title": "Contract", "message": "contract notification"},
        "expect": (200, 201),
    },
    ("GET", "/api/notifications/list"): {},
    ("GET", "/api/notifications/unread-count"): {},
    ("GET", "/api/notifications/preferences"): {},
    ("PUT", "/api/notifications/preferences"): {
        "json": {"push_enabled": True, "email_enabled": False},
    },
    ("POST", "/api/notifications/mark-all-read"): {},
    ("GET", "/api/notifications/{notification_id}"): {
        "path": lambda ctx: {"notification_id": ctx["notification_id"]},
    },
    ("POST", "/api/notifications/{notification_id}/mark-read"): {
        "path": lambda ctx: {"notification_id": ctx["notification_id"]},
    },
    ("DELETE", "/api/notifications/{notification_id}"): {
        "setup": _fresh_notification,
    },
    ("POST", "/api/notifications/register-token"): {
        "json": {"token": f"contract-fcm-{uuid4().hex[:12]}", "platform": "android"},
    },
    ("POST", "/api/notifications/register-device"): {
        "json": {
            "device_id": f"contract-{uuid4().hex[:8]}",
            "token": f"contract-fcm-{uuid4().hex[:12]}",
            "platform": "android",
        },
        "expect": (200, 201, 400, 422),
    },
    ("POST", "/api/notifications/update-device"): {
        "json": {
            "old_push_token": f"contract-old-{uuid4().hex[:12]}",
            "new_push_token": f"contract-new-{uuid4().hex[:12]}",
            "platform": "android",
        },
        "expect": (200, 201),
    },
    ("PATCH", "/api/notifications/update-device"): {
        "json": {
            "old_push_token": f"contract-old-{uuid4().hex[:12]}",
            "new_push_token": f"contract-new-{uuid4().hex[:12]}",
            "platform": "android",
        },
        "expect": (200, 201),
    },
    ("POST", "/api/notifications/unregister-device"): {
        "json": {"device_id": f"contract-{uuid4().hex[:8]}"},
        "expect": (200, 400, 404, 422),
    },
    ("DELETE", "/api/notifications/unregister-device"): {
        "json": {"device_id": f"contract-{uuid4().hex[:8]}"},
        "expect": (200, 400, 404, 422),
    },
    ("POST", "/api/notifications/test"): {
        "json": {"message": "contract test push"},
        "expect": (200, 400, 422, 503),
    },
    # ---- referral -----------------------------------------------------------------------
    ("GET", "/api/referral/code"): {},
    # DEFERRED (TASK-15 policy): users table has no referral schema.
    ("POST", "/api/referral/eligibility"): {"expect": (501,)},
    ("POST", "/api/referral/claim"): {"expect": (501,)},
    # ---- financial ----------------------------------------------------------------------
    ("GET", "/api/financial/dynamic-budget-method"): {},
    ("GET", "/api/financial/dynamic-thresholds/{threshold_type}"): {
        "path": {"threshold_type": "savings_rate"},
        "expect": (200, 400, 404, 422),
    },
    ("POST", "/api/financial/installment-evaluate"): {
        "json": {"price": "600.00", "months": 12},
    },
    # ---- expense (legacy router) ----------------------------------------------------------
    ("POST", "/api/expense/add"): {
        "json": lambda ctx: {
            "user_id": str(ctx["user"].id),
            "action": "food",
            "amount": 12.00,
            "date": TODAY.isoformat(),
        },
        "expect": (200, 201),
    },
    ("POST", "/api/expense/history"): {},
    # ---- checkpoint / spend / style / drift / cluster (engine utilities) -------------------
    # DEFERRED (TASK-15 policy): no backing implementation has ever matched
    # this contract — explicit 501 instead of a permanent 500.
    ("POST", "/api/checkpoint/today"): {
        "json": {
            "calendar": _engine_calendar(),
            "income": 6000.0,
            "day": TODAY.day,
        },
        "expect": (501,),
    },
    ("POST", "/api/spend/check"): {
        "json": {
            "calendar": _engine_calendar(),
            "day": TODAY.day,
            "category": "food",
        },
    },
    ("POST", "/api/spend/limit"): {
        "json": {
            "calendar": _engine_calendar(),
            "day": TODAY.day,
            "category": "food",
        },
    },
    ("POST", "/api/style/"): {
        "json": {"profile": {"cohort": "balanced", "income": 6000.0}},
    },
    ("POST", "/api/drift/log"): {
        "json": {"month": TODAY.strftime("%Y-%m"), "value": 0.15},
        "patches": [
            (
                "app.services.drift_service",
                "_get_db",
                lambda: (lambda: _FakeFirestore()),
            )
        ],
    },
    ("POST", "/api/drift/get"): {
        "json": {"month": TODAY.strftime("%Y-%m")},
        "patches": [
            (
                "app.services.drift_service",
                "_get_db",
                lambda: (lambda: _FakeFirestore()),
            )
        ],
        "expect": (200, 404),
    },
    # Cluster fit/centroids were never functional (the mounted request schema
    # does not match the in-memory KMeans engine input) — deprecated to 501
    # instead of shipping a permanent 500 (TASK-15 policy).
    ("POST", "/api/cluster/fit"): {
        "json": {"user_data": [{"income": 6000.0}]},
        "expect": (501,),
    },
    ("GET", "/api/cluster/centroids"): {"expect": (501,)},
    ("POST", "/api/cluster/label"): {
        "check": lambda body, ctx: _wrapped(body),
    },
    # ---- iap ---------------------------------------------------------------------------------
    ("GET", "/api/iap/status"): {},
    ("POST", "/api/iap/validate"): {
        # No store secrets in test env: the service returns status=invalid
        # without a network call — the route must stay non-5xx.
        "json": {"receipt": "contract-fake-receipt", "platform": "ios"},
        "expect": (200, 400, 422),
    },
    ("POST", "/api/iap/webhook"): {
        "json": {},
        "expect": (200, 202, 400, 401, 403, 422, 503),
    },
    # ---- ocr ----------------------------------------------------------------------------------
    ("POST", "/api/ocr/process"): {
        "files": _upload,
        "expect": (200, 201, 202, 400, 402, 422, 503),
    },
    ("POST", "/api/ocr/enhance"): {
        "files": _upload,
        "expect": (200, 201, 202, 400, 402, 422, 503),
    },
    ("POST", "/api/ocr/categorize"): {
        "json": {"merchant": "Test Store", "amount": 12.34},
        "expect": (200, 400, 422),
    },
    ("GET", "/api/ocr/status/{ocr_job_id}"): {
        "path": {"ocr_job_id": "nonexistent-job"},
        "expect": (200, 404),
    },
    ("GET", "/api/ocr/image/{job_id}"): {
        "path": {"job_id": "nonexistent-job"},
        "expect": (404,),
    },
    ("DELETE", "/api/ocr/image/{job_id}"): {
        "path": {"job_id": "nonexistent-job"},
        "expect": (200, 404),
    },
    # ---- tasks (RQ queue) -----------------------------------------------------------------------
    ("GET", "/api/tasks/{task_id}"): {
        "path": {"task_id": "nonexistent-task"},
        "expect": (200, 404, 429),
    },
    ("DELETE", "/api/tasks/{task_id}"): {
        "path": {"task_id": "nonexistent-task"},
        "expect": (200, 400, 404, 429),
    },
    ("POST", "/api/tasks/{task_id}/retry"): {
        "path": {"task_id": "nonexistent-task"},
        "expect": (200, 400, 404, 429),
    },
    ("POST", "/api/tasks/notifications"): {
        "json": {"message": "contract queue test"},
        "expect": (200, 201, 202, 429, 503),
    },
    ("POST", "/api/tasks/data-export"): {
        "json": {},
        "expect": (200, 201, 202, 429, 503),
    },
    ("POST", "/api/tasks/ai-analysis"): {
        "json": dict(YM),
        "expect": (200, 201, 202, 429, 503),
    },
    ("POST", "/api/tasks/budget-redistribution"): {
        "json": dict(YM),
        "expect": (200, 201, 202, 429, 503),
    },
    ("GET", "/api/tasks/system/stats"): {
        "actor": "admin",
        "expect": (200, 403, 429, 503),
    },
    ("POST", "/api/tasks/admin/daily-advice"): {
        "actor": "admin",
        # 429: strict admin-batch RateLimiter window — limiter answering is
        # contract-valid.
        "expect": (200, 201, 202, 403, 429, 503),
    },
    ("POST", "/api/tasks/admin/monthly-redistribution"): {
        "actor": "admin",
        # 429: shares a strict RateLimiter window with the user-facing
        # redistribution route — the limiter answering is contract-valid.
        "expect": (200, 201, 202, 403, 429, 503),
    },
    ("POST", "/api/tasks/admin/cleanup"): {
        "actor": "admin",
        "query": {"max_age_hours": 24},
        "expect": (200, 201, 202, 403, 429, 503),
    },
    # ---- email -----------------------------------------------------------------------------------
    ("GET", "/api/email/health"): {"expect": (200, 503)},
    ("GET", "/api/email/templates"): {},
    ("GET", "/api/email/queue/status"): {"expect": (200, 503)},
    ("GET", "/api/email/queue/job/{job_id}"): {
        "path": {"job_id": "nonexistent-job"},
        "expect": (200, 404),
    },
    ("POST", "/api/email/queue"): {
        "json": lambda ctx: {
            "to_email": ctx["user"].email,
            "email_type": "welcome",
            "variables": {"name": "Contract"},
        },
        "expect": (200, 201, 202, 400, 422, 503),
    },
    ("POST", "/api/email/send"): {
        # Admin-only route; the admin 200 path needs live SMTP (owner
        # DEF-005) — the enforced contract for a normal user is 403.
        "json": lambda ctx: {
            "to_email": ctx["user"].email,
            "email_type": "welcome",
            "variables": {"name": "Contract"},
        },
        "expect": (403,),
    },
    ("POST", "/api/email/test/template"): {
        "query": {"email_type": "welcome"},
        "json": {"name": "Contract"},
        "expect": (200, 400, 422, 503),
    },
    ("POST", "/api/email/admin/queue/start"): {
        "actor": "admin",
        "expect": (200, 202, 403, 503),
    },
    ("POST", "/api/email/admin/queue/stop"): {
        "actor": "admin",
        "expect": (200, 202, 403, 503),
    },
    # ---- audit / database / cache (admin observability) --------------------------------------------
    ("GET", "/api/audit/event-types"): {"actor": "admin", "expect": (200, 403)},
    ("POST", "/api/audit/flush"): {"actor": "admin", "expect": (200, 403)},
    ("GET", "/api/audit/health"): {"actor": "admin", "expect": (200, 403, 503)},
    ("GET", "/api/audit/performance-metrics"): {
        "actor": "admin",
        "query": {"hours": 1},
        "expect": (200, 403),
    },
    ("GET", "/api/audit/report"): {
        "actor": "admin",
        "query": {
            "start_date": (NOW - timedelta(days=1)).isoformat(),
            "end_date": NOW.isoformat(),
        },
        "expect": (200, 403, 404),
    },
    ("GET", "/api/audit/security-summary"): {
        "actor": "admin",
        "query": {"hours": 1},
        "expect": (200, 403),
    },
    ("GET", "/api/audit/user-activity/{user_id}"): {
        "actor": "admin",
        "path": lambda ctx: {"user_id": str(ctx["user"].id)},
        "query": {"days": 1},
        "expect": (200, 403),
    },
    ("GET", "/api/database/health"): {"actor": "admin", "expect": (200, 403, 503)},
    ("GET", "/api/database/connections"): {
        "actor": "admin",
        "expect": (200, 403, 404),  # 404 when pool metrics are not collected
    },
    ("GET", "/api/database/performance"): {"actor": "admin", "expect": (200, 403)},
    ("GET", "/api/database/optimization-report"): {
        "actor": "admin",
        "query": {"days": 1},
        "expect": (200, 403),
    },
    ("POST", "/api/database/optimize/queries"): {
        "actor": "admin",
        "query": {"auto_apply": "false"},
        "expect": (200, 403),
    },
    ("GET", "/api/database/queries/slow"): {
        "actor": "admin",
        "query": {"limit": 5},
        "expect": (200, 403),
    },
    ("GET", "/api/cache/health"): {"actor": "admin", "expect": (200, 403, 503)},
    ("GET", "/api/cache/statistics"): {"actor": "admin", "expect": (200, 403)},
    ("GET", "/api/cache/performance"): {"actor": "admin", "expect": (200, 403)},
    ("GET", "/api/cache/optimization-report"): {
        "actor": "admin",
        "expect": (200, 403),
    },
    ("GET", "/api/cache/top-keys"): {
        "actor": "admin",
        "query": {"limit": 5},
        "expect": (200, 403),
    },
    ("POST", "/api/cache/invalidate"): {
        "actor": "admin",
        "json": {"keys": ["contract-test-key"]},
        "expect": (200, 403),
    },
    ("POST", "/api/cache/clear"): {
        "actor": "admin",
        "query": {"confirm": "false"},
        "expect": (200, 400, 403, 422),
    },
    ("POST", "/api/cache/warm-up"): {"actor": "admin", "expect": (200, 403)},
    # ---- feature flags -----------------------------------------------------------------------------
    ("GET", "/api/feature-flags"): {"actor": "admin"},
    ("GET", "/api/feature-flags/{flag_key}"): {
        "actor": "admin",
        "path": {"flag_key": "admin_endpoints_enabled"},
        "expect": (200, 404),
    },
    ("GET", "/api/feature-flags/{flag_key}/check"): {
        "actor": "admin",
        "path": {"flag_key": "admin_endpoints_enabled"},
        "expect": (200, 404),
    },
    ("POST", "/api/feature-flags/{flag_key}/set"): {
        "actor": "admin",
        "path": {"flag_key": "contract_test_flag"},
        "json": {"value": True},
        "expect": (200, 201, 403, 404),
    },
}

# Routes that cannot be meaningfully exercised in-process. Each needs a reason.
EXCLUDED = {}


# ---------------------------------------------------------------------------
# Completeness gate
# ---------------------------------------------------------------------------


class TestRouteCoverage:
    def test_every_mounted_route_is_covered(self):
        missing = [r for r in MOUNTED if r not in SPECS and r not in EXCLUDED]
        assert not missing, (
            f"{len(missing)} mounted route(s) have no contract spec — add a "
            f"spec (or a documented exclusion) for: "
            + ", ".join(f"{m} {p}" for m, p in missing)
        )

    def test_no_stale_specs(self):
        stale = [r for r in list(SPECS) + list(EXCLUDED) if r not in MOUNTED]
        assert (
            not stale
        ), "spec entries for routes that are no longer mounted: " + ", ".join(
            f"{m} {p}" for m, p in stale
        )


# ---------------------------------------------------------------------------
# The parametrized contract
# ---------------------------------------------------------------------------


def _resolve(value, ctx):
    return value(ctx) if callable(value) else value


@pytest.mark.parametrize("method,path", MOUNTED, ids=[f"{m} {p}" for m, p in MOUNTED])
def test_route_contract(method, path, client, ctx, as_actor, monkeypatch):
    key = (method, path)
    if key in EXCLUDED:
        pytest.skip(EXCLUDED[key])
    spec = SPECS[key]

    ctx["actor"] = ctx["admin"] if spec.get("actor") == "admin" else ctx["user"]

    for module_path, attr, factory in spec.get("patches", []):
        import importlib

        module = importlib.import_module(module_path)
        monkeypatch.setattr(module, attr, factory())

    overrides = {}
    if spec.get("setup"):
        overrides = spec["setup"](ctx, client)

    path_params = dict(_resolve(spec.get("path"), ctx) or {})
    path_params.update(overrides)
    url = path
    for name, value in path_params.items():
        url = url.replace("{" + name + "}", str(value))
    assert "{" not in url, f"unresolved path params in {url}"

    kwargs = {}
    if spec.get("query") is not None:
        kwargs["params"] = _resolve(spec["query"], ctx)
    if spec.get("files") is not None:
        kwargs["files"] = spec["files"]()
        if spec.get("json") is not None:
            kwargs["data"] = _resolve(spec["json"], ctx)
    elif spec.get("json") is not None:
        kwargs["json"] = _resolve(spec["json"], ctx)

    resp = client.request(method, url, **kwargs)

    body_excerpt = resp.text[:500]
    expected = spec.get("expect", (200,))
    # 5xx is a contract violation with two explicit, spec-declared
    # exceptions: 501 for deprecated/deferred features (TASK-15 policy) and
    # 503 for an external dependency that is legitimately absent in the test
    # environment (e.g. the tesseract binary; installed in the prod image).
    assert resp.status_code < 500 or (
        resp.status_code in (501, 503) and resp.status_code in expected
    ), (
        f"{method} {url} returned {resp.status_code} (5xx breaks the route "
        f"contract): {body_excerpt}"
    )
    assert resp.status_code in expected, (
        f"{method} {url} returned {resp.status_code}, expected one of "
        f"{expected}: {body_excerpt}"
    )

    if spec.get("check") and resp.status_code == 200:
        spec["check"](resp.json(), ctx)


# ---------------------------------------------------------------------------
# Real-token auth journey (no dependency overrides): covers the token paths
# the overridden specs above cannot (validate/revoke against a real Bearer).
# ---------------------------------------------------------------------------


class TestRealAuthJourney:
    def test_register_login_validate_refresh_logout_delete(self, client, ctx):
        from app.api.dependencies import get_current_user
        from app.main import app

        email = f"contract_auth_{uuid4().hex[:10]}@mita.app"
        password = "Str0ng!passw0rd#2026"

        # The module installs a get_current_user override; this journey needs
        # the REAL dependency to exercise Bearer-token auth end to end.
        saved = app.dependency_overrides.pop(get_current_user, None)
        try:
            r = client.post(
                "/api/auth/register",
                json={"email": email, "password": password, "country": "US"},
            )
            assert r.status_code in (200, 201), r.text
            tokens = r.json()["data"]
            access, refresh = tokens["access_token"], tokens["refresh_token"]

            hdr = {"Authorization": f"Bearer {access}"}

            r = client.get("/api/auth/token/validate", headers=hdr)
            assert r.status_code == 200, r.text

            r = client.get("/api/users/me", headers=hdr)
            assert r.status_code == 200, r.text

            r = client.post("/api/auth/refresh-token", json={"refresh_token": refresh})
            assert r.status_code == 200, r.text
            rotated = r.json()["data"]
            access2 = rotated["access_token"]
            refresh2 = rotated["refresh_token"]

            # Rotated-out refresh token must be rejected on reuse.
            r = client.post("/api/auth/refresh-token", json={"refresh_token": refresh})
            assert r.status_code in (400, 401, 403), r.text

            hdr2 = {"Authorization": f"Bearer {access2}"}
            r = client.post(
                "/api/auth/logout", json={"refresh_token": refresh2}, headers=hdr2
            )
            assert r.status_code == 200, r.text

            # Refresh token revoked by logout.
            r = client.post("/api/auth/refresh-token", json={"refresh_token": refresh2})
            assert r.status_code in (400, 401, 403), r.text
        finally:
            if saved is not None:
                app.dependency_overrides[get_current_user] = saved
