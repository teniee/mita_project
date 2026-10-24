"""MITA's financial calendar: a data tool and the tool that shows it.

OpenAI's decoupled pattern (docs: "Separate data processing from UI
rendering"): ``get_calendar_month`` returns the month as data and carries no
template; ``show_financial_calendar`` is the only tool bound to the calendar
component. One deliberate difference from the pattern's example: the render
tool does not take the figures as arguments. It recomputes them from the
account, so nothing the model writes can change a number on screen — the
backend stays the source of every figure.
"""

from __future__ import annotations

import calendar as calendar_module
from datetime import date
from decimal import Decimal
from typing import Annotated, List, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.errors import ValidationError
from app.mcp.queries import calendar as calendar_queries
from app.mcp.queries.periods import UserContext, resolve_month
from app.mcp.runtime import McpRuntime, ToolOutput
from app.mcp.schemas import CalendarMonthOut, CalendarViewOut
from app.mcp.serializers import (
    calendar_month_out,
    calendar_view_out,
    calendar_widget_payload,
    money,
)
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta
from app.mcp.ui import component_callable_meta, render_tool_meta

# Keys of the component-only ``_meta`` (namespaced; never shown to the model).
CALENDAR_META_KEY = "mita/calendar"
VIEW_META_KEY = "mita/view"

Year = Annotated[
    Optional[int],
    Field(
        description="Calendar year. Give with month; omit both for the current month.",
        ge=2000,
        le=2100,
    ),
]
Month = Annotated[
    Optional[int],
    Field(
        description="Calendar month 1-12. Give with year; omit both for the current month.",
        ge=1,
        le=12,
    ),
]

TERMS = (
    "Each date has its saved plan (planned: every line except money set aside; "
    "planned_everyday: its everyday part) and, once begun, recorded spending; a "
    "day's state compares everyday spending with that date's everyday plan (over, "
    "within, unplanned, quiet; future dates planned or free — never a forecast). "
    "The summary splits the plan into commitments (rent, mortgage, utilities, debt "
    "repayment, medical insurance, school fees, online courses and the categories of "
    "the user's saved regular payments), money set aside (savings, goals, "
    "investments — never spendable) and everyday spending, which add up to the "
    "plan; average_per_day is the safe daily figure of get_budget_forecast, an "
    "average for each remaining day — not a budget for a particular date. bills "
    "are the dates the user's saved payments fall on this month."
)

GET_DESCRIPTION = (
    "The user's month in MITA as data, date by date: each date's planned amount, "
    "recorded spending and state, the month's budget lines with their group, saved "
    "bills by date and a summary (plan, commitments, money set aside, everyday "
    "budget, spent, left, average a day, days left). Use it to answer questions "
    "about particular days ('which days was I over?', 'what is planned for "
    "Friday?') or before show_financial_calendar. "
    + TERMS
    + " Months follow the user's timezone; default is the current month; a month "
    "MITA has no plan for has plan_status 'not_generated' and no plan figures. "
    + READ_ONLY_DISCLAIMER
)

SHOW_DESCRIPTION = (
    "Show the user's interactive MITA financial calendar for a month inside the "
    "chat — use it when the user asks to see, show or open their calendar, month "
    "or daily plan ('show my financial calendar for November'). MITA fills every "
    "figure from the signed-in user's own account; the arguments only choose the "
    "month, an optional date to open on and an optional category filter, so never "
    "pass amounts. The user can pick dates, filter categories, move between months "
    "and save the month as an image. Afterwards, add at most a short comment: the "
    "figures are on screen. For the data without the calendar, use "
    "get_calendar_month. " + READ_ONLY_DISCLAIMER
)


def _month_name(year: int, month: int) -> str:
    return f"{calendar_module.month_name[month]} {year}"


def _target_month(
    ctx: UserContext, year: Optional[int], month: Optional[int], focus: Optional[date]
):
    if focus is not None and year is None and month is None:
        return resolve_month(ctx, focus.year, focus.month)
    y, m = resolve_month(ctx, year, month)
    if focus is not None and (focus.year, focus.month) != (y, m):
        raise ValidationError(
            "focus_date must be a date inside the month that is shown."
        )
    return y, m


def _match_category(cal, wanted: Optional[str]):
    """The budget line a free-text category names: its stored code, one of its
    codes or its display label (case-insensitive). None when nothing matches."""
    if not wanted:
        return None
    needle = wanted.strip().casefold()
    for line in cal.lines:
        names = {line.key.casefold(), line.label.casefold()} | {
            c.casefold() for c in line.codes
        }
        if needle in names:
            return line
    return None


