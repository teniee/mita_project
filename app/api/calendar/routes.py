from fastapi import APIRouter, Body, Depends, HTTPException

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
    calendar = generate_shell_calendar(user.id, payload.dict())
    return success_response({"calendar": calendar})
