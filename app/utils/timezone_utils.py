from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional


def to_user_timezone(dt: Optional[datetime], tz: str) -> Optional[datetime]:
    """Convert UTC datetime to user's timezone. Returns None if dt is None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz))


def from_user_timezone(dt: Optional[datetime], tz: str) -> Optional[datetime]:
    """Convert user's timezone datetime to UTC. Returns None if dt is None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(ZoneInfo("UTC"))
