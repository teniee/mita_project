from datetime import datetime
from zoneinfo import ZoneInfo


def to_user_timezone(dt: datetime, tz: str) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz))


def from_user_timezone(dt: datetime, tz: str) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz))
    return dt.astimezone(ZoneInfo("UTC"))
