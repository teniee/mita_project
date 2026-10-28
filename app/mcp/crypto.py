"""Opaque references and signed tokens handed to ChatGPT.

Everything here is keyed by ``MCP_DATA_SECRET`` through HKDF with a distinct
label per purpose, and every value is bound to the authenticated user:

* **transaction references** (``tx_…``): the transaction id encrypted with
  AES-SIV, the user id as associated data. Deterministic (the same row always
  has the same reference), opaque (no database id is visible), and useless to
  anyone else — decrypting under another user's id fails authentication;
* **budget drafts** (``bd1_…``) and **list cursors** (``cur1_…``): a compact
  binary payload plus a truncated HMAC over (purpose, user id, payload);
* **budget drafts with the user's own budget lines** (``bd2_…``, F-11): the
  same claims plus the lines the user asked for, encrypted with AES-SIV (the
  user id as associated data), so their names and amounts are never readable
  in the token and it cannot be edited in transit.

A reference or token that fails verification is reported as "not found" or
"expired" — never as a different user's object. Ownership is still enforced
in SQL on every lookup; these only keep identifiers out of model context.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

TRANSACTION_REF_PREFIX = "tx_"
DRAFT_PREFIX = "bd1_"
DRAFT_V2_PREFIX = "bd2_"
MAX_DRAFT_TOKEN_CHARS = 8192
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


# One requested budget line: (line key, amount as "200.00", replaced MITA
# lines or None to keep the saved choice).
DraftLine = Tuple[str, str, Optional[Tuple[str, ...]]]


@dataclass(frozen=True)
class DraftClaims:
    year: int
    month: int
    expires_at: int
    digest: bytes  # first 16 bytes of the draft's SHA-256
    # The user's own budget lines asked for in the preview (F-11), and the
    # lines asked to leave the plan. Empty for a bd1_ token.
    lines: Tuple[DraftLine, ...] = ()
    remove: Tuple[str, ...] = ()

    @property
    def has_request(self) -> bool:
        return bool(self.lines or self.remove)


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
        self._draft_siv = AESSIV(_derive(secret, b"mita-mcp/budget-draft/v2", 64))
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
        if not claims.has_request:
            return self._seal(DRAFT_PREFIX, b"budget-draft", user_id, payload)
        request = json.dumps(
            {
                "l": [
                    [key, amount, list(replaces) if replaces is not None else None]
                    for key, amount, replaces in claims.lines
                ],
                "r": list(claims.remove),
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        sealed = self._draft_siv.encrypt(
            payload + request, [b"budget-draft/v2", user_id.bytes]
        )
        return DRAFT_V2_PREFIX + _b64(sealed)

    def open_budget_draft(self, user_id: UUID, token: str) -> Optional[DraftClaims]:
        if isinstance(token, str) and token.startswith(DRAFT_V2_PREFIX):
            return self._open_draft_v2(user_id, token)
        payload = self._open(
            DRAFT_PREFIX, b"budget-draft", user_id, token, _DRAFT_LAYOUT.size
        )
        if payload is None:
            return None
        return _draft_claims(payload)

    def _open_draft_v2(self, user_id: UUID, token: str) -> Optional[DraftClaims]:
        if len(token) > MAX_DRAFT_TOKEN_CHARS:
            return None
        sealed = _unb64(token[len(DRAFT_V2_PREFIX) :])
        if sealed is None or len(sealed) <= _DRAFT_LAYOUT.size + 16:
            return None
        try:
            raw = self._draft_siv.decrypt(sealed, [b"budget-draft/v2", user_id.bytes])
        except InvalidTag:
            return None
        claims = _draft_claims(raw[: _DRAFT_LAYOUT.size])
        if claims is None:
            return None
        try:
            request = json.loads(raw[_DRAFT_LAYOUT.size :].decode())
            lines = tuple(
                (
                    str(key),
                    str(amount),
                    tuple(str(c) for c in replaces) if replaces is not None else None,
                )
                for key, amount, replaces in request["l"]
            )
            remove = tuple(str(key) for key in request["r"])
        except (ValueError, KeyError, TypeError):
            return None
        return DraftClaims(
            claims.year, claims.month, claims.expires_at, claims.digest, lines, remove
        )

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


def _draft_claims(payload: bytes) -> Optional[DraftClaims]:
    year, month, expires_at, digest = _DRAFT_LAYOUT.unpack(payload)
    try:
        date(year, month, 1)
    except ValueError:
        return None
    return DraftClaims(year, month, expires_at, digest)


def request_digest(*parts: object) -> str:
    """Stable SHA-256 over a canonical rendering of the parts."""
    text = "\x1f".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(text.encode()).hexdigest()
