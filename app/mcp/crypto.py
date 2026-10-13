"""Opaque references and signed tokens handed to ChatGPT.

Everything here is keyed by ``MCP_DATA_SECRET`` through HKDF with a distinct
label per purpose, and every value is bound to the authenticated user:

* **transaction references** (``tx_…``): the transaction id encrypted with
  AES-SIV, the user id as associated data. Deterministic (the same row always
  has the same reference), opaque (no database id is visible), and useless to
  anyone else — decrypting under another user's id fails authentication;
* **budget drafts** (``bd1_…``) and **list cursors** (``cur1_…``): a compact
  binary payload plus a truncated HMAC over (purpose, user id, payload).

A reference or token that fails verification is reported as "not found" or
"expired" — never as a different user's object. Ownership is still enforced
in SQL on every lookup; these only keep identifiers out of model context.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

TRANSACTION_REF_PREFIX = "tx_"
DRAFT_PREFIX = "bd1_"
CURSOR_PREFIX = "cur1_"
MAC_BYTES = 16  # 128-bit truncated HMAC-SHA256

_DRAFT_LAYOUT = struct.Struct(">HBI16s")  # year, month, expires_at, digest[:16]
_CURSOR_LAYOUT = struct.Struct(">q16s8s")  # spent_at µs, transaction id, filter digest


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> Optional[bytes]:
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, TypeError):
        return None


def _derive(secret: str, label: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=label).derive(
        secret.encode()
    )


@dataclass(frozen=True)
class DraftClaims:
    year: int
    month: int
    expires_at: int
    digest: bytes  # first 16 bytes of the draft's SHA-256


@dataclass(frozen=True)
class CursorPosition:
    spent_at_us: int
    transaction_id: UUID
    filter_digest: bytes


class DataKeys:
    def __init__(self, secret: str):
        if len(secret) < 32:
            raise ValueError("MCP_DATA_SECRET must be at least 32 characters")
        self._siv = AESSIV(_derive(secret, b"mita-mcp/transaction-ref/v1", 64))
        self._mac_key = _derive(secret, b"mita-mcp/signed-token/v1", 32)

    # --- transaction references ---------------------------------------------

    def transaction_ref(self, user_id: UUID, transaction_id: UUID) -> str:
        sealed = self._siv.encrypt(transaction_id.bytes, [b"txn", user_id.bytes])
        return TRANSACTION_REF_PREFIX + _b64(sealed)

    def transaction_id(self, user_id: UUID, ref: str) -> Optional[UUID]:
        if not isinstance(ref, str) or not ref.startswith(TRANSACTION_REF_PREFIX):
            return None
        sealed = _unb64(ref[len(TRANSACTION_REF_PREFIX) :])
        if sealed is None or len(sealed) != 32:
            return None
        try:
            raw = self._siv.decrypt(sealed, [b"txn", user_id.bytes])
        except InvalidTag:
            return None
        return UUID(bytes=raw)

    # --- signed compact tokens -------------------------------------------------

    def _mac(self, purpose: bytes, user_id: UUID, payload: bytes) -> bytes:
        message = purpose + b"|" + user_id.bytes + b"|" + payload
        return hmac.new(self._mac_key, message, hashlib.sha256).digest()[:MAC_BYTES]

    def _seal(self, prefix: str, purpose: bytes, user_id: UUID, payload: bytes) -> str:
        return prefix + _b64(payload + self._mac(purpose, user_id, payload))

    def _open(
        self, prefix: str, purpose: bytes, user_id: UUID, token: str, size: int
    ) -> Optional[bytes]:
        if not isinstance(token, str) or not token.startswith(prefix):
            return None
        raw = _unb64(token[len(prefix) :])
        if raw is None or len(raw) != size + MAC_BYTES:
            return None
        payload, tag = raw[:size], raw[size:]
        if not hmac.compare_digest(tag, self._mac(purpose, user_id, payload)):
            return None
        return payload

    def budget_draft(self, user_id: UUID, claims: DraftClaims) -> str:
        payload = _DRAFT_LAYOUT.pack(
            claims.year, claims.month, claims.expires_at, claims.digest[:16]
        )
        return self._seal(DRAFT_PREFIX, b"budget-draft", user_id, payload)

    def open_budget_draft(self, user_id: UUID, token: str) -> Optional[DraftClaims]:
        payload = self._open(
            DRAFT_PREFIX, b"budget-draft", user_id, token, _DRAFT_LAYOUT.size
        )
        if payload is None:
            return None
        year, month, expires_at, digest = _DRAFT_LAYOUT.unpack(payload)
        try:
            date(year, month, 1)
        except ValueError:
            return None
        return DraftClaims(year, month, expires_at, digest)

    def cursor(self, user_id: UUID, position: CursorPosition) -> str:
        payload = _CURSOR_LAYOUT.pack(
            position.spent_at_us,
            position.transaction_id.bytes,
            position.filter_digest[:8],
        )
        return self._seal(CURSOR_PREFIX, b"list-cursor", user_id, payload)

    def open_cursor(self, user_id: UUID, token: str) -> Optional[CursorPosition]:
        payload = self._open(
            CURSOR_PREFIX, b"list-cursor", user_id, token, _CURSOR_LAYOUT.size
        )
        if payload is None:
            return None
        spent_at_us, txn_bytes, filter_digest = _CURSOR_LAYOUT.unpack(payload)
        return CursorPosition(spent_at_us, UUID(bytes=txn_bytes), filter_digest)


def request_digest(*parts: object) -> str:
    """Stable SHA-256 over a canonical rendering of the parts."""
    text = "\x1f".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(text.encode()).hexdigest()
