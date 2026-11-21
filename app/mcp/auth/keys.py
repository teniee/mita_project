"""RS256 signing key for MCP access tokens, and its public JWKS."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.mcp.config import McpConfigError

MIN_RSA_BITS = 2048


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _public_jwk(public_key: rsa.RSAPublicKey) -> Dict[str, str]:
    numbers = public_key.public_numbers()
    jwk = {"kty": "RSA", "e": _b64url_uint(numbers.e), "n": _b64url_uint(numbers.n)}
    # RFC 7638 thumbprint as the key id: stable for the key, changes on rotation.
    canonical = json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()
    kid = (
        base64.urlsafe_b64encode(hashlib.sha256(canonical).digest())
        .decode()
        .rstrip("=")
    )
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


@dataclass(frozen=True)
class SigningKeys:
    private_key: rsa.RSAPrivateKey
    kid: str
    verification_keys: Dict[str, rsa.RSAPublicKey]  # kid -> key (current + previous)
    jwks: Dict[str, List[Dict[str, str]]]


def load_signing_keys(
    private_pem: str, previous_public_pem: Optional[str] = None
) -> SigningKeys:
    try:
        private_key = serialization.load_pem_private_key(
            private_pem.encode(), password=None
        )
    except (ValueError, TypeError) as exc:
        raise McpConfigError(
            "MCP_OAUTH_PRIVATE_KEY is not a valid unencrypted PEM private key"
        ) from exc
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise McpConfigError("MCP_OAUTH_PRIVATE_KEY must be an RSA key")
    if private_key.key_size < MIN_RSA_BITS:
        raise McpConfigError(
            f"MCP_OAUTH_PRIVATE_KEY must be at least {MIN_RSA_BITS} bits"
        )

    current = _public_jwk(private_key.public_key())
    keys = {current["kid"]: private_key.public_key()}
    jwks = [current]
    if previous_public_pem:
        try:
            previous = serialization.load_pem_public_key(previous_public_pem.encode())
        except ValueError as exc:
            raise McpConfigError(
                "MCP_OAUTH_PREVIOUS_PUBLIC_KEY is not a valid PEM public key"
            ) from exc
        if not isinstance(previous, rsa.RSAPublicKey):
            raise McpConfigError("MCP_OAUTH_PREVIOUS_PUBLIC_KEY must be an RSA key")
        prev_jwk = _public_jwk(previous)
        keys[prev_jwk["kid"]] = previous
        jwks.append(prev_jwk)
    return SigningKeys(
        private_key=private_key,
        kid=current["kid"],
        verification_keys=keys,
        jwks={"keys": jwks},
    )


def generate_private_key_pem(bits: int = 3072) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
