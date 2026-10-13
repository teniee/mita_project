from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, List, Literal, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.core.financial_constants import FinancialConstants
from app.db.models import Goal
from app.mcp import analytics, idempotency
from app.mcp.auth.scopes import FINANCE_READ, FINANCE_WRITE
from app.mcp.errors import ValidationError
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.goals import list_goals
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import GoalCreatedOut, GoalsOut
from app.mcp.serializers import goals_out, money
from app.mcp.tools.common import (
    NO_MONEY_MOVEMENT,
    READ_ONLY_DISCLAIMER,
    read_only_annotations,
    tool_meta,
    write_annotations,
)
from app.mcp.tools.inputs import IdempotencyKey
from app.mcp.tools.inputs import money as money_input
from app.mcp.writes import goals as writes
from app.mcp.writes.transactions import require_currency

DESCRIPTION = (
    "List the user's MITA savings goals with target, amount saved, remaining amount, "
    "progress and target date. For active goals it adds a deterministic projection: "
    "whether saved + monthly contribution × months left reaches the target by the "
    "target date, the monthly amount that would be required, and any shortfall. Goals "
    "without a target date get no on-track verdict. By default only active goals are "
    "returned. " + READ_ONLY_DISCLAIMER
)

CREATE_DESCRIPTION = (
    "Create a savings goal the user asks for, e.g. 'I want to save €5,000 by June'. "
    "Use the user's own words as the title, unchanged (do not shorten, translate or "
    "rename). target_date is the date the user named; if they named only a month, "
    "use the last day of that month and say so. If they already saved part of it, "
    "pass already_saved. MITA returns the plain arithmetic of the monthly amount "
    "needed and reserves it in this month's budget plan when it can; it gives no "
    "advice. MITA does not move or hold the money: " + NO_MONEY_MOVEMENT
)

STATUS_SETS = {
    "active": ("active",),
    "all": ("active", "paused", "completed", "cancelled"),
    "completed": ("completed",),
}

GOAL_CATEGORIES = tuple(sorted(FinancialConstants.VALID_GOAL_CATEGORIES))

GoalAmount = money_input(
    "Goal target in the user's MITA currency, as stated.",
    minimum=FinancialConstants.MIN_GOAL_AMOUNT,
    maximum=FinancialConstants.MAX_GOAL_AMOUNT,
)
SavedAmount = money_input(
    "Amount the user says they have already saved towards it (default 0).",
    maximum=FinancialConstants.MAX_GOAL_AMOUNT,
    allow_zero=True,
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_goals",
        title="Get savings goals",
        description=DESCRIPTION,
        annotations=read_only_annotations("Get savings goals"),
        meta=tool_meta(FINANCE_READ, "Reading your goals…", "Read your goals"),
    )
    async def get_goals(
        ctx: Context,
        status: Annotated[
            Literal["active", "completed", "all"],
            Field(description="Which goals to return. Default: active."),
        ] = "active",
    ) -> Annotated[CallToolResult, GoalsOut]:
        def body(session, user_ctx):
            return goals_out(
                user_ctx, list_goals(session, user_ctx, STATUS_SETS[status])
            )

        return await runtime.execute(
            "get_goals", FINANCE_READ, body, ctx=ctx, intent="goal_progress"
        )

    @server.tool(
        name="create_savings_goal",
        title="Create a MITA savings goal",
        description=CREATE_DESCRIPTION,
        annotations=write_annotations(
            "Create a MITA savings goal", destructive=False, idempotent=True
        ),
        meta=tool_meta(FINANCE_WRITE, "Creating your goal…", "Created your goal"),
    )
    async def create_savings_goal(
        ctx: Context,
        title: Annotated[
            str,
            Field(
                min_length=1,
                max_length=200,
                description="The goal's name exactly as the user said it.",
            ),
        ],
        target_amount: GoalAmount,
        idempotency_key: IdempotencyKey,
        target_date: Annotated[
            Optional[date],
            Field(
                description="Date the user wants to reach it by (YYYY-MM-DD), if any."
            ),
        ] = None,
        already_saved: Optional[SavedAmount] = None,
        category: Annotated[
            Literal[GOAL_CATEGORIES],  # type: ignore[valid-type]
            Field(description="Kind of goal; 'savings' when the user did not say."),
        ] = "savings",
    ) -> Annotated[CallToolResult, GoalCreatedOut]:
        async def body(session, user_ctx, call):
            require_currency(user_ctx, setup_queries.currency_set(user_ctx))
            text = title.strip()
            if not text or any(ord(ch) < 32 for ch in text):
                raise ValidationError(
                    "title must be the user's words, without control characters."
                )
            if target_date is not None and target_date <= user_ctx.today:
                raise ValidationError("target_date must be after today.")
            saved = already_saved if already_saved is not None else Decimal("0.00")
            if saved > target_amount:
                raise ValidationError(
                    "already_saved cannot be more than target_amount."
                )
            request = [
                text,
                str(target_amount),
                str(target_date or ""),
                str(saved),
                category,
            ]
            claim = await session.run_sync(
                lambda s: idempotency.claim(
                    s,
                    user_id=user_ctx.user_id,
                    operation="create_savings_goal",
                    session_digest=call.session_digest,
                    key=idempotency_key,
                    request=request,
                    now=call.now,
                )
            )
            notes: List[str] = []
            if claim.is_replay:
                analytics.mark_replayed()
                goal = await session.get(Goal, claim.replay_ids[0])
                status = "already_created"
                reserved = await writes.has_reservation(session, goal)
                notes.append(
                    "This goal was already created by an earlier identical request; "
                    "nothing new was written."
                )
            else:
                goal = writes.build_goal(
                    user_ctx,
                    title=text,
                    target_amount=target_amount,
                    saved_amount=saved,
                    target_date=target_date,
                    category=category,
                )
                session.add(goal)
                await session.flush()
                reserved = (
                    await writes.reserve_in_plan(session, goal, user_ctx)
                    if target_date is not None
                    else False
                )
                claim.complete([goal.id])
                await session.commit()
                status = "created"
                analytics.emit(
                    "savings_goal_created", has_target_date=target_date is not None
                )
                if target_date is not None and not reserved:
                    notes.append(
                        "The goal is saved, but MITA could not set aside its daily "
                        "amounts in this month's budget plan (a known limitation when "
                        "another dated goal already reserves them)."
                    )
            required = (
                writes.required_monthly(goal, user_ctx.today)
                if goal.target_date is not None
                else None
            )
            target_savings = setup_queries.known_monthly_savings(user_ctx)
            if required is not None and target_savings is not None:
                if required > target_savings:
                    notes.append(
                        f"Arithmetic: reaching it by {goal.target_date:%Y-%m-%d} needs "
                        f"{money(required)} a month; the monthly savings target the "
                        f"user set is {money(target_savings)}."
                    )
            progress = Decimal(str(goal.progress or 0)).quantize(Decimal("0.1"))
            return GoalCreatedOut(
                status=status,
                title=goal.title,
                category=goal.category or "savings",
                currency=user_ctx.currency,
                target_amount=money(Decimal(str(goal.target_amount))),
                saved_amount=money(Decimal(str(goal.saved_amount or 0))),
                progress_percent=str(progress),
                target_date=goal.target_date,
                required_monthly_contribution=(
                    money(required) if required is not None else None
                ),
                reserved_in_budget_plan=reserved,
                notes=notes,
            )

        return await runtime.execute_write(
            "create_savings_goal",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="create_goal",
        )
