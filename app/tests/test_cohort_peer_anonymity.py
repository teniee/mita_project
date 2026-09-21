"""Regression: /cohort/peer_comparison must not disclose a member's spending.

History, all reproduced against the real route:

* Before #282 the cohort was every user within ±20% of the caller's own
  (writable) income and statistics were published from ONE peer: victim
  income 7777, expenses 111.11 + 222.22 -> ``peer_average = peer_median =
  333.33``. Sweeping the caller's income and reading ``peer_count`` pinned
  another user's income (probes 25252/25253/37878/37879 -> 0/1/1/0).
* The first #282 revision (fixed tiers, k = 10, count rounded down to a
  multiple of 10) still leaked: ranking the caller's spending against the raw
  totals made ``percentile`` a search probe that walked every member's exact
  total out; ``comparison``/``savings_potential`` against the raw median gave
  the median exactly; the odd-n median was one member's exact total; and the
  rounded count moved at 19 -> 20, so ``20·avg' − 19·avg`` was the joiner's
  exact spending.

The contract pinned here (see ``_peer_comparison_payload``):

* nothing is published below 10 CONTRIBUTING peers;
* the only peer statistic is ``peer_median`` = median_low of the contributors,
  rounded half-up to $100 — never the mean of two, never unrounded;
* ``peer_average`` and ``percentile`` are always null;
* ``comparison`` and ``savings_potential`` derive from the published median
  and the caller's own spending only;
* ``peer_count`` is the constant 10 ("at least 10") whenever anything is
  published, and 0 when suppressed;
* the cohort is the caller's fixed income tier — (0, 3000], (3000, 4800],
  (4800, 7200], (7200, 12000], (12000, ∞) per month — with an income of 0,
  negative or NULL in no tier.

Every expected value below is written out by hand, not recomputed with the
production helpers, so a broken helper cannot agree with itself.

The database tests run inside one outer transaction that is rolled back, and
first set every pre-existing user's income to 0 inside it. Other suites seed
users in every tier of the shared test database; hiding them is what lets
these tests assert EXACT cohorts (0, 1, 9, 10 ... contributors) against the
shipped threshold instead of the threshold relative to whatever happens to be
there. Nothing here is committed.

Requires: PostgreSQL at DATABASE_URL with migrations at head.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.cohort import routes as cohort_routes
from app.db.models import Transaction, User

payload = cohort_routes._peer_comparison_payload

# 20 contributor totals, deliberately unsorted and off the $100 grid. The
# cohort of size n is the first n of them.
#
#   n  sorted central value(s)      median_low   published
#   10 1240.00 | 1270.00            1240.00      1200.0  (mean-of-two 1255 -> 1300)
#   11 1261.17                      1261.17      1300.0
#   19 1240.00                      1240.00      1200.0
#   20 1240.00 | 1255.55            1240.00      1200.0
TOTALS = [
    "1270.00", "310.45", "88.10", "2999.99", "1240.00",
    "760.30", "1905.00", "45.00", "4100.75", "1333.33",
    "1261.17",
    "15.00", "2210.40", "3890.00", "640.00",
    "1199.99", "999.50", "5210.00", "150.25",
    "1255.55",
]  # fmt: skip
PUBLISHED_MEDIAN = {10: 1200.0, 11: 1300.0, 19: 1200.0, 20: 1200.0}

SUPPRESSED_SIZES = (0, 1, 9)
DISCLOSED_SIZES = (10, 11, 19, 20)

CONTRACT_KEYS = {
    "your_spending",
    "peer_average",
    "peer_median",
    "percentile",
    "comparison",
    "savings_potential",
    "peer_count",
    "income_bracket",
    "analysis_period_days",
    "note",
}


def _totals(n):
    return [Decimal(v) for v in TOTALS[:n]]


def _expected_verdict(spending, median):
    """The comparison rule, restated independently of the route."""
    if spending < median * 0.9:
        return "well_below_average"
    if spending < median:
        return "below_average"
    if spending <= median * 1.1:
        return "average"
    if spending <= median * 1.3:
        return "above_average"
    return "well_above_average"


def _numbers_in(data):
    return [v for v in data.values() if isinstance(v, (int, float))]


# ---------------------------------------------------------------------------
# 1. Cohort size and the published values (pure contract, exact inputs)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", SUPPRESSED_SIZES)
def test_fewer_than_ten_contributors_publish_nothing(n):
    assert payload(500.0, _totals(n), "tier") is None


@pytest.mark.parametrize("n", DISCLOSED_SIZES)
def test_ten_or_more_contributors_publish_exactly_the_contract(n):
    data = payload(1500.0, _totals(n), "tier")

    assert set(data) == CONTRACT_KEYS
    assert data["peer_median"] == PUBLISHED_MEDIAN[n]
    assert data["peer_average"] is None
    assert data["percentile"] is None
    assert data["peer_count"] == 10
    assert data["your_spending"] == 1500.0
    assert data["income_bracket"] == "tier"
    assert data["analysis_period_days"] == 30


def test_the_first_disclosure_is_at_exactly_ten():
    """Pins k from both sides without reading the constant."""
    assert payload(0.0, _totals(9), "t") is None
    assert payload(0.0, _totals(10), "t") is not None


# ---------------------------------------------------------------------------
# 2. Median: never a member's exact total, never interpolated
# ---------------------------------------------------------------------------
def test_odd_count_median_is_not_the_members_exact_total():
    # 11 contributors: the central member spent exactly 1261.17.
    data = payload(0.0, _totals(11), "t")
    assert data["peer_median"] == 1300.0
    assert "1261.17" not in str(data)


def test_even_count_median_is_the_lower_central_member_rounded():
    # 10 contributors: central pair 1240.00 / 1270.00. The mean of the pair
    # (1255) would publish 1300; median_low publishes 1240 -> 1200. The mean of
    # the pair is linear in either member, which is what makes it solvable.
    assert payload(0.0, _totals(10), "t")["peer_median"] == 1200.0


def test_input_order_does_not_matter():
    shuffled = list(reversed(_totals(11)))
    assert payload(0.0, shuffled, "t") == payload(0.0, _totals(11), "t")


@pytest.mark.parametrize(
    "central,published",
    [
        ("1249.99", 1200.0),
        ("1250.00", 1300.0),  # half-up
        ("1250.01", 1300.0),
        ("49.99", 0.0),
        ("50.00", 100.0),
        ("12345.67", 12300.0),
    ],
)
def test_median_rounds_half_up_to_one_hundred_dollars(central, published):
    # 11 values; the 6th smallest is `central`.
    low = [Decimal("1")] * 5
    high = [Decimal("99999")] * 5
    data = payload(0.0, low + [Decimal(central)] + high, "t")
    assert data["peer_median"] == published


def test_published_median_is_always_on_the_grid():
    import random

    rng = random.Random(282)
    for _ in range(500):
        n = rng.randint(10, 40)
        totals = [Decimal(rng.randint(1, 900_000)) / 100 for _ in range(n)]
        median = payload(0.0, totals, "t")["peer_median"]
        assert median % 100 == 0, median
        off_grid = {t for t in totals if t % 100 != 0}
        assert Decimal(str(median)) not in off_grid


# ---------------------------------------------------------------------------
# 3. peer_count: no single-member transition is observable
# ---------------------------------------------------------------------------
def test_peer_count_is_constant_at_every_cohort_size():
    counts = {
        payload(0.0, [Decimal("500")] * n, "t")["peer_count"] for n in range(10, 61)
    }
    assert counts == {10}


@pytest.mark.parametrize("before", [10, 19])
def test_one_more_contributor_changes_nothing_when_it_does_not_move_the_median(
    before,
):
    # Every member between $1,150 and $1,199 rounds to $1,200, so a joiner far
    # above cannot move the published median; if anything in the response
    # changes, it is the joiner (or the count) leaking.
    cohort = [Decimal("1150.00") + i for i in range(before)]
    assert payload(900.0, cohort, "t") == payload(
        900.0, cohort + [Decimal("7777.77")], "t"
    )


# ---------------------------------------------------------------------------
# 4. The caller's own spending is not an oracle
# ---------------------------------------------------------------------------
def _sweep_points(*cohorts):
    """Every cent-neighbour of every member total, plus a dense ramp."""
    points = {Decimal(c) / 100 for c in range(0, 700_000, 37)}
    for cohort in cohorts:
        for t in cohort:
            points |= {t - Decimal("0.01"), t, t + Decimal("0.01")}
    return sorted(float(p) for p in points if p >= 0)


def test_sweeping_own_spending_reveals_nothing_beyond_the_published_median():
    """Two different cohorts, one published median -> identical answers.

    A (10 people, mean 1405.29) and B (17 people, mean 3228.62) share only their
    published median of $1,200. If any response field depended on the raw
    cohort — a rank, a comparison against the raw median, a savings figure
    against it, a count — some caller spending would tell them apart.
    """
    a = _totals(10)
    b = [Decimal(v) for v in ("1201.00", "1180.55", "1219.99", "4500.00",
                              "9000.10", "300.00", "8800.00", "1234.56",
                              "1150.00", "7000.00", "6000.00", "20.00",
                              "1210.10", "3000.00", "1170.20", "5500.00",
                              "2400.00")]  # fmt: skip
    assert payload(0.0, a, "t")["peer_median"] == 1200.0
    assert payload(0.0, b, "t")["peer_median"] == 1200.0

    for spending in _sweep_points(a, b):
        got_a = payload(spending, a, "t")
        got_b = payload(spending, b, "t")
        assert got_a == got_b, spending
        assert got_a["percentile"] is None
        assert got_a["comparison"] == _expected_verdict(spending, 1200.0), spending
        assert got_a["savings_potential"] == round(max(spending - 1200.0, 0.0), 2)


def test_comparison_flips_only_at_the_published_median_not_the_raw_one():
    # Raw odd-n median 1261.17, published 1300. Spending just under and just
    # over the RAW median must get the same verdict.
    cohort = _totals(11)
    just_under = payload(1261.16, cohort, "t")
    just_over = payload(1261.18, cohort, "t")
    assert just_under["comparison"] == just_over["comparison"] == "below_average"
    assert just_under["savings_potential"] == just_over["savings_potential"] == 0.0


# ---------------------------------------------------------------------------
# 5. Temporal differencing: one member joining or leaving
# ---------------------------------------------------------------------------
def test_a_joiner_amount_cannot_be_differenced_out():
    cohort = _totals(14)  # published median over 14
    before = payload(800.0, cohort, "t")

    after_a = payload(800.0, cohort + [Decimal("987.65")], "t")
    after_b = payload(800.0, cohort + [Decimal("12.34")], "t")

    # Two different joiners below the median produce the same public answer:
    # nothing published depends on the joiner's amount.
    assert after_a == after_b
    for data in (before, after_a):
        assert "987.65" not in str(data)
        assert data["peer_average"] is None
        assert data["peer_count"] == 10
    # And leaving undoes it exactly.
    assert payload(800.0, cohort, "t") == before


# ---------------------------------------------------------------------------
# Database fixtures: one rolled-back transaction, every pre-existing user
# hidden from all tiers inside it.
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def iso_db():
    from sqlalchemy.orm import Session as OrmSession

    import app.core.session as session_module

    gen = session_module.get_db()  # initialises the engine
    next(gen)
    connection = session_module.engine.connect()
    outer = connection.begin()
    db = OrmSession(bind=connection, join_transaction_mode="create_savepoint")
    # Income 0 is in no tier, so every user created by other suites drops
    # out of every cohort — for this transaction only.
    db.query(User).update({User.monthly_income: 0}, synchronize_session=False)
    db.flush()
    try:
        yield db
    finally:
        db.close()
        outer.rollback()
        connection.close()
        gen.close()


NOW = datetime.now(timezone.utc)


def _user(db, income, spends=(), *, days_ago=1, deleted=False):
    user = User(
        id=uuid4(),
        email=f"anon_{uuid4().hex[:12]}@mita.app",
        password_hash="x",
        has_onboarded=True,
        timezone="UTC",
        monthly_income=None if income is None else Decimal(str(income)),
    )
    db.add(user)
    db.flush()
    for amount in spends:
        db.add(
            Transaction(
                id=uuid4(),
                user_id=user.id,
                category="food",
                amount=Decimal(str(amount)),
                spent_at=NOW - timedelta(days=days_ago),
                deleted_at=NOW if deleted else None,
            )
        )
    db.flush()
    return user


def _get(client, db, subject):
    from app.api.dependencies import get_current_user
    from app.core.session import get_db
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: subject
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = client.get("/api/cohort/peer_comparison")
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def _peers_seen_by(db, caller):
    since = NOW - timedelta(days=30)
    return set(
        cohort_routes._peer_spending_by_user(
            db, caller.id, caller.monthly_income, since
        )
    )


def _assert_suppressed(data):
    assert data["comparison"] == "insufficient_peer_data"
    assert data["peer_average"] is None
    assert data["peer_median"] is None
    assert data["percentile"] is None
    assert data["peer_count"] == 0
    assert data["savings_potential"] == 0


# ---------------------------------------------------------------------------
# 6. Tier membership, asserted against a hand-written table
# ---------------------------------------------------------------------------
# (monthly income, tier index) — independent of the production ladder code.
TIER_OF = [
    ("0.01", 0), ("1500.00", 0), ("3000.00", 0),
    ("3000.01", 1), ("3900.00", 1), ("4800.00", 1),
    ("4800.01", 2), ("6000.00", 2), ("7200.00", 2),
    ("7200.01", 3), ("9000.00", 3), ("12000.00", 3),
    ("12000.01", 4), ("250000.00", 4),
]  # fmt: skip
IN_NO_TIER = ("0", "-100.00", None)


def test_every_boundary_income_belongs_to_exactly_one_tier(iso_db):
    peers = {income: _user(iso_db, income, ["10.00"]) for income, _ in TIER_OF}
    outsiders = [_user(iso_db, income, ["10.00"]) for income in IN_NO_TIER]

    for caller_income, tier in TIER_OF:
        caller = _user(iso_db, caller_income)  # contributes nothing itself
        expected = {peers[income].id for income, t in TIER_OF if t == tier}
        seen = _peers_seen_by(iso_db, caller)
        assert seen == expected, f"caller at {caller_income}"
        assert not seen & {u.id for u in outsiders}


@pytest.mark.parametrize("income", IN_NO_TIER)
def test_a_caller_with_no_income_is_in_no_cohort(client, iso_db, income):
    for _ in range(12):
        _user(iso_db, "0.01", ["10.00"])  # a full bottom tier
    caller = _user(iso_db, income, ["50.00"])
    assert _peers_seen_by(iso_db, caller) == set()
    data = _get(client, iso_db, caller)
    _assert_suppressed(data)
    assert data["note"] == "Set monthly income for peer comparison"


@pytest.mark.parametrize("income", ["NaN", "Infinity"])
def test_a_non_finite_income_is_no_income_not_a_500(client, iso_db, income):
    # PATCH /users/me can store either (JSON `NaN` parses; float allows it).
    for _ in range(12):
        _user(iso_db, "20000.00", ["10.00"])  # a full top tier
    caller = _user(iso_db, income, ["50.00"])
    assert _peers_seen_by(iso_db, caller) == set()
    _assert_suppressed(_get(client, iso_db, caller))


def test_only_contributors_are_counted_and_the_caller_is_never_one(iso_db):
    caller = _user(iso_db, "6000.00", ["400.00"])
    contributor = _user(iso_db, "6000.00", ["111.11", "222.22"], days_ago=29)
    _user(iso_db, "6000.00")  # member, no spending
    _user(iso_db, "6000.00", ["500.00"], deleted=True)
    _user(iso_db, "6000.00", ["500.00"], days_ago=31)

    since = NOW - timedelta(days=30)
    seen = cohort_routes._peer_spending_by_user(
        iso_db, caller.id, caller.monthly_income, since
    )
    assert seen == {contributor.id: Decimal("333.33")}


# ---------------------------------------------------------------------------
# 7. The real route, real threshold, exact cohorts
# ---------------------------------------------------------------------------
MIDDLE_INCOMES = ("4800.01", "5500.00", "6000.00", "7200.00")


@pytest.mark.parametrize("n", SUPPRESSED_SIZES + DISCLOSED_SIZES)
def test_route_publishes_from_the_tenth_contributor(client, iso_db, n):
    subject = _user(iso_db, "6000.00", ["1500.00"])
    for i, amount in enumerate(TOTALS[:n]):
        _user(iso_db, MIDDLE_INCOMES[i % 4], [amount])

    data = _get(client, iso_db, subject)
    if n < 10:
        _assert_suppressed(data)
        assert data["note"] == "Need more users in database for peer comparison"
        for amount in TOTALS[:n]:
            assert amount not in str(data)
        return

    median = PUBLISHED_MEDIAN[n]
    assert set(data) == CONTRACT_KEYS
    assert data["peer_median"] == median
    assert data["peer_average"] is None
    assert data["percentile"] is None
    assert data["peer_count"] == 10
    assert data["your_spending"] == 1500.0
    assert data["comparison"] == _expected_verdict(1500.0, median)
    assert data["savings_potential"] == 1500.0 - median
    assert data["income_bracket"] == "$4,800 - $7,200/month"
    for amount in TOTALS[:n]:
        assert float(amount) not in _numbers_in(data)


@pytest.mark.parametrize("contributors,published", [(1, False), (9, False), (10, True)])
def test_route_counts_contributors_not_tier_members(
    client, iso_db, contributors, published
):
    subject = _user(iso_db, "6000.00", ["1500.00"])
    for i in range(20):
        income = MIDDLE_INCOMES[i % 4]
        if i < contributors:
            _user(iso_db, income, [TOTALS[i]])
        elif i % 3 == 0:
            _user(iso_db, income)  # no spending at all
        elif i % 3 == 1:
            _user(iso_db, income, ["900.00"], deleted=True)
        else:
            _user(iso_db, income, ["900.00"], days_ago=45)

    data = _get(client, iso_db, subject)
    if published:
        assert data["peer_median"] == PUBLISHED_MEDIAN[10]
        assert data["peer_count"] == 10
    else:
        _assert_suppressed(data)


@pytest.mark.parametrize(
    "peer_income,caller_income,published",
    [
        ("7200.00", "7200.00", True),  # both at MIDDLE's top edge
        ("7200.00", "7200.01", False),  # caller one cent into UPPER_MIDDLE
        ("7200.01", "7200.00", False),
        ("7200.01", "7200.01", True),
        ("3000.00", "0.01", True),  # bottom tier is (0, 3000]
        ("0.00", "0.01", False),  # no income is not a bottom-tier peer
    ],
)
def test_route_tier_edges(client, iso_db, peer_income, caller_income, published):
    subject = _user(iso_db, caller_income, ["100.00"])
    for amount in TOTALS[:10]:
        _user(iso_db, peer_income, [amount])

    data = _get(client, iso_db, subject)
    if published:
        assert data["peer_median"] == 1200.0
    else:
        _assert_suppressed(data)


def test_probing_adjacent_tiers_by_editing_income(client, iso_db):
    """The caller CAN choose which fixed tier to look at; nothing finer.

    LOW has 10 contributors, LOWER_MIDDLE 9, MIDDLE 12, the top two none.
    Every probe inside a tier gets the identical answer, and a 9-contributor
    tier is indistinguishable from an empty one.
    """
    for amount in TOTALS[:10]:
        _user(iso_db, "2000.00", [amount])
    for amount in TOTALS[:9]:
        _user(iso_db, "4000.00", [amount])
    for amount in TOTALS[:12]:
        _user(iso_db, "6500.00", [amount])

    subject = _user(iso_db, "1.00", ["1500.00"])
    probes = {
        0: ("0.01", "1999.99", "2000.00", "2999.99", "3000.00"),
        1: ("3000.01", "3999.99", "4000.00", "4800.00"),
        2: ("4800.01", "6499.99", "6500.00", "7200.00"),
        3: ("7200.01", "11000.00", "12000.00"),
        4: ("12000.01", "40000.00", "999999.00"),
    }
    answers = {}
    for tier, incomes in probes.items():
        seen = set()
        for income in incomes:
            subject.monthly_income = Decimal(income)
            iso_db.flush()
            seen.add(tuple(sorted(_get(client, iso_db, subject).items())))
        assert len(seen) == 1, f"tier {tier} answered differently inside itself"
        answers[tier] = dict(seen.pop())

    assert answers[0]["peer_median"] == 1200.0
    assert answers[0]["income_bracket"] == "Up to $3,000/month"
    assert answers[2]["peer_median"] == 1200.0  # 12 contributors: 1240.00
    assert answers[2]["income_bracket"] == "$4,800 - $7,200/month"
    for tier in (1, 3, 4):
        _assert_suppressed(answers[tier])
    assert answers[1] == answers[3] == answers[4]


def test_one_contributor_joining_then_leaving_is_not_differencable(client, iso_db):
    subject = _user(iso_db, "6000.00", ["800.00"])
    for i, amount in enumerate(TOTALS[:14]):
        _user(iso_db, MIDDLE_INCOMES[i % 4], [amount])
    before = _get(client, iso_db, subject)

    joiner = _user(iso_db, "6000.00", ["987.65"])
    during = _get(client, iso_db, subject)

    iso_db.query(Transaction).filter_by(user_id=joiner.id).update(
        {Transaction.amount: Decimal("12.34")}
    )
    iso_db.flush()
    during_other_amount = _get(client, iso_db, subject)

    iso_db.query(Transaction).filter_by(user_id=joiner.id).update(
        {Transaction.deleted_at: NOW}
    )
    iso_db.flush()
    after = _get(client, iso_db, subject)

    assert during == during_other_amount, "the answer depends on the joiner's amount"
    assert after == before
    for data in (before, during, after):
        assert data["peer_count"] == 10
        assert data["peer_average"] is None
        assert 987.65 not in _numbers_in(data)


def test_own_spending_moves_only_own_fields(client, iso_db):
    subject = _user(iso_db, "6000.00")
    for i, amount in enumerate(TOTALS[:10]):
        _user(iso_db, MIDDLE_INCOMES[i % 4], [amount])

    peer_fields = ("peer_average", "peer_median", "percentile", "peer_count")
    seen_peer_fields = set()
    for amount in ("1079.99", "1080.01", "1199.99", "1240.00", "1240.01",
                   "1319.99", "1320.01", "1559.99", "1560.01"):  # fmt: skip
        iso_db.query(Transaction).filter_by(user_id=subject.id).delete()
        iso_db.add(
            Transaction(
                id=uuid4(),
                user_id=subject.id,
                category="food",
                amount=Decimal(amount),
                spent_at=NOW - timedelta(days=1),
            )
        )
        iso_db.flush()
        data = _get(client, iso_db, subject)
        spending = float(amount)
        seen_peer_fields.add(tuple(data[f] for f in peer_fields))
        assert data["comparison"] == _expected_verdict(spending, 1200.0), amount
        assert data["savings_potential"] == round(max(spending - 1200.0, 0.0), 2)

    assert seen_peer_fields == {(None, 1200.0, None, 10)}