def _shown_text(ctx: UserContext, cal, line) -> str:
    """The sentence the model reads (and a client without UI shows)."""
    name = _month_name(cal.year, cal.month)
    parts: List[str] = [f"MITA's calendar for {name} is on screen ({ctx.currency})."]
    if cal.plan_generated and cal.forecast is not None:
        left = cal.forecast.remaining_budget
        parts.append(
            f"Plan {money(cal.total_planned)}, spent {money(cal.total_spent)}, "
            f"left {money(left)}"
            + (
                f" ({money(cal.forecast.savings_set_aside)} of it set aside for savings)"
                if cal.forecast.savings_set_aside > Decimal("0")
                else ""
            )
            + "."
        )
        remaining = sum(1 for d in cal.days if d.kind == "future")
        if cal.position != "past" and remaining:
            parts.append(
                f"On average {money(cal.forecast.safe_daily_limit)} a day for the "
                f"{remaining} days left — each date also has its own plan."
            )
        over = sum(1 for d in cal.days if d.status == "over")
        if over:
            parts.append(
                f"{over} day{'s' if over != 1 else ''} went over the everyday plan."
            )
    else:
        parts.append(
            "MITA has no saved plan for this month, so the calendar shows recorded "
            f"spending only ({money(cal.total_spent)})."
        )
    upcoming = [b for b in cal.bills if b.occurrence.day > cal.today]
    if upcoming:
        first = upcoming[0].occurrence
        parts.append(
            f"Next saved bill: {money(first.amount)} on {first.day.isoformat()}."
        )
    if line is not None:
        parts.append(f"Filtered to {line.label}.")
    return " ".join(parts)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_calendar_month",
        title="Get the month's calendar data",
        description=GET_DESCRIPTION,
        annotations=read_only_annotations("Get the month's calendar data"),
        meta=tool_meta(
            FINANCE_READ,
            "Reading your month…",
            "Read your month",
            **component_callable_meta(),
        ),
    )
    async def get_calendar_month(
        ctx: Context, year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, CalendarMonthOut]:
        def body(session, user_ctx):
            y, m = resolve_month(user_ctx, year, month)
            cal = calendar_queries.calendar_month(session, user_ctx, y, m)
            return ToolOutput(
                model=calendar_month_out(user_ctx, cal),
                component_meta={
                    CALENDAR_META_KEY: calendar_widget_payload(user_ctx, cal)
                },
            )

        return await runtime.execute(
            "get_calendar_month",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="calendar_data",
        )

    @server.tool(
        name="show_financial_calendar",
        title="Show the financial calendar",
        description=SHOW_DESCRIPTION,
        annotations=read_only_annotations("Show the financial calendar"),
        meta=tool_meta(
            FINANCE_READ,
            "Opening your calendar…",
            "Opened your calendar",
            **render_tool_meta(),
        ),
    )
    async def show_financial_calendar(
        ctx: Context,
        year: Year = None,
        month: Month = None,
        focus_date: Annotated[
            Optional[date],
            Field(
                description=(
                    "Optional YYYY-MM-DD date to open the calendar on, inside the "
                    "month shown (alone, it also chooses the month)."
                )
            ),
        ] = None,
        category: Annotated[
            Optional[str],
            Field(
                max_length=64,
                description=(
                    "Optional budget line to filter the calendar to, as MITA names it "
                    "(category_label or code, e.g. 'Groceries')."
                ),
            ),
        ] = None,
    ) -> Annotated[CallToolResult, CalendarViewOut]:
        def body(session, user_ctx):
            y, m = _target_month(user_ctx, year, month, focus_date)
            cal = calendar_queries.calendar_month(session, user_ctx, y, m)
            line = _match_category(cal, category)
            notes = []
            if category and line is None:
                notes.append(
                    f"No budget line called '{category.strip()[:64]}' this month, so "
                    "the calendar shows every category."
                )
            view = {
                "focus_date": focus_date.isoformat() if focus_date else None,
                "category": line.key if line is not None else None,
            }
            return ToolOutput(
                model=calendar_view_out(
                    user_ctx,
                    cal,
                    focus_date=focus_date,
                    category=line.key if line is not None else None,
                    shown=_shown_text(user_ctx, cal, line),
                    notes=notes,
                ),
                text=_shown_text(user_ctx, cal, line),
                component_meta={
                    CALENDAR_META_KEY: calendar_widget_payload(user_ctx, cal),
                    VIEW_META_KEY: view,
                },
            )

        return await runtime.execute(
            "show_financial_calendar",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="calendar_view",
        )
