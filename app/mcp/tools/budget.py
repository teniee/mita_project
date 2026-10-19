from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, List, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import analytics
from app.mcp.auth.scopes import FINANCE_READ, FINANCE_WRITE
from app.mcp.categories import label as category_label
from app.mcp.crypto import DraftClaims
from app.mcp.queries import budget_draft, ledger, plan
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import load_user_context, month_days, resolve_month
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import (
    AllocationOut,
    BudgetPreviewOut,
    BudgetSavedOut,
    BudgetStatusOut,
    DataSourceOut,
    FinancialSummaryOut,
    ForecastOut,
    HistoryUsedOut,
    ObligationOut,
)
from app.mcp.serializers import (
    budget_status_out,
    financial_summary_out,
    forecast_out,
    money,
    optional_money,
)
from app.mcp.tools.common import (
    NO_MONEY_MOVEMENT,
    READ_ONLY_DISCLAIMER,
    read_only_annotations,
    tool_meta,
    write_annotations,
)
from app.mcp.writes import budget as budget_writes

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

PLAN_NOTE = (
    "If MITA has not generated a plan for the month, plan_status is 'not_generated' and "
    "no budget figure is estimated."
)

SUMMARY_DESCRIPTION = (
    "One-month overview of the user's MITA finances: the monthly income the user "
    "entered (self-reported, may be null), the month's total budget plan, total "
    "recorded spending, what remains of the plan, the transaction count and the three "
    "largest spending categories. top_categories is not a full breakdown: spending "
    "outside those three is in other MITA categories, which get_spending_breakdown "
    "lists by name — do not report that remainder as a category of its own. Months "
    "follow the user's timezone; default is the current month. "
    + PLAN_NOTE
    + " "
    + READ_ONLY_DISCLAIMER
)

STATUS_DESCRIPTION = (
    "Budget vs. actual for one month, per category: planned amount, spent, remaining, "
    "percent used and a state (within_budget, over_budget, unplanned_spending, "
    "not_started), plus today's planned/spent/remaining for the current month. "
    "Allocations are MITA's persisted daily plan (including any automatic "
    "redistribution MITA already applied); spending is the user's recorded expenses. "
    "Each line has category_label, MITA's display name, and category_codes: expenses "
    "are shown on the line of the plan category they spend from (expenses recorded as "
    "'gas' with the 'transport gas' plan, as 'Fuel'). "
    + PLAN_NOTE
    + " "
    + READ_ONLY_DISCLAIMER
)

FORECAST_DESCRIPTION = (
    "Project where the user's budget lands at month end at the current pace, using "
    "MITA's forecast engine: daily pace so far, safe daily amount for the remaining "
    "days, projected month-end spend and balance, a status (on_track / warning / "
    "danger / no_data) and the categories spending 1.2× faster than planned. It is a "
    "linear projection, not a prediction of specific purchases, and does not include "
    "scheduled future expenses. " + PLAN_NOTE + " " + READ_ONLY_DISCLAIMER
)


PREVIEW_DESCRIPTION = (
    "Build a monthly budget for the user to REVIEW — nothing is saved. Use it for "
    "'Build my budget for this month' or to change an existing plan. MITA computes "
    "it from what the user stated (monthly net income, monthly savings target), "
    "their saved recurring obligations and MITA's deterministic allocation rules; "
    "recorded history only adds warnings. It returns fixed obligations, savings, "
    "category allocations, unallocated money, a daily average, assumptions, warnings "
    "and data sources. Show the figures to the user; if they confirm, call "
    "save_monthly_budget with the draft_token. Never present a preview as saved, "
    "and never recompute or edit the numbers yourself. Needs income and currency "
    "(see get_setup_status); for a first budget, ask about regular payments such as "
    "rent first — without them the preview is a default draft and says so. "
    + READ_ONLY_DISCLAIMER
)

