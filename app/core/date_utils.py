"""
Date utility helpers for SQLAlchemy DateTime column queries.

DailyPlan.date is DateTime(timezone=True). Comparing it with a Python
`date` object via filter_by(date=day) produces:
    WHERE date = '2026-03-19 00:00:00+00'
which misses rows stored at any other time on that day (e.g. noon UTC).

Use day_to_range() to build an inclusive range that covers the full day.
"""
from datetime import date, datetime
from typing import Tuple


def day_to_range(d: date) -> Tuple[datetime, datetime]:
    """Return (start, end) datetime covering the full calendar day."""
    return (
        datetime(d.year, d.month, d.day, 0, 0, 0),
        datetime(d.year, d.month, d.day, 23, 59, 59),
    )
