"""Verification of Apple App Store Server Notifications V2.

Apple delivers notifications as a JWS (`signedPayload`) whose header carries
an x5c certificate chain rooted in the Apple Root CA. Verification:

1. Parse the x5c chain (leaf, intermediate, root).
2. Check each certificate's validity window.
3. Check Apple marker OIDs (leaf: 1.2.840.113635.100.6.11.1,
   intermediate: 1.2.840.113635.100.6.2.1).
4. Verify leaf is signed by intermediate, intermediate by root.
5. Verify the root is one of the pinned trusted roots (Apple Root CA G3,
   provided via APPLE_ROOT_CA_PATH — Apple publishes it at
   https://www.apple.com/certificateauthority/AppleRootCA-G3.cer).
6. Verify the JWS signature (ES256) with the leaf public key.
7. Validate claims: bundleId and environment.

The nested `signedTransactionInfo` / `signedRenewalInfo` JWS payloads are
verified the same way.
"""

import base64
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import jwt as pyjwt
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import ObjectIdentifier

from app.services.iap.errors import IAPNotConfiguredError, IAPVerificationError

logger = logging.getLogger(__name__)

APPLE_LEAF_MARKER_OID = ObjectIdentifier("1.2.840.113635.100.6.11.1")
APPLE_INTERMEDIATE_MARKER_OID = ObjectIdentifier("1.2.840.113635.100.6.2.1")


@dataclass
class AppleNotification:
    """A fully verified App Store Server Notification V2."""

    notification_type: str
    subtype: Optional[str]
    notification_uuid: str
    bundle_id: Optional[str]
    environment: Optional[str]
    transaction_info: Dict = field(default_factory=dict)
    renewal_info: Dict = field(default_factory=dict)


def load_trusted_roots(pem_path: str) -> List[x509.Certificate]:
    """Load one or more trusted root certificates from a PEM bundle."""
    try:
        with open(pem_path, "rb") as fh:
            pem_data = fh.read()
    except OSError as exc:
        raise IAPNotConfiguredError(
            f"Apple root CA bundle not readable at {pem_path!r}"
        ) from exc
    roots = x509.load_pem_x509_certificates(pem_data)
    if not roots:
        raise IAPNotConfiguredError("Apple root CA bundle contains no certificates")
    return roots


def _b64url_decode(segment: str) -> bytes:
    padding_needed = -len(segment) % 4
    return base64.urlsafe_b64decode(segment + "=" * padding_needed)


def _parse_x5c_chain(signed_payload: str) -> List[x509.Certificate]:
    try:
        header_segment = signed_payload.split(".")[0]
        header = json.loads(_b64url_decode(header_segment))
    except Exception as exc:
        raise IAPVerificationError("Malformed JWS header") from exc

    x5c = header.get("x5c")
    if not isinstance(x5c, list) or len(x5c) != 3:
        raise IAPVerificationError("JWS header must carry a 3-certificate x5c chain")
    if header.get("alg") != "ES256":
        raise IAPVerificationError(f"Unexpected JWS alg: {header.get('alg')!r}")

    try:
        return [x509.load_der_x509_certificate(base64.b64decode(c)) for c in x5c]
    except Exception as exc:
        raise IAPVerificationError("x5c chain contains invalid certificates") from exc


def _has_marker_oid(cert: x509.Certificate, oid: ObjectIdentifier) -> bool:
    try:
        cert.extensions.get_extension_for_oid(oid)
        return True
    except x509.ExtensionNotFound:
        return False


def _verify_signed_by(child: x509.Certificate, parent: x509.Certificate) -> None:
    public_key = parent.public_key()
    try:
        if isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(
                child.signature,
                child.tbs_certificate_bytes,
                ec.ECDSA(child.signature_hash_algorithm),
            )
        elif isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                child.signature,
                child.tbs_certificate_bytes,
                padding.PKCS1v15(),
                child.signature_hash_algorithm,
            )
        else:
            raise IAPVerificationError("Unsupported issuer key type in x5c chain")
    except InvalidSignature as exc:
        raise IAPVerificationError("x5c chain signature verification failed") from exc


