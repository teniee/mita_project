"""Data schemas for analytics endpoints."""

from typing import Dict, List

from pydantic import BaseModel


class CalendarPayload(BaseModel):
    """Request body containing the behavioral calendar."""

    calendar: List[dict]


class AnomalyResult(BaseModel):
    """Payload for anomaly detection response."""

    anomalies: List[dict]


class AggregateResult(BaseModel):
    """Aggregated monthly data output."""

    aggregation: Dict[str, float]


class MonthlyAnalyticsOut(BaseModel):
    """Totals by category for the current month."""

    categories: Dict[str, float]


class TrendOut(BaseModel):
    """Daily expense trend output."""

    trend: List[dict]
