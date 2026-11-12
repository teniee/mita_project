"""Retry safety for tools that create rows.

ChatGPT can send the same tool call twice (a timeout, a retried turn). Each
create tool takes an ``idempotency_key`` argument; MITA records a digest of
(operation, ChatGPT conversation, key) together with a digest of the request
and the ids of the rows it created, **in the same database transaction as
those rows**:

* the record is inserted *before* the rows, so a concurrent duplicate blocks
  on its primary key until the first commits, then sees the record and
  replays — two identical in-flight calls can never both write;
* the same key with a *different* request is refused (a key is one request);
* the replay returns the rows created the first time, marked
  ``already_recorded``, and writes nothing.

Never deduplicates by content: two real €3.50 coffees on one day are two
transactions unless the client sends the same key. Rows hold digests and ids
only — no amounts, merchants or other values — and are purged per user after
``RETENTION``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import McpIdempotencyKey
from app.mcp.errors import ValidationError

RETENTION = timedelta(days=30)

KEY_REUSED_MESSAGE = (
    "This idempotency_key was already used for a different request. Create a new "
    "key for a new request; reuse a key only to retry exactly the same request."
)


def scope_hash(operation: str, session_digest: str, key: str) -> str:
    return hashlib.sha256(f"{operation}|{session_digest}|{key}".encode()).hexdigest()


def request_hash(payload: Any) -> str:
    """Digest of the canonical request (sorted JSON, Decimals as strings)."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


@dataclass(frozen=True)
class Claim:
    """Outcome of claiming a key: either fresh (do the work) or a replay."""

    record: McpIdempotencyKey
    replay_ids: Optional[List[UUID]]

    @property
    def is_replay(self) -> bool:
        return self.replay_ids is not None

    def complete(self, resource_ids: Sequence[UUID]) -> None:
        self.record.resource_ids = [str(i) for i in resource_ids]


def _existing(db: Session, user_id: UUID, scope: str) -> Optional[McpIdempotencyKey]:
    return db.get(McpIdempotencyKey, (user_id, scope))


def claim(
    db: Session,
    *,
    user_id: UUID,
    operation: str,
    session_digest: str,
    key: str,
    request: Any,
    now: datetime,
) -> Claim:
    """Claim ``key`` for this request inside the caller's transaction.

    Fresh: the record is flushed (holding the key) and the caller does the
    work, calls ``Claim.complete`` with the new ids and commits. Replay: the
    caller returns the original rows and must not write.
    """
    scope = scope_hash(operation, session_digest, key)
    digest = request_hash(request)
    db.execute(
        delete(McpIdempotencyKey).where(
            McpIdempotencyKey.user_id == user_id,
            McpIdempotencyKey.created_at < now - RETENTION,
        )
    )
    found = _existing(db, user_id, scope)
    if found is None:
        record = McpIdempotencyKey(
            user_id=user_id,
            scope_hash=scope,
            operation=operation,
            request_hash=digest,
            resource_ids=[],
            created_at=now,
        )
        try:
            # The INSERT blocks on a concurrent twin's uncommitted row and
            # fails once that twin commits; the savepoint keeps our outer
            # transaction usable either way.
            with db.begin_nested():
                db.add(record)
                db.flush()
            return Claim(record=record, replay_ids=None)
        except IntegrityError:
            # A concurrent identical call committed first: replay its result.
            found = db.execute(
                select(McpIdempotencyKey).where(
                    McpIdempotencyKey.user_id == user_id,
                    McpIdempotencyKey.scope_hash == scope,
                )
            ).scalar_one()
    if found.request_hash != digest or found.operation != operation:
        raise ValidationError(KEY_REUSED_MESSAGE)
    return Claim(record=found, replay_ids=[UUID(i) for i in found.resource_ids or []])
