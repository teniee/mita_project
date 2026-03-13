"""
Redistribution Audit Log
Real event log for budget redistributions — replaces heuristic history.
"""
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# In-memory audit log (replace with DB table in future migration)
# Format: {user_id_str: [event_dict, ...]}
_audit_log: Dict[str, List[Dict]] = {}


def record_redistribution_event(
    user_id: UUID,
    from_category: str,
    to_category: str,
    amount: Decimal,
    reason: str,
    from_day: Optional[str] = None,
) -> Dict:
    """
    Record a redistribution event to the audit log.
    Called by budget_redistributor and realtime_rebalancer after each transfer.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": str(user_id),
        "from_category": from_category,
        "to_category": to_category,
        "amount": float(amount),
        "reason": reason,
        "from_day": from_day,
    }
    key = str(user_id)
    if key not in _audit_log:
        _audit_log[key] = []
    _audit_log[key].append(event)
    logger.info(f"Redistribution: {from_category} → {to_category} ${amount:.2f} ({reason})")
    return event


def get_redistribution_history(
    user_id: UUID,
    limit: int = 50,
) -> List[Dict]:
    """
    Return real redistribution history for a user (most recent first).
    """
    key = str(user_id)
    events = _audit_log.get(key, [])
    return list(reversed(events[-limit:]))


def clear_user_audit_log(user_id: UUID) -> None:
    """Clear audit log for a user (e.g., on month rollover)."""
    _audit_log.pop(str(user_id), None)
