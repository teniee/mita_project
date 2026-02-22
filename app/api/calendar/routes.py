from collections import defaultdict
from datetime import datetime
import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import extract
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------- Schemas ----------------------------
from app.api.calendar.schemas import (
    CalendarDayOut,
    CalendarDayStateOut,
    CalendarOut,
    DayInput,
    EditDayRequest,
    GenerateCalendarRequest,
    RedistributeInput,
    RedistributeResult,
    ShellCalendarOut,
    ShellConfig,
)
from app.api.dependencies import get_current_user
from app.core.session import get_db
from app.db.models.daily_plan import DailyPlan

# core budget redistribution algorithm
from app.engine.budget_redistributor import (
    redistribute_budget as redistribute_calendar_budget,
)

# -------------------------- Service functions -------------------
from app.services.calendar_service import (
    fetch_calendar,
    fetch_day_state,
    generate_calendar,
    generate_shell_calendar,
    update_day,
)
from app.utils.response_wrapper import success_response

router = APIRouter(prefix="/calendar", tags=["calendar"])


# ----------------------------- ROUTES ----------------------------


@router.post("/generate", response_model=CalendarOut)
async def generate(data: GenerateCalendarRequest):
    days = generate_calendar(
        data.calendar_id,
        data.start_date,
        data.num_days,
        data.budget_plan,
    )
    return success_response(
        {
            "calendar_id": data.calendar_id,
            "days": days,
        }
    )


@router.get("/day/{year}/{month}/{day}", response_model=CalendarDayOut)
async def get_day_view(
    year: int,
    month: int,
    day: int,
    user=Depends(get_current_user),  # noqa: B008
):
    calendar = fetch_calendar(user.id, year, month)
    if day not in calendar:
        raise HTTPException(status_code=404, detail="Day not found")
    return success_response(calendar[day])


@router.patch("/day/{year}/{month}/{day}", response_model=CalendarDayOut)
async def edit_day(
    year: int,
    month: int,
    day: int,
    payload: EditDayRequest = Body(...),
    user=Depends(get_current_user),  # noqa: B008
):
    calendar = fetch_calendar(user.id, year, month)
    if day not in calendar:
        raise HTTPException(status_code=404, detail="Day not found")

    updated_day = update_day(calendar, day, payload.updates)
    return success_response(updated_day)


@router.post("/day_state", response_model=CalendarDayStateOut)
async def get_day_state(
    payload: DayInput,
    user=Depends(get_current_user),  # noqa: B008
):
    state = fetch_day_state(
        user.id,
        payload.year,
        payload.month,
        payload.day,
    )
    return success_response({"state": state})


@router.post("/redistribute", response_model=RedistributeResult)
async def redistribute(payload: RedistributeInput):
    """Return the calendar updated by ``redistribute_budget``.

    The ``strategy`` field is currently unused but reserved for future modes.
    """
    updated_calendar = redistribute_calendar_budget(payload.calendar)
    return success_response({"updated_calendar": updated_calendar})


@router.post("/shell", response_model=ShellCalendarOut)
async def get_shell(
    payload: ShellConfig,
    user=Depends(get_current_user),  # noqa: B008
):
    try:
        # Convert ShellConfig to the format expected by generate_shell_calendar
        shell_data = {
            "start_date": f"{payload.year}-{payload.month:02d}-01",
            "num_days": 30,  # Default to 30 days for shell calendar
            "budget_plan": {
                # Convert the weights to actual budget amounts based on income
                category: float(payload.income * weight / 100) if weight else 0.0
                for category, weight in payload.weights.items()
            }
        }

        # Add fixed expenses to budget plan
        for category, amount in payload.fixed.items():
            if category in shell_data["budget_plan"]:
                shell_data["budget_plan"][category] += float(amount)
            else:
                shell_data["budget_plan"][category] = float(amount)

        calendar = generate_shell_calendar(user.id, shell_data)
        return success_response({"calendar": calendar})
    except Exception as e:
        logger.error(f"Error generating shell calendar: {e}")
        # Return a fallback response to prevent 500 error
        return success_response({
            "calendar": [{
                "date": f"{payload.year}-{payload.month:02d}-01",
                "planned_budget": {},
                "limit": 0.0,
                "total": 0.0
            }]
        })


def _fetch_saved_calendar_data(db: Session, user_id, year: int, month: int):
    """Shared logic to retrieve saved calendar data from DailyPlan table."""
    try:
        rows = db.query(DailyPlan).filter(
            DailyPlan.user_id == user_id,
            extract('year', DailyPlan.date) == year,
            extract('month', DailyPlan.date) == month,
        ).order_by(DailyPlan.date).all()

        if not rows:
            logger.info(f"No saved calendar data found for user {user_id}, {year}-{month}")
            return success_response({"calendar": []})

        logger.info(f"Retrieved {len(rows)} saved calendar entries for user {user_id}, {year}-{month}")

        # Group by date to aggregate categories for each day
        days_data = defaultdict(lambda: {
            'date': None,
            'day': 0,
            'total_budget': 0,
            'total_planned': 0,
            'total_spent': 0,
            'categories': {}
        })

        for row in rows:
            day_key = row.date.isoformat()
            day_data = days_data[day_key]

            if day_data['date'] is None:
                day_data['date'] = row.date.isoformat()
                day_data['day'] = row.date.day

            # Aggregate amounts
            day_data['total_budget'] += (row.daily_budget or 0)
            day_data['total_planned'] += (row.planned_amount or 0)
            day_data['total_spent'] += (row.spent_amount or 0)

            # Add category details (convert Decimal to float for JSON serialization)
            category_name = row.category or 'uncategorized'
            day_data['categories'][category_name] = {
                'planned': float(row.planned_amount or 0),
                'spent': float(row.spent_amount or 0),
                'status': row.status or 'pending'
            }

        # Convert to list format matching the shell calendar structure
        calendar_days = []
        for day_data in days_data.values():
            calendar_days.append({
                'date': day_data['date'],
                'day': day_data['day'],
                'planned_budget': day_data['categories'],
                'limit': float(day_data['total_budget']),
                'total': float(day_data['total_planned']),
                'spent': float(day_data['total_spent']),
                'status': 'active' if day_data['total_spent'] > 0 else 'pending'
            })

        # Sort by date
        calendar_days.sort(key=lambda x: x['date'])

        return success_response({"calendar": calendar_days})

    except Exception as e:
        logger.error(f"Error retrieving saved calendar: {str(e)}", exc_info=True)
        return success_response({"calendar": []})


@router.get("/current-month")
def get_current_month_calendar(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Convenience endpoint to retrieve calendar for the current month.

    This is a wrapper around /saved/{year}/{month} that automatically
    uses the current year and month based on server time (UTC).
    """
    now = datetime.utcnow()
    return _fetch_saved_calendar_data(db, user.id, now.year, now.month)


@router.get("/saved/{year}/{month}")
def get_saved_calendar(
    year: int,
    month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Retrieve saved calendar data for a specific month from DailyPlan table.
    This returns the calendar that was saved during onboarding or budget updates.

    Returns empty list if no saved data exists for this month.
    This endpoint is used by the mobile app to retrieve the budget created during onboarding.
    """
    return _fetch_saved_calendar_data(db, user.id, year, month)
