from fastapi import APIRouter, HTTPException, Body

# ---------------------------- Schemas ----------------------------
from app.api.calendar.schemas import (
    GenerateCalendarRequest,
    CalendarOut,
    EditDayRequest,
    CalendarDayOut,
    DayInput,
    CalendarDayStateOut,
    RedistributeInput,
    RedistributeResult,
    ShellConfig,
    ShellCalendarOut,
)

# -------------------------- Service functions -------------------
from app.services.calendar_service import (
    generate_calendar,
    fetch_calendar,
    update_day,
    fetch_day_state,
    generate_shell_calendar,
)

# core budget redistribution algorithm
from app.engine.budget_redistributor import (
    redistribute_budget as redistribute_calendar_budget,
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
    return success_response({
        "calendar_id": data.calendar_id,
        "days": days,
    })


@router.get(
    "/day/{user_id}/{year}/{month}/{day}",
    response_model=CalendarDayOut,
)
async def get_day_view(user_id: str, year: int, month: int, day: int):
    calendar = fetch_calendar(user_id, year, month)
    if day not in calendar:
        raise HTTPException(status_code=404, detail="Day not found")
    return success_response(calendar[day])


@router.patch(
    "/day/{user_id}/{year}/{month}/{day}",
    response_model=CalendarDayOut,
)
async def edit_day(
    user_id: str,
    year: int,
    month: int,
    day: int,
    payload: EditDayRequest = Body(...),
):
    calendar = fetch_calendar(user_id, year, month)
    if day not in calendar:
        raise HTTPException(status_code=404, detail="Day not found")

    updated_day = update_day(calendar, day, payload.updates)
    return success_response(updated_day)


@router.post("/day_state", response_model=CalendarDayStateOut)
async def get_day_state(payload: DayInput):
    state = fetch_day_state(
        payload.user_id,
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
async def get_shell(payload: ShellConfig):
    calendar = generate_shell_calendar(payload.user_id, payload.dict())
    return success_response({"calendar": calendar})
