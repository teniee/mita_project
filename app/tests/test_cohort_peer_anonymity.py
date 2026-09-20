"""Regression: /cohort/peer_comparison must not publish a cohort of one.

The endpoint compared the caller against every user within ±20% of the
caller's own income and published the mean, median, percentile, comparison and
savings_potential as soon as ONE of them had spent anything. Two consequences,
both reproduced against the real route before this fix:

* A bracket holding a single peer published that person's exact 30-day
  spending as `peer_average` (and again as `peer_median`): victim income 7777,
  expenses 111.11 + 222.22 -> `peer_average = peer_median = 333.33`. With two
  peers both totals came back out of the mean and the median.
* `monthly_income` is writable (PATCH /api/users/me), so the bracket moved
  with the caller. Sweeping it and watching `peer_count` step by one located
  another user's income to within a rounding error (probe incomes
  25252/25253/37878/37879 -> counts 0/1/1/0, pinning 30303).

README.md calls this "anonymized peer comparison" and PRIVACY_POLICY.md says
peer data is "aggregated and anonymized", so publishing one identifiable
person's figures is a privacy defect, not a product decision.

What is enforced now:

* the cohort is the caller's income TIER (server-defined, disjoint), so the
  answer does not move when the caller edits their own income;
* no statistic is published unless at least ``MIN_PEER_COHORT`` peers actually
  contributed spending — below that the endpoint returns its existing honest
  ``insufficient_peer_data`` envelope;
* the published ``peer_count`` is rounded down to a multiple of the threshold,
  so it cannot be watched for single-member changes.

The threshold is monkeypatched relative to the cohort already present in the
database in most tests here: the suite shares one database with tests that
seed users across every income tier, so "a cohort of exactly one" cannot be
assumed. The rule — suppress below the threshold, publish at or above it — is
what these tests pin, plus one test that the shipped constant itself stays
sane.

Requires: PostgreSQL at DATABASE_URL with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.cohort import routes as cohort_routes
from app.db.models import Transaction, User

# Well inside the top tier, away from the boundary the other suites sit on.
SUBJECT_INCOME = Decimal("18000.00")


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
def made(db_session):
    """Users created by a test, removed afterwards."""
    created: list = []
    yield created
    for u in created:
        db_session.query(Transaction).filter_by(user_id=u.id).delete()
        db_session.query(User).filter_by(id=u.id).delete()
    db_session.commit()


def _make_user(db, made, income, spends=()):
    user = User(
        id=uuid4(),
        email=f"anon_{uuid4().hex[:12]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=Decimal(str(income)),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    made.append(user)
    when = datetime.now(timezone.utc) - timedelta(days=1)
    for amount in spends:
        db.add(
            Transaction(
                id=uuid4(),
                user_id=user.id,
                category="food",
                amount=Decimal(str(amount)),
                spent_at=when,
            )
        )
    db.commit()
    return user


def _contributor_totals(db, subject):
    """The peer sums the endpoint would average, computed independently.

    Uses the endpoint's own tier helper so the two cannot drift apart.
    """
    from sqlalchemy import func

    lower, upper = cohort_routes._tier_income_bounds(float(subject.monthly_income))
    filters = [User.id != subject.id, User.monthly_income > lower]
    if upper is not None:
        filters.append(User.monthly_income <= upper)
    peer_ids = [row.id for row in db.query(User.id).filter(*filters).all()]
    if not peer_ids:
        return []
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(func.sum(Transaction.amount))
        .filter(
            Transaction.user_id.in_(peer_ids),
            Transaction.deleted_at.is_(None),
            Transaction.spent_at >= since,
        )
        .group_by(Transaction.user_id)
        .all()
    )
    return [float(r[0]) for r in rows if r[0] is not None]


def _get(client, subject):
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: subject
    try:
        resp = client.get("/api/cohort/peer_comparison")
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _assert_suppressed(data):
    assert data["comparison"] == "insufficient_peer_data"
    assert data["peer_average"] is None
    assert data["peer_median"] is None
    assert data["percentile"] is None
    assert data["peer_count"] == 0
    assert data["savings_potential"] == 0


def test_a_lone_peer_spend_is_never_published(client, db_session, made, monkeypatch):
    """The headline case: one more peer must not become the 'peer average'."""
    subject = _make_user(db_session, made, SUBJECT_INCOME)
    baseline = len(_contributor_totals(db_session, subject))
    # Threshold above whatever this database already holds, so the peer added
    # below is genuinely under it (and is the only one when the DB is clean).
    monkeypatch.setattr(cohort_routes, "MIN_PEER_COHORT", baseline + 2)

    secret = "333.33"
    _make_user(db_session, made, SUBJECT_INCOME, ["111.11", "222.22"])

    data = _get(client, subject)
    _assert_suppressed(data)
    assert secret not in str(data), "an individual peer's exact spend leaked"


def test_cohort_below_the_threshold_publishes_nothing(
    client, db_session, made, monkeypatch
):
    subject = _make_user(db_session, made, SUBJECT_INCOME)
    baseline = len(_contributor_totals(db_session, subject))
    monkeypatch.setattr(cohort_routes, "MIN_PEER_COHORT", baseline + 3)

    _make_user(db_session, made, SUBJECT_INCOME, ["120.00"])
    _make_user(db_session, made, SUBJECT_INCOME, ["480.00"])  # one short

    assert len(_contributor_totals(db_session, subject)) == baseline + 2
    _assert_suppressed(_get(client, subject))


def test_cohort_at_the_threshold_still_gets_a_real_comparison(
    client, db_session, made, monkeypatch
):
    subject = _make_user(db_session, made, SUBJECT_INCOME, ["200.00"])
    baseline = len(_contributor_totals(db_session, subject))
    threshold = baseline + 3
    monkeypatch.setattr(cohort_routes, "MIN_PEER_COHORT", threshold)

    for amount in ("100.00", "300.00", "500.00"):
        _make_user(db_session, made, SUBJECT_INCOME, [amount])

    totals = _contributor_totals(db_session, subject)
    assert len(totals) == threshold

    data = _get(client, subject)
    assert data["comparison"] != "insufficient_peer_data"
    assert data["peer_average"] == pytest.approx(sum(totals) / len(totals), abs=0.01)
    assert data["peer_median"] is not None
    assert data["percentile"] is not None
    assert data["your_spending"] == pytest.approx(200.00)


def test_published_peer_count_is_coarsened(client, db_session, made, monkeypatch):
    """An exact count lets a poller watch single members join or leave."""
    subject = _make_user(db_session, made, SUBJECT_INCOME, ["200.00"])
    baseline = len(_contributor_totals(db_session, subject))
    threshold = max(2, baseline + 1)
    monkeypatch.setattr(cohort_routes, "MIN_PEER_COHORT", threshold)

    # One more than a whole multiple of the threshold.
    for _ in range(threshold + 1 - baseline):
        _make_user(db_session, made, SUBJECT_INCOME, ["250.00"])

    exact = len(_contributor_totals(db_session, subject))
    data = _get(client, subject)
    assert data["comparison"] != "insufficient_peer_data"
    assert data["peer_count"] % threshold == 0, "count must be a multiple, not exact"
    assert data["peer_count"] <= exact
    assert data["peer_count"] != exact or exact % threshold == 0


def test_caller_cannot_move_the_cohort_by_editing_their_income(
    client, db_session, made, monkeypatch
):
    """The probing attack: sweeping your own income must change nothing.

    Before the fix the cohort was [0.8x, 1.2x] of the caller's own income, so
    each step of x added or dropped one peer and `peer_count` reported it.
    """
    subject = _make_user(db_session, made, SUBJECT_INCOME, ["200.00"])
    # Low threshold so statistics ARE published at every probe: this test is
    # about the cohort not moving, and a suppressed answer is trivially
    # constant. Peers sit at incomes spread across the top tier, so a window
    # centred on the caller would take a different subset at each probe.
    monkeypatch.setattr(cohort_routes, "MIN_PEER_COHORT", 2)
    for income, spend in (
        ("13500.00", "111.00"),
        ("21000.00", "777.77"),
        ("28000.00", "999.00"),
    ):
        _make_user(db_session, made, income, [spend])

    seen = set()
    # Every probe stays inside the same tier (> $12,000/month).
    for income in ("13000.00", "16000.00", "19000.00", "24000.00", "30000.00"):
        subject.monthly_income = Decimal(income)
        db_session.commit()
        data = _get(client, subject)
        assert data["comparison"] != "insufficient_peer_data", (
            "precondition: the cohort must publish for this test to be "
            "sensitive to the cohort moving"
        )
        seen.add(
            (
                data["comparison"],
                data["peer_average"],
                data["peer_median"],
                data["peer_count"],
            )
        )

    assert len(seen) == 1, f"response varied with the caller's own income: {seen}"


def test_shipped_threshold_matches_the_rule_it_documents(client, db_session, made):
    """Guards the real constant and the real code path (no monkeypatching)."""
    assert cohort_routes.MIN_PEER_COHORT >= 5, "k below 5 is not anonymity"

    subject = _make_user(db_session, made, SUBJECT_INCOME, ["200.00"])
    totals = _contributor_totals(db_session, subject)
    data = _get(client, subject)

    if len(totals) < cohort_routes.MIN_PEER_COHORT:
        _assert_suppressed(data)
    else:
        assert data["peer_average"] == pytest.approx(
            sum(totals) / len(totals), abs=0.01
        )
        assert data["peer_count"] % cohort_routes.MIN_PEER_COHORT == 0


def test_tier_bounds_partition_the_income_axis():
    """Disjoint tiers are what removes the caller-steerable window."""
    incomes = [500.0, 2999.0, 3000.0, 3001.0, 4800.0, 7200.0, 12000.0, 12001.0, 50000.0]
    for income in incomes:
        lower, upper = cohort_routes._tier_income_bounds(income)
        assert lower < income, f"{income} not above its lower bound"
        if upper is not None:
            assert income <= upper, f"{income} not within its upper bound"

    # Neighbouring incomes on either side of an edge land in different tiers,
    # and the bounds line up exactly (no gap, no overlap).
    below = cohort_routes._tier_income_bounds(4800.0)
    above = cohort_routes._tier_income_bounds(4800.01)
    assert below[1] == above[0] == 4800.0
