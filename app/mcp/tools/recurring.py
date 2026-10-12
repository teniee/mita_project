from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import analytics, idempotency
from app.mcp.auth.scopes import FINANCE_READ, FINANCE_WRITE
from app.mcp.errors import ValidationError
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.recurring import recurring_expenses
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import RecurringCreatedOut, RecurringOut
from app.mcp.serializers import money, recurring_out
from app.mcp.tools.common import (
    NO_MONEY_MOVEMENT,
    READ_ONLY_DISCLAIMER,
    read_only_annotations,
    tool_meta,
    write_annotations,
)
from app.mcp.tools.inputs import CATEGORY_HELP, ExpenseCategory, IdempotencyKey
from app.mcp.tools.inputs import money as money_input
from app.mcp.writes import recurring as writes
from app.mcp.writes.transactions import clean_merchant, require_currency
from app.services.scheduled_expense_service import create_scheduled_expense

DESCRIPTION = (
    "List recurring and upcoming expenses the user has confirmed in MITA: repeating "
    "expenses they scheduled (with the repeat rule and next due date), one-time "
    "expenses scheduled for the next 60 days, and transactions from the last 180 days "
    "that the user marked as recurring, grouped by merchant or category. MITA does not "
    "detect subscriptions automatically, so nothing here is guessed from merchant "
    "names. " + READ_ONLY_DISCLAIMER
)

ADD_DESCRIPTION = (
    "Save a repeating obligation the user tells you about, e.g. 'My rent is €700 "
    "every month on the first' or 'Gym €25 every Monday'. MITA stores it in the "
    "user's account (shown in get_recurring_expenses and used in budget previews) "
    "with the next due date computed from what the user said: day_of_month for "
    "monthly, weekday for weekly, or first_date when the user gives the next due "
    "date. If the user did not say when it is due, ask — MITA never guesses a due "
    "date. Keep the name exactly as the user said it. This only records the "
    "obligation; " + NO_MONEY_MOVEMENT
)

RecurringAmount = money_input(
    "Amount due each time, in the user's MITA currency, as stated.",
    maximum=writes.MAX_SCHEDULED_AMOUNT,
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_recurring_expenses",
        title="Get recurring expenses",
        description=DESCRIPTION,
        annotations=read_only_annotations("Get recurring expenses"),
        meta=tool_meta(
            FINANCE_READ,
            "Reading your recurring expenses…",
            "Read your recurring expenses",
        ),
    )
    async def get_recurring_expenses(
        ctx: Context,
    ) -> Annotated[CallToolResult, RecurringOut]:
        return await runtime.execute(
            "get_recurring_expenses",
            FINANCE_READ,
            lambda session, user_ctx: recurring_out(
                user_ctx, recurring_expenses(session, user_ctx)
            ),
            ctx=ctx,
            intent="upcoming_expenses",
        )

    @server.tool(
        name="add_recurring_expense",
        title="Save a recurring expense in MITA",
        description=ADD_DESCRIPTION,
        annotations=write_annotations(
            "Save a recurring expense in MITA", destructive=False, idempotent=True
        ),
        meta=tool_meta(
            FINANCE_WRITE,
            "Saving the recurring expense…",
            "Saved the recurring expense",
        ),
    )
    async def add_recurring_expense(
        ctx: Context,
        name: Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description="What it is, exactly as the user named it, e.g. 'Rent' or 'Maple Apartments'.",
            ),
        ],
        amount: RecurringAmount,
        category: Annotated[ExpenseCategory, Field(description=CATEGORY_HELP)],
        recurrence: Annotated[
            Literal["monthly", "weekly"], Field(description="How often it repeats.")
        ],
        idempotency_key: IdempotencyKey,
        day_of_month: Annotated[
            Optional[int],
            Field(
                ge=1,
                le=31,
                description="For monthly: the day it is due (1-31). In shorter months MITA uses the last day.",
            ),
        ] = None,
        weekday: Annotated[
            Optional[Literal[writes.WEEKDAYS]],  # type: ignore[valid-type]
            Field(description="For weekly: the day of the week it is due."),
        ] = None,
        first_date: Annotated[
            Optional[date],
            Field(
                description="The next due date (YYYY-MM-DD) when the user gives one."
            ),
        ] = None,
    ) -> Annotated[CallToolResult, RecurringCreatedOut]:
        async def body(session, user_ctx, call):
            require_currency(user_ctx, setup_queries.currency_set(user_ctx))
            label = clean_merchant(name)
            if not label:
                raise ValidationError("name must not be empty.")
            due = writes.next_due_date(
                user_ctx,
                recurrence,
                day_of_month=day_of_month,
                weekday=weekday,
                first_date=first_date,
            )
            request = [label, str(amount), category, recurrence, str(due.day)]
            claim = await session.run_sync(
                lambda s: idempotency.claim(
                    s,
                    user_id=user_ctx.user_id,
                    operation="add_recurring_expense",
                    session_digest=call.session_digest,
                    key=idempotency_key,
                    request=request,
                    now=call.now,
                )
            )
            notes = []
            if claim.is_replay:
                analytics.mark_replayed()
                status = "already_created"
                notes.append(
                    "This recurring expense was already saved by an earlier identical "
                    "request; nothing new was written."
                )
            else:
                similar = await session.run_sync(
                    lambda s: writes.similar_pending(
                        s, user_ctx, category, amount, recurrence
                    )
                )
                expense = await create_scheduled_expense(
                    session,
                    user_id=user_ctx.user_id,
                    category=category,
                    amount=amount,
                    scheduled_date=due.day,
                    merchant=label,
                    recurrence=recurrence,
                )
                claim.complete([expense.id])
                await session.commit()
                status = "created"
                analytics.emit("recurring_expense_created", recurrence=recurrence)
                if similar:
                    notes.append(
                        f"MITA already had {len(similar)} other {recurrence} "
                        f"{category} expense(s) of the same amount; both are kept. "
                        "If this is a duplicate, tell the user."
                    )
            if due.clamped_from is not None:
                notes.append(
                    f"{due.day:%B} has no day {due.clamped_from}; the next due date "
                    f"is the last day of the month."
                )
            return RecurringCreatedOut(
                status=status,
                name=label,
                category=category,
                amount=money(amount),
                currency=user_ctx.currency,
                recurrence=recurrence,
                next_due_date=due.day,
                notes=notes,
            )

        return await runtime.execute_write(
            "add_recurring_expense",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="create_recurring",
        )
