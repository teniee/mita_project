"""IAP webhook security tests.

The webhook previously trusted a client-supplied {user_id, expires_at}
payload — anyone could self-grant premium. The intended product behavior
(store-signed notifications only, fail closed without configuration,
idempotent replay handling, ownership through the store transaction key)
is what these tests pin down. The old test asserting the insecure
behavior was removed for that reason.

Apple notifications are exercised with a locally generated certificate
chain that carries Apple's marker OIDs and is pinned as the trusted root
via APPLE_ROOT_CA_PATH — the same code path used for real Apple roots.
"""

import base64
import json
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.iap.routes import router
from app.core.config import settings
from app.core.session import get_db
from app.db.models import IAPEvent, Subscription, User
from app.services.iap.apple_verifier import (
    APPLE_INTERMEDIATE_MARKER_OID,
    APPLE_LEAF_MARKER_OID,
)
from app.services.iap.entitlements import compute_is_premium

DATABASE_URL = "postgresql://test:test@localhost:5432/test_mita"
BUNDLE_ID = "com.mita.finance.test"


# ---------------------------------------------------------------------------
# Fake Apple signing chain (root -> intermediate -> leaf with marker OIDs)
# ---------------------------------------------------------------------------


def _make_cert(subject_name, issuer_name, public_key, signing_key, marker_oid=None):
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_name)])
        )
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)]))
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
    )
    if marker_oid is not None:
        builder = builder.add_extension(
            x509.UnrecognizedExtension(marker_oid, b"\x05\x00"), critical=False
        )
    return builder.sign(signing_key, hashes.SHA256())


class FakeAppleChain:
    def __init__(self):
        self.root_key = ec.generate_private_key(ec.SECP256R1())
        self.intermediate_key = ec.generate_private_key(ec.SECP256R1())
        self.leaf_key = ec.generate_private_key(ec.SECP256R1())

        self.root = _make_cert(
            "Fake Apple Root CA",
            "Fake Apple Root CA",
            self.root_key.public_key(),
            self.root_key,
        )
        self.intermediate = _make_cert(
            "Fake Apple WWDR CA",
            "Fake Apple Root CA",
            self.intermediate_key.public_key(),
            self.root_key,
            marker_oid=APPLE_INTERMEDIATE_MARKER_OID,
        )
        self.leaf = _make_cert(
            "Fake App Store Notifications",
            "Fake Apple WWDR CA",
            self.leaf_key.public_key(),
            self.intermediate_key,
            marker_oid=APPLE_LEAF_MARKER_OID,
        )

    def x5c(self):
        return [
            base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode()
            for c in (self.leaf, self.intermediate, self.root)
        ]

    def sign(self, payload: dict) -> str:
        return pyjwt.encode(
            payload,
            self.leaf_key,
            algorithm="ES256",
            headers={"x5c": self.x5c()},
        )

    def root_pem_path(self, tmp_path):
        path = tmp_path / "fake_apple_root.pem"
        path.write_bytes(self.root.public_bytes(serialization.Encoding.PEM))
        return str(path)


