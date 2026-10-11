"""Product analytics for the ChatGPT app: what was used, never what was said.

One row per tool call (``tool_call_succeeded`` / ``tool_call_failed``) plus a
small set of lifecycle events (``transaction_created``, ``budget_saved``…).
The taxonomy, properties and privacy rules are documented in
``docs/chatgpt-app/product-analytics.md``; this module enforces them:

* **Allow-listed events and properties.** ``record()`` drops any event name
  or property key that is not listed below, and any property value that is
  not a short enum-like string, a small integer or a boolean. Amounts,
  merchants, titles, free text and identifiers cannot be stored here.
* **Pseudonymous, and only with the user's consent.** ``user_key`` is an HMAC
  of the MITA user id under ``MCP_ANALYTICS_SECRET``; ``session_key`` is an
  HMAC of ChatGPT's anonymized conversation id. Neither raw value is stored.
  A user who has not opted in (or who opted out) produces events with both
  keys NULL — counted for reliability, linked to nobody.
* **Out of band.** Events are queued after the tool has produced its result
  and written by a background task in a separate transaction. A failure here
  is logged by type and dropped; it can never fail, slow down or roll back a
  financial operation, and read-only tools stay read-only.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import hmac
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol
from uuid import UUID

logger = logging.getLogger("app.mcp.analytics")

TOOL_CONTRACT_VERSION = "2.0"
SURFACE = "chatgpt"

TOOL_CALL_SUCCEEDED = "tool_call_succeeded"
TOOL_CALL_FAILED = "tool_call_failed"

# event -> allowed property keys (values: see _clean_value)
EVENT_PROPERTIES: Dict[str, frozenset] = {
    TOOL_CALL_SUCCEEDED: frozenset({"replayed"}),
    TOOL_CALL_FAILED: frozenset(),
    "account_created": frozenset(),
    "oauth_connected": frozenset({"new_account"}),
    "onboarding_started": frozenset(),
    "onboarding_completed": frozenset(),
    "financial_profile_created": frozenset({"fields"}),
    "financial_profile_updated": frozenset({"fields"}),
    "transaction_created": frozenset({"entry_method"}),
    "transaction_batch_created": frozenset({"entry_method", "item_count"}),
    "transaction_updated": frozenset({"fields"}),
    "transaction_deleted": frozenset(),
    "receipt_flow_completed": frozenset({"item_count"}),
    "budget_previewed": frozenset({"month_offset", "existing_plan"}),
    "budget_saved": frozenset({"month_offset"}),
    "budget_replaced": frozenset({"month_offset"}),
    "recurring_expense_created": frozenset({"recurrence"}),
    "savings_goal_created": frozenset({"has_target_date"}),
    "feedback_submitted": frozenset({"type", "feature_area", "rating"}),
    "usage_analytics_enabled": frozenset(),
}

EVENT_NAMES = frozenset(EVENT_PROPERTIES)

# tool -> feature (one row per tool; every tool must be listed — enforced by test)
TOOL_FEATURES: Dict[str, str] = {
    "get_profile": "account",
    "get_setup_status": "setup",
    "update_financial_profile": "setup",
    "get_financial_summary": "summary",
    "list_transactions": "transactions",
    "add_transaction": "transactions",
    "add_transactions": "transactions",
    "update_transaction": "transactions",
    "delete_transaction": "transactions",
    "get_spending_breakdown": "spending",
    "get_budget_status": "budget_status",
    "get_budget_forecast": "forecast",
    "preview_monthly_budget": "budget_plan",
    "save_monthly_budget": "budget_plan",
    "get_recurring_expenses": "recurring",
    "add_recurring_expense": "recurring",
    "get_goals": "goals",
    "create_savings_goal": "goals",
    "get_spending_history": "history",
    "get_financial_climate": "history",
    "submit_feedback": "feedback",
    "set_usage_analytics": "privacy",
}

_ENUM_VALUE = re.compile(r"^[a-z0-9_]{1,32}$")
_LOCALE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8}){0,2}$")


def _clean_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and -1000 <= value <= 1000:
        return value
    if isinstance(value, str) and _ENUM_VALUE.fullmatch(value):
        return value
    if isinstance(value, (list, tuple)) and len(value) <= 10:
        cleaned = [v for v in value if isinstance(v, str) and _ENUM_VALUE.fullmatch(v)]
        if len(cleaned) == len(value):
            return sorted(cleaned)
    return None


def clean_properties(event_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    allowed = EVENT_PROPERTIES.get(event_name, frozenset())
    out: Dict[str, Any] = {}
    for key, value in (properties or {}).items():
        if key not in allowed:
            continue
        cleaned = _clean_value(value)
        if cleaned is not None:
            out[key] = cleaned
    return out


def clean_locale(raw: Any) -> Optional[str]:
    if isinstance(raw, str) and len(raw) <= 16 and _LOCALE.fullmatch(raw):
        return raw.replace("_", "-")
    return None


def _hmac_hex(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()[:32]


def user_key(secret: str, user_id: UUID) -> str:
    return _hmac_hex(secret, f"mita-analytics/user/v1:{user_id}")


def session_key(secret: str, raw_session: str) -> str:
    return _hmac_hex(secret, f"mita-analytics/session/v1:{raw_session}")


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EventRecord:
    occurred_at: datetime
    event_name: str
    user_id: Optional[UUID]  # resolved to user_key by the sink; never stored raw
    user_key: Optional[str]
    session_key: Optional[str]
    feature: Optional[str] = None
    tool_name: Optional[str] = None
    intent_code: Optional[str] = None
    status: str = "ok"
    error_code: Optional[str] = None
    latency_ms: Optional[int] = None
    locale: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallTelemetry:
    """Collected while one tool call runs; turned into events afterwards."""

    tool: str
    intent: Optional[str] = None
    lifecycle: List[tuple] = field(default_factory=list)  # (event_name, props)
    replayed: bool = False


_current_call: contextvars.ContextVar[Optional[CallTelemetry]] = contextvars.ContextVar(
    "mita_mcp_call_telemetry", default=None
)


def emit(event_name: str, **properties: Any) -> None:
    """Record a lifecycle event for the current tool call (no-op outside one).

    Called by tool bodies at the point the fact becomes true (a row was
    created, setup became complete). The event is only written if the call
    then succeeds.
    """
    call = _current_call.get()
    if call is not None and event_name in EVENT_NAMES:
        call.lifecycle.append((event_name, properties))


def mark_replayed() -> None:
    call = _current_call.get()
    if call is not None:
        call.replayed = True


def bind_call(call: CallTelemetry) -> contextvars.Token:
    return _current_call.set(call)


def unbind_call(token: contextvars.Token) -> None:
    _current_call.reset(token)


# ---------------------------------------------------------------------------
# Sinks
# ---------------------------------------------------------------------------


class AnalyticsSink(Protocol):
    def record(self, events: Iterable[EventRecord]) -> None: ...

    async def flush(self) -> None: ...


class NullSink:
    def record(self, events: Iterable[EventRecord]) -> None:
        return None

    async def flush(self) -> None:
        return None


class MemorySink:
    """Keeps events in a list (tests)."""

    def __init__(self) -> None:
        self.events: List[EventRecord] = []

    def record(self, events: Iterable[EventRecord]) -> None:
        self.events.extend(events)

    async def flush(self) -> None:
        return None

    def names(self) -> List[str]:
        return [e.event_name for e in self.events]


class Analytics:
    """Turns one finished tool call (or an OAuth milestone) into event rows."""

    def __init__(self, secret: str, sink: Optional[AnalyticsSink] = None) -> None:
        self.secret = secret
        self.sink: AnalyticsSink = sink or NullSink()

    def _keys(self, user_id: Optional[UUID], consent: bool, raw_session: Optional[str]):
        if user_id is None or not consent:
            return None, None
        session = (
            session_key(self.secret, raw_session)
            if isinstance(raw_session, str) and 0 < len(raw_session) <= 256
            else None
        )
        return user_key(self.secret, user_id), session

    def tool_call(
        self,
        call: CallTelemetry,
        *,
        outcome: str,
        latency_ms: float,
        user_id: Optional[UUID],
        consent: bool,
        meta: Optional[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> None:
        try:
            meta = meta or {}
            ukey, skey = self._keys(user_id, consent, meta.get("openai/session"))
            stamp = now or datetime.now(timezone.utc)
            locale = clean_locale(meta.get("openai/locale"))
            feature = TOOL_FEATURES.get(call.tool)
            ok = outcome == "ok"
            base = dict(
                occurred_at=stamp,
                user_id=user_id if ukey else None,
                user_key=ukey,
                session_key=skey,
                feature=feature,
                tool_name=call.tool,
                intent_code=call.intent,
                locale=locale,
            )
            events = [
                EventRecord(
                    event_name=TOOL_CALL_SUCCEEDED if ok else TOOL_CALL_FAILED,
                    status="ok" if ok else "error",
                    error_code=None if ok else outcome[:32],
                    latency_ms=int(round(latency_ms)),
                    properties=(
                        clean_properties(TOOL_CALL_SUCCEEDED, {"replayed": True})
                        if ok and call.replayed
                        else {}
                    ),
                    **base,
                )
            ]
            if ok:
                for name, props in call.lifecycle:
                    events.append(
                        EventRecord(
                            event_name=name,
                            properties=clean_properties(name, props),
                            **base,
                        )
                    )
            self.sink.record(events)
        except Exception as exc:  # noqa: BLE001 - analytics never fails a call
            logger.warning(
                "analytics dropped",
                extra={"event": "analytics_dropped", "reason": type(exc).__name__},
            )

    def milestone(
        self,
        event_name: str,
        *,
        user_id: Optional[UUID],
        consent: bool,
        properties: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> None:
        """An event outside a tool call (account created, OAuth connected)."""
        if event_name not in EVENT_NAMES:
            return
        try:
            ukey, _ = self._keys(user_id, consent, None)
            self.sink.record(
                [
                    EventRecord(
                        occurred_at=now or datetime.now(timezone.utc),
                        event_name=event_name,
                        user_id=user_id if ukey else None,
                        user_key=ukey,
                        session_key=None,
                        properties=clean_properties(event_name, properties or {}),
                    )
                ]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "analytics dropped",
                extra={"event": "analytics_dropped", "reason": type(exc).__name__},
            )

    async def flush(self) -> None:
        try:
            await asyncio.wait_for(self.sink.flush(), timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "analytics flush failed",
                extra={"event": "analytics_dropped", "reason": type(exc).__name__},
            )