def _verify_chain(
    chain: List[x509.Certificate],
    trusted_roots: List[x509.Certificate],
    at_time: Optional[datetime] = None,
) -> x509.Certificate:
    leaf, intermediate, root = chain
    now = at_time or datetime.now(timezone.utc)

    for cert in chain:
        if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
            raise IAPVerificationError("Certificate in x5c chain is expired")

    if not _has_marker_oid(leaf, APPLE_LEAF_MARKER_OID):
        raise IAPVerificationError("Leaf certificate missing Apple marker OID")
    if not _has_marker_oid(intermediate, APPLE_INTERMEDIATE_MARKER_OID):
        raise IAPVerificationError("Intermediate certificate missing Apple marker OID")

    _verify_signed_by(leaf, intermediate)
    _verify_signed_by(intermediate, root)

    root_der = root.public_bytes(Encoding.DER)
    for trusted in trusted_roots:
        if trusted.public_bytes(Encoding.DER) == root_der:
            return leaf
    raise IAPVerificationError("x5c root certificate is not a pinned Apple root")


def verify_signed_payload(
    signed_payload: str,
    trusted_roots: List[x509.Certificate],
    at_time: Optional[datetime] = None,
) -> Dict:
    """Verify a JWS signed by Apple and return its decoded payload."""
    if not trusted_roots:
        raise IAPNotConfiguredError("No trusted Apple root certificates configured")

    chain = _parse_x5c_chain(signed_payload)
    leaf = _verify_chain(chain, trusted_roots, at_time=at_time)

    try:
        return pyjwt.decode(
            signed_payload,
            key=leaf.public_key(),
            algorithms=["ES256"],
            options={"verify_exp": False, "verify_aud": False},
        )
    except pyjwt.InvalidTokenError as exc:
        raise IAPVerificationError("JWS signature verification failed") from exc


def verify_apple_notification(
    signed_payload: str,
    *,
    trusted_roots: List[x509.Certificate],
    bundle_id: Optional[str] = None,
    allowed_environments: Optional[List[str]] = None,
    at_time: Optional[datetime] = None,
) -> AppleNotification:
    """Verify an App Store Server Notification V2 end to end."""
    payload = verify_signed_payload(signed_payload, trusted_roots, at_time=at_time)

    notification_uuid = payload.get("notificationUUID")
    notification_type = payload.get("notificationType")
    if not notification_uuid or not notification_type:
        raise IAPVerificationError("Notification missing type or UUID")

    data = payload.get("data") or {}
    payload_bundle = data.get("bundleId")
    if bundle_id and payload_bundle != bundle_id:
        raise IAPVerificationError("Notification bundleId does not match app")

    environment = data.get("environment")
    if allowed_environments and environment not in allowed_environments:
        raise IAPVerificationError(
            f"Notification environment {environment!r} not allowed"
        )

    transaction_info: Dict = {}
    signed_tx = data.get("signedTransactionInfo")
    if signed_tx:
        transaction_info = verify_signed_payload(
            signed_tx, trusted_roots, at_time=at_time
        )
        if bundle_id and transaction_info.get("bundleId") not in (None, bundle_id):
            raise IAPVerificationError("Transaction bundleId does not match app")

    renewal_info: Dict = {}
    signed_renewal = data.get("signedRenewalInfo")
    if signed_renewal:
        renewal_info = verify_signed_payload(
            signed_renewal, trusted_roots, at_time=at_time
        )

    return AppleNotification(
        notification_type=notification_type,
        subtype=payload.get("subtype"),
        notification_uuid=notification_uuid,
        bundle_id=payload_bundle,
        environment=environment,
        transaction_info=transaction_info,
        renewal_info=renewal_info,
    )