NO_OBLIGATIONS_WARNING = (
    "No regular payments (rent, utilities, loans, subscriptions) are saved, so this "
    "is a default draft that assumes there are none. Ask the user about them, save "
    "them with add_recurring_expense and preview again before relying on it."
)

SAVE_DESCRIPTION = (
    "Save the monthly budget the user reviewed and confirmed, using the draft_token "
    "from preview_monthly_budget. Saves exactly that previewed plan and nothing "
    "else; if the user's income, savings target or obligations changed since the "
    "preview, it refuses and you must preview again. It replaces any existing plan "
    "for that month (existing_plan in the preview says so), keeps savings-goal "
    "reservations, and recalculates the month with the recorded expenses. Only call "
    "it after the user said yes to the shown plan. " + NO_MONEY_MOVEMENT
)


def preview_out(
    ctx, draft: budget_draft.BudgetDraft, token: str, expires: int
) -> BudgetPreviewOut:
    alloc = draft.allocation
    month_label = f"{draft.year:04d}-{draft.month:02d}"
    is_current = (draft.year, draft.month) == (ctx.today.year, ctx.today.month)
    assumptions = [
        budget_draft.region_note(ctx.region),
        "Category shares come from MITA's standard allocation rules for this "
        "income; they are a starting plan, not an assessment of the user.",
        "Each category is spread over the month's days by MITA's usual pattern "
        "(rent on the 1st, groceries on weekdays, dining on a few days).",
    ]
    if draft.obligations:
        assumptions.append("Repeating obligations count in full for the month.")
    if ctx.household_size is not None:
        assumptions.append(
            f"Household size ({ctx.household_size}) is recorded but MITA's "
            "allocation rules do not change with it."
        )
    if alloc.unallocated > 0:
        assumptions.append(
            f"{money(alloc.unallocated)} is left unallocated by MITA's rules and is "
            "free to spend."
        )
    warnings: List[str] = []
    if not draft.obligations:
        warnings.append(NO_OBLIGATIONS_WARNING)
    if draft.existing_plan:
        warnings.append(
            f"A plan for {month_label} is already saved; saving this one replaces it"
            + (", including days already past." if is_current else ".")
        )
    if draft.savings_requested > alloc.savings:
        warnings.append(
            f"The monthly savings target of {money(draft.savings_requested)} does not "
            f"fit after fixed obligations; MITA's rules set aside {money(alloc.savings)}."
        )
    history = draft.history
    spendable = draft.plan_total - alloc.savings + alloc.unallocated
    if (
        history.average_monthly_spending is not None
        and history.average_monthly_spending > spendable
    ):
        warnings.append(
            f"In the last {history.months_used} complete month(s) MITA recorded an "
            f"average of {money(history.average_monthly_spending)} a month in expenses, "
            f"more than the {money(spendable)} this plan leaves for spending."
        )
    for category, average in sorted(history.category_averages.items()):
        planned = alloc.allocations.get(category)
        if planned is not None and average > planned:
            warnings.append(
                f"{category_label(category)}: recorded average {money(average)} a "
                f"month vs {money(planned)} planned."
            )
    if not setup_queries.savings_set(ctx):
        warnings.append("No monthly savings target is set, so nothing is set aside.")

    income_source = (
        "stated by the user" if ctx.income_confirmed else "entered in the MITA app"
    )
    sources = [
        DataSourceOut(input="monthly_net_income", source=income_source),
        DataSourceOut(
            input="monthly_savings_target",
            source=(
                "stated by the user" if setup_queries.savings_set(ctx) else "not set"
            ),
        ),
        DataSourceOut(
            input="fixed_obligations",
            source=(
                f"{len(draft.obligations)} recurring or scheduled expense(s) the user "
                "saved in MITA"
                if draft.obligations
                else "none saved"
            ),
        ),
        DataSourceOut(
            input="category_allocations",
            source="MITA budget engine (deterministic rules)",
        ),
        DataSourceOut(
            input="history",
            source=(
                f"{history.months_used} complete month(s) of recorded expenses, "
                "used for warnings only"
                if history.months_used
                else "no complete month of recorded expenses yet"
            ),
        ),
    ]
    categories = sorted(alloc.discretionary.items(), key=lambda kv: (-kv[1], kv[0]))
    return BudgetPreviewOut(
        status="preview",
        month=month_label,
        currency=ctx.currency,
        existing_plan=draft.existing_plan,
        stated_monthly_income=money(draft.income),
        fixed_obligations=[
            ObligationOut(
                name=o.name,
                category=o.category,
                category_label=category_label(o.category),
                amount=money(o.amount),
                basis=o.basis,
            )
            for o in draft.obligations
        ],
        fixed_obligations_total=money(draft.fixed_total),
        savings_allocation=money(alloc.savings),
        category_allocations=[
            AllocationOut(
                category=category,
                category_label=category_label(category),
                amount=money(amount),
                layout=budget_draft.layout_of(category),
            )
            for category, amount in categories
        ],
        unallocated=money(alloc.unallocated),
        flexible_total=money(alloc.discretionary_total),
        plan_total=money(draft.plan_total),
        daily_flexible_average=money(draft.daily_flexible_average),
        days_in_month=draft.days_in_month,
        days_remaining=(
            (draft.days_in_month - ctx.today.day + 1) if is_current else None
        ),
        recurring_included=bool(draft.obligations),
        history=HistoryUsedOut(
            months_used=history.months_used,
            period_start=history.period_start,
            period_end=history.period_end,
            average_monthly_spending=optional_money(history.average_monthly_spending),
        ),
        assumptions=assumptions,
        warnings=warnings,
        data_sources=sources,
        draft_token=token,
        expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
    )


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_financial_summary",
        title="Get monthly financial summary",
        description=SUMMARY_DESCRIPTION,
        annotations=read_only_annotations("Get monthly financial summary"),
        meta=tool_meta(
            FINANCE_READ, "Summarizing your month…", "Summarized your month"
        ),
    )
    async def get_financial_summary(
        ctx: Context, year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, FinancialSummaryOut]:
        def body(session, user_ctx):
            y, m = resolve_month(user_ctx, year, month)
            # Totals only: the redistribution note belongs to get_budget_status.
            status = plan.budget_status(
                session, user_ctx, y, m, with_redistribution=False
            )
            first, last = month_days(y, m)
            totals = ledger.totals_by_category(session, user_ctx, first, last)
            return financial_summary_out(user_ctx, status, totals)

        return await runtime.execute(
            "get_financial_summary",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="monthly_summary",
        )

    @server.tool(
        name="get_budget_status",
        title="Get budget status",
        description=STATUS_DESCRIPTION,
        annotations=read_only_annotations("Get budget status"),
        meta=tool_meta(FINANCE_READ, "Checking your budget…", "Checked your budget"),
    )
    async def get_budget_status(
        ctx: Context, year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, BudgetStatusOut]:
        def body(session, user_ctx):
            y, m = resolve_month(user_ctx, year, month)
            return budget_status_out(
                user_ctx, plan.budget_status(session, user_ctx, y, m)
            )

        return await runtime.execute(
            "get_budget_status", FINANCE_READ, body, ctx=ctx, intent="budget_status"
        )

    @server.tool(
        name="get_budget_forecast",
        title="Get month-end budget forecast",
        description=FORECAST_DESCRIPTION,
        annotations=read_only_annotations("Get month-end budget forecast"),
        meta=tool_meta(FINANCE_READ, "Projecting your month…", "Projected your month"),
    )
    async def get_budget_forecast(
        ctx: Context, year: Year = None, month: Month = None
    ) -> Annotated[CallToolResult, ForecastOut]:
        def body(session, user_ctx):
            y, m = resolve_month(user_ctx, year, month)
            forecast = plan.month_forecast(session, user_ctx, y, m)
            first, last = month_days(y, m)
            others = ledger.other_currencies_in_range(session, user_ctx, first, last)
            return forecast_out(user_ctx, forecast, others)

        return await runtime.execute(
            "get_budget_forecast", FINANCE_READ, body, ctx=ctx, intent="forecast"
        )

    @server.tool(
        name="preview_monthly_budget",
        title="Preview a monthly budget",
        description=PREVIEW_DESCRIPTION,
        annotations=read_only_annotations("Preview a monthly budget"),
        meta=tool_meta(
            FINANCE_READ, "Building a budget preview…", "Built a budget preview"
        ),
    )
    async def preview_monthly_budget(
        ctx: Context,
        month: Annotated[
            Optional[str],
            Field(
                pattern=r"^\d{4}-\d{2}$",
                description="YYYY-MM: the current month (default) or the next one.",
            ),
        ] = None,
    ) -> Annotated[CallToolResult, BudgetPreviewOut]:
        def body(session, user_ctx):
            y, m = budget_draft.target_month(user_ctx, month)
            draft = budget_draft.build_draft(session, user_ctx, y, m)
            now = runtime.clock()
            expires = int((now + budget_draft.DRAFT_TTL).timestamp())
            token = runtime.data_keys.budget_draft(
                user_ctx.user_id, DraftClaims(y, m, expires, draft.digest)
            )
            analytics.emit(
                "budget_previewed",
                month_offset=(y * 12 + m)
                - (user_ctx.today.year * 12 + user_ctx.today.month),
                existing_plan=draft.existing_plan,
            )
            return preview_out(user_ctx, draft, token, expires)

        return await runtime.execute(
            "preview_monthly_budget",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="create_budget",
        )

    @server.tool(
        name="save_monthly_budget",
        title="Save the reviewed monthly budget",
        description=SAVE_DESCRIPTION,
        annotations=write_annotations(
            "Save the reviewed monthly budget", destructive=True, idempotent=True
        ),
        meta=tool_meta(FINANCE_WRITE, "Saving your budget…", "Saved your budget"),
    )
    async def save_monthly_budget(
        ctx: Context,
        draft_token: Annotated[
            str,
            Field(
                min_length=10,
                max_length=200,
                description="The draft_token from preview_monthly_budget, unchanged.",
            ),
        ],
    ) -> Annotated[CallToolResult, BudgetSavedOut]:
        async def body(session, user_ctx, call):
            def write(s) -> BudgetSavedOut:
                before = setup_queries.setup_state(s, user_ctx)
                draft = budget_writes.verified_draft(
                    s, user_ctx, runtime.data_keys, draft_token, call.now
                )
                outcome = budget_writes.save(s, user_ctx, draft)
                s.commit()
                offset = (draft.year * 12 + draft.month) - (
                    user_ctx.today.year * 12 + user_ctx.today.month
                )
                notes: List[str] = []
                if outcome.status == "replaced":
                    analytics.emit("budget_replaced", month_offset=offset)
                    if offset == 0:
                        notes.append(
                            "The new plan replaces the old one for the whole month, "
                            "including days already past."
                        )
                elif outcome.status == "saved":
                    analytics.emit("budget_saved", month_offset=offset)
                if outcome.redistributed:
                    notes.append(
                        "Expenses already recorded this month were applied to the "
                        "new plan; where a day was already over plan, MITA moved "
                        "money between categories (its automatic redistribution, as "
                        "in the app). The saved base plan is the one reviewed."
                    )
                after = setup_queries.setup_state(
                    s, load_user_context(s, user_ctx.user_id, now=call.now)
                )
                if after.setup_complete and not before.setup_complete:
                    analytics.emit("onboarding_completed")
                return BudgetSavedOut(
                    status=outcome.status,
                    month=f"{draft.year:04d}-{draft.month:02d}",
                    currency=user_ctx.currency,
                    plan_total=money(draft.plan_total),
                    category_count=len(draft.allocation.allocations),
                    notes=notes,
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "save_monthly_budget",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="save_budget",
        )
