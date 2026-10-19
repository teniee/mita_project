"""Setup: what MITA knows about the user, and saving what they tell it."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field
from sqlalchemy import func, select

from app.db.models import McpUserProfile, Transaction, User
from app.mcp import analytics
from app.mcp.auth.scopes import FINANCE_WRITE, PROFILE_READ
from app.mcp.errors import ValidationError
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import load_user_context
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import KnownProfileOut, ProfileUpdateOut, SetupStatusOut
from app.mcp.serializers import optional_money
from app.mcp.tools.common import (
    NO_MONEY_MOVEMENT,
    READ_ONLY_DISCLAIMER,
    read_only_annotations,
    tool_meta,
    write_annotations,
)
from app.mcp.tools.inputs import money

STATUS_DESCRIPTION = (
    "Use at the start of any setup or budgeting request, and before asking the user "
    "for income, currency, timezone, household size or savings: reports what MITA "
    "already knows about this user (values included), which profile fields are "
    "still missing, whether a budget plan exists for the current month, and how "
    "many expenses, recurring expenses and savings goals are recorded. Ask only for "
    "missing_fields; never re-ask what is in 'known'. MITA keeps this across all "
    "future conversations. " + READ_ONLY_DISCLAIMER
)

UPDATE_DESCRIPTION = (
    "Save facts the user states about their finances to their MITA profile: monthly "
    "net income, currency (ISO code such as EUR), timezone (IANA name such as "
    "Europe/Sofia), household size, and how much they want to save each month. "
    "Example: 'I earn €2,500 net, there are two of us and I want to save €400' → "
    "monthly_net_income 2500, household_size 2, monthly_savings_target 400 (and "
    "currency EUR if not yet set). Send only fields the user actually stated; never "
    "guess or estimate a value. Overwrites the previous value of each field sent. "
    "Does not change an already saved budget. Before a first budget, ask whether the "
    "user has regular payments (rent, utilities, loans, subscriptions) and save them "
    "with add_recurring_expense; then preview_monthly_budget. The currency cannot be "
    "changed once expenses are recorded, because MITA does not convert amounts. "
    + NO_MONEY_MOVEMENT
)

OBLIGATIONS_FIRST = (
    "No regular payments are saved yet. Before building a first budget, ask once "
    "whether the user has any (rent, utilities, loans, subscriptions) and save each "
    "with add_recurring_expense; a budget previewed now assumes there are none."
)

PROFILE_FIELDS = (
    setup_queries.FIELD_INCOME,
    setup_queries.FIELD_CURRENCY,
    setup_queries.FIELD_TIMEZONE,
    setup_queries.FIELD_HOUSEHOLD,
    setup_queries.FIELD_SAVINGS,
)

MonthlyAmount = money(
    "Monthly amount in the user's currency, as stated (at most two decimals).",
    minimum=Decimal("0.01"),
    maximum=Decimal("10000000.00"),
)
SavingsAmount = money(
    "Amount the user wants to save each month (0 if they want no fixed savings).",
    maximum=Decimal("10000000.00"),
    allow_zero=True,
)


def known_profile(ctx) -> KnownProfileOut:
    return KnownProfileOut(
        monthly_net_income=(
            optional_money(ctx.stated_monthly_income)
            if setup_queries.income_set(ctx)
            else None
        ),
        currency=ctx.currency if setup_queries.currency_set(ctx) else None,
        timezone=ctx.timezone if setup_queries.timezone_set(ctx) else None,
        household_size=ctx.household_size,
        monthly_savings_target=optional_money(setup_queries.known_monthly_savings(ctx)),
    )


def setup_status_out(state: setup_queries.SetupState, ctx) -> SetupStatusOut:
    notes: List[str] = []
    if state.transaction_count == 0:
        notes.append("No expenses are recorded in MITA yet.")
    if not state.monthly_plan_exists:
        notes.append("No budget plan is saved for the current month yet.")
    if state.suggested_next_step == "ask_about_obligations":
        notes.append(OBLIGATIONS_FIRST)
    return SetupStatusOut(
        profile_complete=state.profile_complete,
        income_set=state.income_set,
        currency_set=state.currency_set,
        timezone_set=state.timezone_set,
        household_size_set=state.household_size_set,
        savings_preference_set=state.savings_preference_set,
        monthly_plan_exists=state.monthly_plan_exists,
        current_month=f"{ctx.today.year:04d}-{ctx.today.month:02d}",
        transaction_count=state.transaction_count,
        recurring_expense_count=state.recurring_expense_count,
        savings_goal_count=state.savings_goal_count,
        months_of_history=state.months_of_history,
        missing_fields=state.missing_fields,
        suggested_next_step=state.suggested_next_step,
        known=known_profile(ctx),
        notes=notes,
    )


def _differs(current, value) -> bool:
    if current is None:
        return True
    if isinstance(value, Decimal):
        return Decimal(str(current)) != value
    return current != value


def _valid_timezone(name: str) -> str:
    try:
        return ZoneInfo(name).key
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(
            "timezone must be an IANA timezone name such as 'Europe/Sofia'."
        ) from None


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_setup_status",
        title="Check MITA setup",
        description=STATUS_DESCRIPTION,
        annotations=read_only_annotations("Check MITA setup"),
        meta=tool_meta(
            PROFILE_READ, "Checking your MITA setup…", "Checked your MITA setup"
        ),
    )
    async def get_setup_status(
        ctx: Context,
    ) -> Annotated[CallToolResult, SetupStatusOut]:
        def body(session, user_ctx):
            state = setup_queries.setup_state(session, user_ctx)
            if not state.setup_complete:
                analytics.emit("onboarding_started")
            return setup_status_out(state, user_ctx)

        return await runtime.execute(
            "get_setup_status", PROFILE_READ, body, ctx=ctx, intent="onboarding"
        )

    @server.tool(
        name="update_financial_profile",
        title="Update MITA financial profile",
        description=UPDATE_DESCRIPTION,
        annotations=write_annotations(
            "Update MITA financial profile", destructive=True, idempotent=True
        ),
        meta=tool_meta(FINANCE_WRITE, "Saving your profile…", "Saved your profile"),
    )
    async def update_financial_profile(
        ctx: Context,
        monthly_net_income: Optional[MonthlyAmount] = None,
        currency: Annotated[
            Optional[str],
            Field(
                description="ISO 4217 currency code the user uses, e.g. 'EUR'.",
                pattern=r"^[A-Za-z]{3}$",
            ),
        ] = None,
        timezone: Annotated[
            Optional[str],
            Field(
                description="IANA timezone the user confirmed, e.g. 'Europe/Sofia'.",
                min_length=1,
                max_length=64,
            ),
        ] = None,
        household_size: Annotated[
            Optional[int],
            Field(
                description="Number of people the budget covers (1-20).", ge=1, le=20
            ),
        ] = None,
        monthly_savings_target: Optional[SavingsAmount] = None,
    ) -> Annotated[CallToolResult, ProfileUpdateOut]:
        async def body(session, user_ctx, call):
            sent = {
                setup_queries.FIELD_INCOME: monthly_net_income,
                setup_queries.FIELD_CURRENCY: currency.upper() if currency else None,
                setup_queries.FIELD_TIMEZONE: (
                    _valid_timezone(timezone) if timezone is not None else None
                ),
                setup_queries.FIELD_HOUSEHOLD: household_size,
                setup_queries.FIELD_SAVINGS: monthly_savings_target,
            }
            sent = {k: v for k, v in sent.items() if v is not None}
            if not sent:
                raise ValidationError(
                    "Send at least one field the user stated: monthly_net_income, "
                    "currency, timezone, household_size or monthly_savings_target."
                )

            def write(s) -> ProfileUpdateOut:
                user = s.get(User, user_ctx.user_id)
                profile = s.get(McpUserProfile, user_ctx.user_id)
                had_confirmed = bool(
                    profile
                    and (
                        profile.income_confirmed_at
                        or profile.currency_confirmed_at
                        or profile.timezone_confirmed_at
                        or profile.savings_confirmed_at
                        or profile.household_size is not None
                    )
                )
                before = setup_queries.setup_state(s, user_ctx)

                income = sent.get(
                    setup_queries.FIELD_INCOME,
                    user_ctx.stated_monthly_income if before.income_set else None,
                )
                savings = sent.get(setup_queries.FIELD_SAVINGS)
                if savings is not None and income is not None and savings > income:
                    raise ValidationError(
                        "monthly_savings_target cannot be more than the monthly net "
                        "income. Check both amounts with the user."
                    )
                new_currency = sent.get(setup_queries.FIELD_CURRENCY)
                if (
                    new_currency is not None
                    and new_currency != (user.currency or "").upper()
                    and s.scalar(
                        select(func.count(Transaction.id)).where(
                            Transaction.user_id == user_ctx.user_id,
                            Transaction.deleted_at.is_(None),
                        )
                    )
                ):
                    raise ValidationError(
                        "The currency cannot be changed after expenses have been "
                        "recorded: MITA does not convert existing amounts."
                    )

                now = call.now
                if profile is None:
                    profile = McpUserProfile(user_id=user_ctx.user_id)
                    s.add(profile)
                changed: List[str] = []

                def confirm(field: str, attr: str, column: str, value) -> None:
                    """Store a stated value on ``users`` and mark it confirmed.

                    Confirming a value equal to the column default (e.g. a
                    user who really is on UTC) is still a change: MITA did not
                    know it before."""
                    if _differs(getattr(user, column), value):
                        setattr(user, column, value)
                        changed.append(field)
                    elif getattr(profile, attr) is None:
                        changed.append(field)
                    setattr(profile, attr, getattr(profile, attr) or now)

                if setup_queries.FIELD_INCOME in sent:
                    confirm(
                        setup_queries.FIELD_INCOME,
                        "income_confirmed_at",
                        "monthly_income",
                        sent[setup_queries.FIELD_INCOME],
                    )
                if setup_queries.FIELD_SAVINGS in sent:
                    confirm(
                        setup_queries.FIELD_SAVINGS,
                        "savings_confirmed_at",
                        "savings_goal",
                        sent[setup_queries.FIELD_SAVINGS],
                    )
                if setup_queries.FIELD_CURRENCY in sent:
                    confirm(
                        setup_queries.FIELD_CURRENCY,
                        "currency_confirmed_at",
                        "currency",
                        new_currency,
                    )
                if setup_queries.FIELD_TIMEZONE in sent:
                    confirm(
                        setup_queries.FIELD_TIMEZONE,
                        "timezone_confirmed_at",
                        "timezone",
                        sent[setup_queries.FIELD_TIMEZONE],
                    )
                if setup_queries.FIELD_HOUSEHOLD in sent:
                    if profile.household_size != household_size:
                        profile.household_size = household_size
                        changed.append(setup_queries.FIELD_HOUSEHOLD)
                if changed:
                    user.updated_at = now
                    profile.updated_at = now
                s.flush()

                after_ctx = load_user_context(s, user_ctx.user_id, now=now)
                after = setup_queries.setup_state(s, after_ctx)
                s.commit()

                fields = sorted(changed)
                if fields:
                    analytics.emit(
                        (
                            "financial_profile_updated"
                            if had_confirmed
                            else "financial_profile_created"
                        ),
                        fields=fields,
                    )
                if after.setup_complete and not before.setup_complete:
                    analytics.emit("onboarding_completed")

                notes: List[str] = []
                if (
                    setup_queries.FIELD_INCOME in changed
                    or setup_queries.FIELD_SAVINGS in changed
                ) and after.monthly_plan_exists:
                    notes.append(
                        "The saved budget for this month is unchanged. Preview a new "
                        "budget (preview_monthly_budget) to plan with the new figures."
                    )
                if setup_queries.FIELD_TIMEZONE in changed:
                    notes.append("Days and months are now counted in the new timezone.")
                if after.suggested_next_step == "ask_about_obligations":
                    notes.append(OBLIGATIONS_FIRST)
                return ProfileUpdateOut(
                    status="updated" if changed else "unchanged",
                    updated_fields=[f for f in PROFILE_FIELDS if f in changed],
                    profile=known_profile(after_ctx),
                    profile_complete=after.profile_complete,
                    missing_fields=after.missing_fields,
                    suggested_next_step=after.suggested_next_step,
                    notes=notes,
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "update_financial_profile",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="profile_update",
        )
