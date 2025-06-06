from fastapi import APIRouter
from pydantic import BaseModel

from app.services.core.api.analytics_engine import (
    aggregate_monthly_data,
    calculate_monthly_savings_progress,
    detect_anomalies,
)
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/analytics", tags=["analytics"])


class CalendarRequest(BaseModel):
    calendar: list


class SavingsProgressRequest(BaseModel):
    current_month: list
    previous_month: list


@router.post("/aggregate")
async def aggregate(payload: CalendarRequest):
    result = aggregate_monthly_data(payload.calendar)
    return success_response(result)


@router.post("/anomalies")
async def anomalies(payload: CalendarRequest):
    result = detect_anomalies(payload.calendar)
    return success_response(result)


@router.post("/savings-progress")
async def savings_progress(payload: SavingsProgressRequest):
    result = calculate_monthly_savings_progress(
        payload.current_month, payload.previous_month
    )
    return success_response(result)