def _apple_notification_payload(
    *,
    chain,
    notification_type="DID_RENEW",
    subtype=None,
    original_transaction_id="orig-tx-1",
    bundle_id=BUNDLE_ID,
    environment="Production",
    expires_in_days=30,
    notification_uuid=None,
    revocation_date=None,
):
    expires_ms = int(
        (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).timestamp()
        * 1000
    )
    tx = {
        "originalTransactionId": original_transaction_id,
        "productId": "com.mita.premium.monthly",
        "bundleId": bundle_id,
        "expiresDate": expires_ms,
    }
    if revocation_date is not None:
        tx["revocationDate"] = revocation_date
    payload = {
        "notificationType": notification_type,
        "notificationUUID": notification_uuid or str(uuid_mod.uuid4()),
        "data": {
            "bundleId": bundle_id,
            "environment": environment,
            "signedTransactionInfo": chain.sign(tx),
        },
    }
    if subtype:
        payload["subtype"] = subtype
    return {"signedPayload": chain.sign(payload)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chain():
    return FakeAppleChain()


@pytest.fixture()
def db_session():
    engine = create_engine(DATABASE_URL)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    yield session
    session.rollback()
    # Clean up rows created by tests
    session.query(IAPEvent).delete()
    session.query(Subscription).filter(
        Subscription.original_transaction_id.isnot(None)
    ).delete()
    session.query(User).filter(User.email.like("iap_test_%@example.com")).delete()
    session.commit()
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def premium_user(db_session):
    user = User(
        email=f"iap_test_{uuid_mod.uuid4().hex[:10]}@example.com",
        password_hash="x",
        is_premium=True,
        premium_until=datetime.now(timezone.utc) + timedelta(days=5),
    )
    db_session.add(user)
    db_session.flush()
    sub = Subscription(
        user_id=user.id,
        platform="ios",
        plan="monthly",
        receipt={"raw": "fixture"},
        status="active",
        original_transaction_id="orig-tx-1",
        product_id="com.mita.premium.monthly",
        expires_at=datetime.now(timezone.utc) + timedelta(days=5),
    )
    db_session.add(sub)
    db_session.commit()
    return user, sub


@pytest.fixture()
def apple_configured(chain, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "APPLE_ROOT_CA_PATH", chain.root_pem_path(tmp_path))
    monkeypatch.setattr(settings, "APPLE_BUNDLE_ID", BUNDLE_ID)
    return chain


# ---------------------------------------------------------------------------
# Legacy payload / fail-closed behavior
# ---------------------------------------------------------------------------


def test_legacy_payload_rejected_and_grants_nothing(client, db_session):
    user = User(
        email=f"iap_test_{uuid_mod.uuid4().hex[:10]}@example.com",
        password_hash="x",
        is_premium=False,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post(
        "/api/iap/webhook",
        json={"user_id": str(user.id), "expires_at": "2030-01-01T00:00:00"},
    )

    assert resp.status_code == 400
    db_session.refresh(user)
    assert user.is_premium is False
    assert user.premium_until is None


def test_apple_webhook_fails_closed_when_unconfigured(
    client, db_session, chain, monkeypatch, premium_user
):
    monkeypatch.setattr(settings, "APPLE_ROOT_CA_PATH", "")
    monkeypatch.setattr(settings, "APPLE_BUNDLE_ID", "")
    body = _apple_notification_payload(chain=chain, notification_type="REVOKE")

    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 503
    # No entitlement change happened
    user, sub = premium_user
    db_session.refresh(sub)
    assert sub.status == "active"


# ---------------------------------------------------------------------------
# Apple path
# ---------------------------------------------------------------------------


def test_apple_renewal_extends_entitlement(
    client, db_session, apple_configured, premium_user
):
    user, sub = premium_user
    body = _apple_notification_payload(chain=apple_configured, expires_in_days=40)

    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 200
    assert resp.json()["data"]["result"] == "processed"
    db_session.refresh(sub)
    db_session.refresh(user)
    assert sub.status == "active"
    assert sub.expires_at > datetime.now(timezone.utc) + timedelta(days=35)
    assert user.is_premium is True


def test_apple_tampered_signature_rejected(
    client, db_session, apple_configured, premium_user
):
    body = _apple_notification_payload(chain=apple_configured)
    # Flip payload content without re-signing
    header, payload, sig = body["signedPayload"].split(".")
    tampered = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    tampered["notificationType"] = "REVOKE"
    payload = (
        base64.urlsafe_b64encode(json.dumps(tampered).encode()).decode().rstrip("=")
    )
    body["signedPayload"] = f"{header}.{payload}.{sig}"

    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 401


def test_apple_unpinned_chain_rejected(client, db_session, tmp_path, monkeypatch):
    """A chain not rooted in the pinned CA must be rejected."""
    pinned = FakeAppleChain()
    attacker = FakeAppleChain()
    monkeypatch.setattr(settings, "APPLE_ROOT_CA_PATH", pinned.root_pem_path(tmp_path))
    monkeypatch.setattr(settings, "APPLE_BUNDLE_ID", BUNDLE_ID)

    body = _apple_notification_payload(chain=attacker)
    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 401


def test_apple_wrong_bundle_rejected(client, db_session, apple_configured):
    body = _apple_notification_payload(
        chain=apple_configured, bundle_id="com.attacker.app"
    )
    resp = client.post("/api/iap/webhook", json=body)
    assert resp.status_code == 401


def test_apple_sandbox_rejected_in_production_mode(
    client, db_session, apple_configured, monkeypatch
):
    monkeypatch.setattr(settings, "IAP_ALLOW_SANDBOX", False)
    body = _apple_notification_payload(chain=apple_configured, environment="Sandbox")
    resp = client.post("/api/iap/webhook", json=body)
    assert resp.status_code == 401


def test_apple_replay_is_idempotent(client, db_session, apple_configured, premium_user):
    nuid = str(uuid_mod.uuid4())
    body = _apple_notification_payload(
        chain=apple_configured, notification_uuid=nuid, expires_in_days=40
    )

    first = client.post("/api/iap/webhook", json=body)
    second = client.post("/api/iap/webhook", json=body)

    assert first.json()["data"]["result"] == "processed"
    assert second.json()["data"]["result"] == "duplicate"
    events = db_session.query(IAPEvent).filter(IAPEvent.event_id == nuid).all()
    assert len(events) == 1


def test_apple_unknown_transaction_grants_nothing(client, db_session, apple_configured):
    body = _apple_notification_payload(
        chain=apple_configured, original_transaction_id="never-seen-tx"
    )
    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 200
    assert resp.json()["data"]["result"] == "unmatched"
    subs = (
        db_session.query(Subscription)
        .filter(Subscription.original_transaction_id == "never-seen-tx")
        .count()
    )
    assert subs == 0


def test_apple_refund_revokes_premium(
    client, db_session, apple_configured, premium_user
):
    user, sub = premium_user
    body = _apple_notification_payload(
        chain=apple_configured,
        notification_type="REFUND",
        revocation_date=int(datetime.now(timezone.utc).timestamp() * 1000),
    )

    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 200
    db_session.refresh(sub)
    db_session.refresh(user)
    assert sub.status == "refunded"
    assert user.is_premium is False


def test_apple_grace_period_keeps_premium(
    client, db_session, apple_configured, premium_user
):
    user, sub = premium_user
    body = _apple_notification_payload(
        chain=apple_configured,
        notification_type="DID_FAIL_TO_RENEW",
        subtype="GRACE_PERIOD",
        expires_in_days=10,
    )

    resp = client.post("/api/iap/webhook", json=body)

    assert resp.status_code == 200
    db_session.refresh(sub)
    db_session.refresh(user)
    assert sub.status == "grace"
    assert user.is_premium is True


# ---------------------------------------------------------------------------
# Google path
# ---------------------------------------------------------------------------


def _google_envelope(
    *,
    notification_type=2,
    purchase_token="play-token-1",
    subscription_id="com.mita.premium.monthly",
    package_name="com.mita.finance.test",
    message_id=None,
):
    data = {
        "version": "1.0",
        "packageName": package_name,
        "eventTimeMillis": int(datetime.now(timezone.utc).timestamp() * 1000),
        "subscriptionNotification": {
            "version": "1.0",
            "notificationType": notification_type,
            "purchaseToken": purchase_token,
            "subscriptionId": subscription_id,
        },
    }
    return {
        "message": {
            "messageId": message_id or uuid_mod.uuid4().hex,
            "data": base64.b64encode(json.dumps(data).encode()).decode(),
        },
        "subscription": "projects/test/subscriptions/rtdn",
    }


@pytest.fixture()
def google_configured(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PACKAGE_NAME", "com.mita.finance.test")
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_AUDIENCE", "https://api.test/iap")
    monkeypatch.setattr(
        settings,
        "GOOGLE_PUBSUB_SERVICE_ACCOUNT",
        "rtdn@test.iam.gserviceaccount.com",
    )

    # Accept only the fixture bearer token, mimicking Google's OIDC check.
    def fake_oidc(token, audience):
        if token != "valid-oidc-token":
            from app.services.iap.errors import IAPVerificationError

            raise IAPVerificationError("bad token")
        return {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "email": "rtdn@test.iam.gserviceaccount.com",
            "email_verified": True,
        }

    monkeypatch.setattr(
        "app.services.iap.google_verifier._default_oidc_verifier", fake_oidc
    )

    expiry_ms = int(
        (datetime.now(timezone.utc) + timedelta(days=25)).timestamp() * 1000
    )

    class FakePlayClient:
        def __init__(self, _path):
            pass

        def get_subscription(self, package_name, subscription_id, token):
            return {"expiryTimeMillis": str(expiry_ms), "paymentState": 1}

    monkeypatch.setattr("app.api.iap.routes.GooglePlayClient", FakePlayClient)
    return expiry_ms


@pytest.fixture()
def android_premium_user(db_session):
    user = User(
        email=f"iap_test_{uuid_mod.uuid4().hex[:10]}@example.com",
        password_hash="x",
        is_premium=True,
        premium_until=datetime.now(timezone.utc) + timedelta(days=5),
    )
    db_session.add(user)
    db_session.flush()
    sub = Subscription(
        user_id=user.id,
        platform="android",
        plan="monthly",
        receipt={"raw": "fixture"},
        status="active",
        original_transaction_id="play-token-1",
        product_id="com.mita.premium.monthly",
        expires_at=datetime.now(timezone.utc) + timedelta(days=5),
    )
    db_session.add(sub)
    db_session.commit()
    return user, sub


def test_google_missing_bearer_rejected(client, db_session, google_configured):
    resp = client.post("/api/iap/webhook", json=_google_envelope())
    assert resp.status_code == 401


def test_google_bad_token_rejected(client, db_session, google_configured):
    resp = client.post(
        "/api/iap/webhook",
        json=_google_envelope(),
        headers={"Authorization": "Bearer forged-token"},
    )
    assert resp.status_code == 401


def test_google_unconfigured_fails_closed(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_AUDIENCE", "")
    monkeypatch.setattr(settings, "GOOGLE_PUBSUB_SERVICE_ACCOUNT", "")
    resp = client.post(
        "/api/iap/webhook",
        json=_google_envelope(),
        headers={"Authorization": "Bearer anything"},
    )
    assert resp.status_code == 503


def test_google_renewal_updates_entitlement(
    client, db_session, google_configured, android_premium_user
):
    user, sub = android_premium_user
    resp = client.post(
        "/api/iap/webhook",
        json=_google_envelope(notification_type=2),
        headers={"Authorization": "Bearer valid-oidc-token"},
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["result"] == "processed"
    db_session.refresh(sub)
    db_session.refresh(user)
    assert sub.status == "active"
    assert sub.expires_at > datetime.now(timezone.utc) + timedelta(days=20)
    assert user.is_premium is True


def test_google_revoke_kills_premium(
    client, db_session, google_configured, android_premium_user
):
    user, sub = android_premium_user
    resp = client.post(
        "/api/iap/webhook",
        json=_google_envelope(notification_type=12),
        headers={"Authorization": "Bearer valid-oidc-token"},
    )

    assert resp.status_code == 200
    db_session.refresh(sub)
    db_session.refresh(user)
    assert sub.status == "revoked"
    assert user.is_premium is False


def test_google_replay_is_idempotent(
    client, db_session, google_configured, android_premium_user
):
    envelope = _google_envelope(message_id="fixed-message-id")
    headers = {"Authorization": "Bearer valid-oidc-token"}

    first = client.post("/api/iap/webhook", json=envelope, headers=headers)
    second = client.post("/api/iap/webhook", json=envelope, headers=headers)

    assert first.json()["data"]["result"] == "processed"
    assert second.json()["data"]["result"] == "duplicate"


def test_google_unknown_purchase_grants_nothing(client, db_session, google_configured):
    resp = client.post(
        "/api/iap/webhook",
        json=_google_envelope(purchase_token="never-seen-token"),
        headers={"Authorization": "Bearer valid-oidc-token"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["result"] == "unmatched"


# ---------------------------------------------------------------------------
# Entitlement state machine
# ---------------------------------------------------------------------------


def test_compute_is_premium_matrix():
    future = datetime.now(timezone.utc) + timedelta(days=1)
    past = datetime.now(timezone.utc) - timedelta(days=1)

    assert compute_is_premium("active", future) is True
    assert compute_is_premium("grace", future) is True
    # canceled = auto-renew off; entitlement survives until expiry
    assert compute_is_premium("canceled", future) is True
    assert compute_is_premium("canceled", past) is False
    assert compute_is_premium("active", past) is False
    assert compute_is_premium("revoked", future) is False
    assert compute_is_premium("refunded", future) is False
    assert compute_is_premium("expired", future) is False
    assert compute_is_premium("on_hold", future) is False
    assert compute_is_premium("billing_retry", future) is False
    assert compute_is_premium("active", None) is False
