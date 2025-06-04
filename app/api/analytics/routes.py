
from fastapi import APIRouter, Depends
from app.core.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from app.api.analytics.schemas import CalendarPayload, AnomalyResult, AggregateResult, MonthlyAnalyticsOut, TrendOut
from app.services.analytics_service import (
    get_monthly_category_totals,
    get_monthly_trend,
    analyze_aggregate,
    analyze_anomalies
)
from app.core.session import get_db
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/monthly/{user_id}", response_model=MonthlyAnalyticsOut)
async def monthly(user_id: str, db: Session = Depends(get_db)):
    result = get_monthly_category_totals(user_id, db)
    return success_response({"categories": result})

@router.get("/trend/{user_id}", response_model=TrendOut)
async def trend(user_id: str, db: Session = Depends(get_db)):
    result = get_monthly_trend(user_id, db)
    return success_response({"trend": result})

@router.post("/aggregate", response_model=AggregateResult)
async def aggregate(payload: CalendarPayload):
    return success_response(analyze_aggregate(payload.calendar))

@router.post("/anomalies", response_model=AnomalyResult)
async def anomalies(payload: CalendarPayload):
    return success_response(analyze_anomalies(payload.calendar))