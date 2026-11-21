"""Setup: what MITA knows about the user, and saving what they tell it.

Personalized onboarding (2.8, docs/chatgpt-app/personalization-2.8.md): the
status reports a derived onboarding stage and the region the user confirmed
(or the country of ChatGPT's approximate location, as a question to ask);
``update_financial_profile`` saves the optional facts the user states — their
country, how their income arrives — and their answers to setup questions
("no regular payments", "that is what I spend on", "skip it").
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.db.models import McpSetupAnswer, McpUserProfile, Transaction, User
from app.mcp import analytics, location_hint
from app.mcp.auth.scopes import FINANCE_WRITE, PROFILE_READ
from app.mcp.categories import label as category_label
from app.mcp.countries import country_code, country_name
from app.mcp.errors import ValidationError
from app.mcp.queries import setup as setup_queries
from app.mcp.queries.periods import load_user_context
from app.mcp.queries.spending import spending_profile
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import (
    CountrySuggestionOut,
    KnownProfileOut,
    OnboardingOut,
    ProfileUpdateOut,
    RegionOut,
    SetupStatusOut,
    SetupTopicOut,
    SpendingLineOut,
    SpendingProfileOut,
)
from app.mcp.serializers import optional_money
from app.mcp.tools.common import (
    NO_MONEY_MOVEMENT,
    READ_ONLY_DISCLAIMER,
    read_only_annotations,
    tool_meta,
    write_annotations,
)
from app.mcp.tools.inputs import money
from app.services.core.engine.spending_schedule import KIND_NOT_APPLICABLE, describe
from app.services.core.engine.user_budget_lines import is_user_line

STATUS_DESCRIPTION = (
    "Use at the start of any setup or budgeting request, and before asking the user "
    "for income, currency, timezone, household size or savings: reports what MITA "
    "already knows about this user (values included), which profile fields are "
    "still missing, whether a budget plan exists for the current month, and how "
    "many expenses, recurring expenses and savings goals are recorded, and how the "
    "user spends line by line (spending: stated purchase patterns, lines without "
    "one, MITA lines that do not apply). onboarding gives the setup stage, whether "
    "a budget would be preliminary or personalized, and the next questions to ask "
    "(a returning user is never asked again); region gives the country the user "
    "confirmed, or ChatGPT's approximate one as a question to ask. Ask only for "
    "missing_fields and onboarding.next_questions; never re-ask what is in "
    "'known' or 'spending'. MITA keeps this across all future conversations. "
    + READ_ONLY_DISCLAIMER
)

UPDATE_DESCRIPTION = (
    "Save facts the user states about their finances to their MITA profile: monthly "
    "net income, currency (ISO code such as EUR), timezone (IANA name such as "
    "Europe/Sofia), household size, and how much they want to save each month. "
    "Example: 'I earn €2,500 net, there are two of us and I want to save €400' → "
    "monthly_net_income 2500, household_size 2, monthly_savings_target 400 (and "
    "currency EUR if not yet set). Optional, only when the user says so: the "
    "country where they usually live and spend money (ISO code, after they "
    "confirm it — ChatGPT's approximate location alone is not enough), whether "
    "their income is regular or varies, how often and on which days of the "
    "month it arrives, the least they receive in a month when it varies, "
    "whether MITA may show regional statistics, and setup_answers: "
    "regular_payments none ('I have no regular payments'), everyday_spending "
    "described (the user has said what they regularly spend on — MITA then "
    "budgets only the lines they confirmed), or skipped for a question they "
    "prefer not to answer. Send only fields the user actually stated; never "
    "guess or estimate a value. Overwrites the previous value of each field sent. "
    "Does not change an already saved budget. Before a first budget, ask whether the "
    "user has regular payments (rent, utilities, loans, subscriptions) and save them "
    "with add_recurring_expense; then preview_monthly_budget. The currency cannot be "
    "changed once expenses are recorded, because MITA does not convert amounts; a "
    "new country changes neither the currency nor any saved budget. "
    + NO_MONEY_MOVEMENT
)

DESCRIBE_SPENDING = (
    "Before the first budget, ask once, in one short message, what the user "
    "spends on each month and how often they buy (their own amounts, e.g. fuel "
    "€200 a month, groceries every Wednesday, coffee whenever). The user can "
    "simply say it, by voice too. Save the patterns with save_spending_patterns "
    "and the amounts with preview_monthly_budget budget_lines. Optional: if they "
    "prefer to skip, MITA plans every line as a flexible budget."
)

OBLIGATIONS_FIRST = (
    "No regular payments are saved yet. Before building a first budget, ask once "
    "whether the user has any (rent, utilities, loans, subscriptions) and save each "
    "with add_recurring_expense; a budget previewed now assumes there are none. If "
    "they have none, save setup_answers regular_payments none."
)

PROFILE_FIELDS = (
    setup_queries.FIELD_INCOME,
    setup_queries.FIELD_CURRENCY,
    setup_queries.FIELD_TIMEZONE,
    setup_queries.FIELD_HOUSEHOLD,
    setup_queries.FIELD_SAVINGS,
)
FIELD_COUNTRY = "country"
FIELD_REGULARITY = "income_regularity"
FIELD_PAY_FREQUENCY = "pay_frequency"
FIELD_PAY_DAYS = "pay_days"
FIELD_MINIMUM = "minimum_monthly_income"
FIELD_REGIONAL = "regional_comparisons"
FIELD_ANSWERS = "setup_answers"
UPDATED_ORDER = PROFILE_FIELDS + (
    FIELD_COUNTRY,
    FIELD_REGULARITY,
    FIELD_PAY_FREQUENCY,
    FIELD_PAY_DAYS,
    FIELD_MINIMUM,
    FIELD_REGIONAL,
    FIELD_ANSWERS,
)

# Pay days make sense only for these frequencies (how many days each takes).
PAY_DAYS_FOR = {"monthly": 1, "twice_monthly": 2}

COUNTRY_SOURCE_STATED = "stated"
COUNTRY_SOURCE_HINT = "chatgpt_location_confirmed"
UNSTATED_COUNTRY = "ZZ"  # what ChatGPT sign-up stores: "not stated"

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
MinimumIncome = money(
    "For income that varies: the least the user says they receive in a month, "
    "as stated (0 is allowed).",
    maximum=Decimal("10000000.00"),
    allow_zero=True,
)

SetupTopicIn = Literal[
    "regular_payments",
    "everyday_spending",
    "irregular_expenses",
    "income_schedule",
    "region",
]


class SetupAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: Annotated[
        SetupTopicIn,
        Field(
            description=(
                "The setup question answered: regular_payments (rent, loans, "
                "bills, subscriptions), everyday_spending (what the user regularly "
                "spends on), irregular_expenses (annual bills, repairs, holidays, "
                "gifts), income_schedule, region."
            )
        ),
    ]
    answer: Annotated[
        Literal["none", "described", "skipped"],
        Field(
            description=(
                "none: the user said they have none (regular_payments, "
                "irregular_expenses). described: the user has told you what they "
                "regularly spend on and said that is it (everyday_spending), or "
                "described their irregular expenses (irregular_expenses) — save "
                "what they described with the other tools first. skipped: the "
                "user prefers not to answer; MITA will not ask again and the "
                "budget stays preliminary. Never answer for the user."
            )
        ),
    ]


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
        country=ctx.country,
        income_regularity=ctx.income_regularity,
        pay_frequency=ctx.pay_frequency,
        pay_days=list(ctx.pay_days),
        minimum_monthly_income=optional_money(ctx.minimum_monthly_income),
    )


def region_out(ctx) -> RegionOut:
    hint = location_hint.current_country()
    return RegionOut(
        country=ctx.country,
        country_name=country_name(ctx.country) if ctx.country else None,
        source=ctx.country_source,
        regional_context=ctx.regional_context_enabled,
        suggestion=(
            CountrySuggestionOut(
                country=hint,
                country_name=country_name(hint),
                source="chatgpt_approximate_location",
            )
            if hint is not None and ctx.country is None
            else None
        ),
    )


def onboarding_out(state: setup_queries.SetupState) -> OnboardingOut:
    next_questions, optional_questions = state.open_topics()
    return OnboardingOut(
        stage=state.stage,
        budget_readiness=state.budget_readiness,
        topics=[
            SetupTopicOut(
                topic=topic,
                state=state.topic_state(topic),
                needed_for_personalized_budget=topic
                in setup_queries.PERSONALIZED_REQUIRES,
            )
            for topic in setup_queries.QUESTION_ORDER
        ],
        next_questions=next_questions,
        optional_questions=optional_questions,
    )


def spending_out(profile) -> SpendingProfileOut:
    return SpendingProfileOut(
        lines=[
            SpendingLineOut(
                category=line.key,
                category_label=category_label(line.key),
                source="set_by_you" if is_user_line(line.key) else "calculated_by_mita",
                line_status=(
                    "user_confirmed"
                    if is_user_line(line.key)
                    or (
                        line.pattern is not None
                        and line.pattern.kind != KIND_NOT_APPLICABLE
                    )
                    else "mita_suggested"
                ),
                monthly_amount=optional_money(line.planned),
                pattern_stated=line.pattern is not None,
                spending_type=(
                    "planned"
                    if line.pattern is not None and line.pattern.kind == "planned"
                    else "flexible"
                ),
                pattern=describe(line.pattern),
            )
            for line in profile.lines
        ],
        lines_without_pattern=profile.missing,
        not_applicable=list(profile.not_applicable),
    )


def setup_status_out(
    state: setup_queries.SetupState, ctx, profile=None
) -> SetupStatusOut:
    notes: List[str] = []
    if state.transaction_count == 0:
        notes.append("No expenses are recorded in MITA yet.")
    if not state.monthly_plan_exists:
        notes.append("No budget plan is saved for the current month yet.")
    if state.suggested_next_step == "ask_about_obligations":
        notes.append(OBLIGATIONS_FIRST)
    if state.suggested_next_step == "describe_spending":
        notes.append(DESCRIBE_SPENDING)
    if profile is not None and profile.plan_exists and profile.missing:
        notes.append(
            f"MITA does not know when the user buys for {len(profile.missing)} "
            "line(s) of this month's plan (lines_without_pattern): they are "
            "flexible budgets with no purchase dates. Ask only if the user wants a "
            "day-by-day plan."
        )
    region = region_out(ctx)
    if region.suggestion is not None and state.stage != setup_queries.STAGE_ESTABLISHED:
        notes.append(
            "ChatGPT shared an approximate location in "
            f"{region.suggestion.country_name}. That is where the user is now, "
            "not necessarily where they live: ask whether they normally live and "
            f"spend money in {region.suggestion.country_name} or another country, "
            "and save only their answer (country), or setup_answers region skipped."
        )
    if state.stage == setup_queries.STAGE_ESTABLISHED:
        notes.append(
            "A returning user: do not repeat setup. optional_questions are only "
            "for when the user wants to update how MITA plans."
        )
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
        spending=(
            spending_out(profile)
            if profile is not None
            else SpendingProfileOut(
                lines=[], lines_without_pattern=[], not_applicable=[]
            )
        ),
        onboarding=onboarding_out(state),
        region=region,
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


def _valid_country(value: str) -> str:
    code = country_code(value)
    if code is None:
        raise ValidationError(
            "country must be the ISO 3166-1 alpha-2 code of the country the user "
            "named, e.g. 'BG' for Bulgaria."
        )
    return code


def _checked_answers(answers: Optional[List[SetupAnswerIn]]) -> Dict[str, str]:
    found: Dict[str, str] = {}
    for item in answers or ():
        if item.topic in found:
            raise ValidationError(
                f"setup_answers names {item.topic} twice; send one answer per topic."
            )
        if item.answer not in setup_queries.TOPIC_ANSWERS[item.topic]:
            allowed = ", ".join(sorted(setup_queries.TOPIC_ANSWERS[item.topic]))
            raise ValidationError(
                f"{item.topic} can be answered only with: {allowed}. A fact the "
                "user stated (a payment, an income schedule, a country) is saved "
                "with its own field or tool, not as an answer."
            )
        found[item.topic] = item.answer
    return found


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
            return setup_status_out(
                state, user_ctx, spending_profile(session, user_ctx)
            )

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
        country: Annotated[
            Optional[str],
            Field(
                description=(
                    "ISO 3166-1 alpha-2 code of the country where the user says "
                    "they usually live and spend money, e.g. 'BG'. Only after the "
                    "user confirmed it; never a city or address."
                ),
                pattern=r"^[A-Za-z]{2}$",
            ),
        ] = None,
        income_regularity: Annotated[
            Optional[Literal["regular", "variable"]],
            Field(
                description=(
                    "regular: about the same amount every month; variable: it "
                    "changes from month to month."
                )
            ),
        ] = None,
        pay_frequency: Annotated[
            Optional[
                Literal[
                    "monthly", "twice_monthly", "every_two_weeks", "weekly", "irregular"
                ]
            ],
            Field(description="How often the user's income arrives, as they said."),
        ] = None,
        pay_days: Annotated[
            Optional[List[Annotated[int, Field(ge=1, le=31)]]],
            Field(
                max_length=2,
                description=(
                    "Days of the month income usually arrives on (31 = the last "
                    "day): one for monthly, two for twice_monthly."
                ),
            ),
        ] = None,
        minimum_monthly_income: Optional[MinimumIncome] = None,
        regional_comparisons: Annotated[
            Optional[bool],
            Field(
                description=(
                    "Whether MITA may show statistics for the user's country "
                    "(false when the user turns them off)."
                )
            ),
        ] = None,
        setup_answers: Annotated[
            Optional[List[SetupAnswerIn]],
            Field(
                max_length=5,
                description=(
                    "Answers to setup questions that no other field records — "
                    "only what the user said."
                ),
            ),
        ] = None,
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
                FIELD_COUNTRY: _valid_country(country) if country is not None else None,
                FIELD_REGULARITY: income_regularity,
                FIELD_PAY_FREQUENCY: pay_frequency,
                FIELD_PAY_DAYS: (
                    sorted(set(pay_days)) if pay_days is not None else None
                ),
                FIELD_MINIMUM: minimum_monthly_income,
                FIELD_REGIONAL: regional_comparisons,
                FIELD_ANSWERS: _checked_answers(setup_answers) or None,
            }
            sent = {k: v for k, v in sent.items() if v is not None}
            if not sent:
                raise ValidationError(
                    "Send at least one field the user stated: monthly_net_income, "
                    "currency, timezone, household_size, monthly_savings_target, "
                    "country, income_regularity, pay_frequency, pay_days, "
                    "minimum_monthly_income, regional_comparisons or setup_answers."
                )
            answers_sent: Dict[str, str] = sent.get(FIELD_ANSWERS, {})
            if FIELD_COUNTRY in sent and setup_queries.TOPIC_REGION in answers_sent:
                raise ValidationError(
                    "Send either the user's country or region skipped, not both."
                )
            if (
                FIELD_REGULARITY in sent
                and setup_queries.TOPIC_INCOME_SCHEDULE in answers_sent
            ):
                raise ValidationError(
                    "Send either how the user's income arrives or income_schedule "
                    "skipped, not both."
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

                # The income schedule, as it will be after this call.
                regularity = sent.get(FIELD_REGULARITY, user_ctx.income_regularity)
                frequency = sent.get(FIELD_PAY_FREQUENCY, user_ctx.pay_frequency)
                minimum = sent.get(FIELD_MINIMUM)
                if minimum is not None:
                    if regularity != "variable":
                        raise ValidationError(
                            "minimum_monthly_income is only for income that varies: "
                            "send income_regularity variable with it."
                        )
                    if income is not None and minimum > income:
                        raise ValidationError(
                            "minimum_monthly_income cannot be more than the monthly "
                            "net income MITA plans on. Check both amounts with the "
                            "user."
                        )
                days = sent.get(FIELD_PAY_DAYS)
                if days is not None:
                    needed = PAY_DAYS_FOR.get(frequency or "")
                    if needed is None:
                        raise ValidationError(
                            "pay_days are days of the month: send them with "
                            "pay_frequency monthly (one day) or twice_monthly (two)."
                        )
                    if len(days) != needed:
                        raise ValidationError(
                            f"pay_frequency {frequency} takes {needed} pay day(s)."
                        )
                if (
                    answers_sent.get(setup_queries.TOPIC_REGULAR_PAYMENTS)
                    == setup_queries.ANSWER_NONE
                    and before.recurring_expense_count
                ):
                    raise ValidationError(
                        f"MITA has {before.recurring_expense_count} saved regular "
                        "payment(s) for this user, so 'none' does not fit. Check "
                        "with the user (get_recurring_expenses)."
                    )

                now = call.now
                if profile is None:
                    profile = McpUserProfile(
                        user_id=user_ctx.user_id,
                        pay_days=[],
                        regional_context_enabled=True,
                    )
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

                def keep(field: str, attr: str, value) -> None:
                    if getattr(profile, attr) != value:
                        setattr(profile, attr, value)
                        changed.append(field)

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

                old_country = user_ctx.country
                if FIELD_COUNTRY in sent:
                    code = sent[FIELD_COUNTRY]
                    source = (
                        COUNTRY_SOURCE_HINT
                        if location_hint.current_country() == code
                        else COUNTRY_SOURCE_STATED
                    )
                    if (
                        old_country != code
                        or profile.country_source != source
                        or (user.country or "").upper() != code
                    ):
                        changed.append(FIELD_COUNTRY)
                    user.country = code
                    if user.region and not str(user.region).upper().startswith(code):
                        # An app region of another country ("US-CA") would keep
                        # the engine on that country's rules.
                        user.region = None
                    profile.country_source = source
                    profile.country_confirmed_at = now  # last confirmation
                    _clear_answer(s, user_ctx.user_id, setup_queries.TOPIC_REGION)
                if FIELD_REGULARITY in sent:
                    keep(FIELD_REGULARITY, "income_regularity", regularity)
                    if (
                        regularity != "variable"
                        and profile.minimum_monthly_income is not None
                    ):
                        profile.minimum_monthly_income = None
                        changed.append(FIELD_MINIMUM)
                    _clear_answer(
                        s, user_ctx.user_id, setup_queries.TOPIC_INCOME_SCHEDULE
                    )
                if FIELD_PAY_FREQUENCY in sent:
                    keep(FIELD_PAY_FREQUENCY, "pay_frequency", frequency)
                    if (
                        days is None
                        and list(profile.pay_days or [])
                        and (PAY_DAYS_FOR.get(frequency) != len(profile.pay_days))
                    ):
                        profile.pay_days = []  # days no longer fit the frequency
                        changed.append(FIELD_PAY_DAYS)
                if days is not None:
                    keep(FIELD_PAY_DAYS, "pay_days", list(days))
                if minimum is not None:
                    if _differs(profile.minimum_monthly_income, minimum):
                        profile.minimum_monthly_income = minimum
                        changed.append(FIELD_MINIMUM)
                if FIELD_REGIONAL in sent:
                    keep(
                        FIELD_REGIONAL, "regional_context_enabled", regional_comparisons
                    )

                for topic, answer in answers_sent.items():
                    row = s.get(McpSetupAnswer, (user_ctx.user_id, topic))
                    if row is None:
                        s.add(
                            McpSetupAnswer(
                                user_id=user_ctx.user_id,
                                topic=topic,
                                answer=answer,
                                answered_at=now,
                            )
                        )
                    elif row.answer != answer:
                        row.answer = answer
                        row.answered_at = now
                    else:
                        continue
                    if FIELD_ANSWERS not in changed:
                        changed.append(FIELD_ANSWERS)
                    if (
                        topic == setup_queries.TOPIC_REGION
                        and answer == setup_queries.ANSWER_SKIPPED
                    ):
                        # The user prefers not to say: no country is used.
                        user.country = UNSTATED_COUNTRY
                        profile.country_source = None
                        profile.country_confirmed_at = None
                if changed:
                    user.updated_at = now
                    profile.updated_at = now
                s.flush()

                after_ctx = load_user_context(s, user_ctx.user_id, now=now)
                after = setup_queries.setup_state(s, after_ctx)
                s.commit()

                fields = [f for f in UPDATED_ORDER if f in changed]
                if fields:
                    analytics.emit(
                        (
                            "financial_profile_updated"
                            if had_confirmed
                            else "financial_profile_created"
                        ),
                        fields=sorted(fields),
                    )
                if after.setup_complete and not before.setup_complete:
                    analytics.emit("onboarding_completed")

                notes = _update_notes(changed, after, after_ctx, answers_sent)
                return ProfileUpdateOut(
                    status="updated" if changed else "unchanged",
                    updated_fields=fields,
                    profile=known_profile(after_ctx),
                    profile_complete=after.profile_complete,
                    missing_fields=after.missing_fields,
                    suggested_next_step=after.suggested_next_step,
                    onboarding=onboarding_out(after),
                    region=region_out(after_ctx),
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


def _clear_answer(s, user_id, topic: str) -> None:
    """A fact the user now stated replaces an earlier "skipped"."""
    row = s.get(McpSetupAnswer, (user_id, topic))
    if row is not None:
        s.delete(row)


def _update_notes(changed, after, after_ctx, answers_sent) -> List[str]:
    notes: List[str] = []
    if (
        setup_queries.FIELD_INCOME in changed or setup_queries.FIELD_SAVINGS in changed
    ) and after.monthly_plan_exists:
        notes.append(
            "The saved budget for this month is unchanged. Preview a new "
            "budget (preview_monthly_budget) to plan with the new figures."
        )
    if setup_queries.FIELD_TIMEZONE in changed:
        notes.append("Days and months are now counted in the new timezone.")
    if FIELD_COUNTRY in changed and after_ctx.country:
        notes.append(
            f"MITA now uses {country_name(after_ctx.country)} as the user's country. "
            "The currency, recorded expenses and saved budgets are unchanged."
        )
    if (
        answers_sent.get(setup_queries.TOPIC_REGION) == setup_queries.ANSWER_SKIPPED
        and FIELD_ANSWERS in changed
    ):
        notes.append(
            "No country is kept for the user; MITA will not ask again unless they "
            "bring it up."
        )
    if (
        answers_sent.get(setup_queries.TOPIC_EVERYDAY_SPENDING)
        == setup_queries.ANSWER_DESCRIBED
        and FIELD_ANSWERS in changed
    ):
        notes.append(
            "From the next preview, MITA budgets only the lines the user confirmed "
            "(their own lines and stated patterns); MITA's other lines are listed "
            "in not_included with what MITA would suggest. A saved plan changes "
            "only when the user previews and saves it."
        )
    skipped = sorted(
        topic
        for topic, answer in answers_sent.items()
        if answer == setup_queries.ANSWER_SKIPPED
        and topic != setup_queries.TOPIC_REGION
    )
    if skipped and FIELD_ANSWERS in changed:
        notes.append(
            "Skipped: "
            + ", ".join(skipped)
            + ". MITA will not ask again unless the user brings it up; a budget "
            "stays preliminary where it depends on them."
        )
    if (
        FIELD_ANSWERS in changed
        or FIELD_REGULARITY in changed
        or FIELD_MINIMUM in changed
    ) and after.monthly_plan_exists:
        notes.append(
            "The saved plan for this month is unchanged; preview it again "
            "(preview_monthly_budget) to show the effect and save only after a yes."
        )
    if after.suggested_next_step == "ask_about_obligations":
        notes.append(OBLIGATIONS_FIRST)
    return notes
