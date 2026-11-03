"""Input types shared by the write tools.

Bounds come from the same constants the API validates against
(``app/core/financial_constants.py``), so ChatGPT can never store a value the
mobile app would have refused. Money is accepted as a JSON number or a
decimal string and must have at most two decimal places — nothing is
rounded silently; NaN and Infinity are refused.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.financial_constants import FinancialConstants

# Every category a recorded expense may have: the API's own list, minus
# "income" — MITA's ledger holds expenses only, and an "income" row would be
# counted as spending by every total.
EXPENSE_CATEGORIES = tuple(
    sorted(FinancialConstants.VALID_TRANSACTION_CATEGORIES - {"income"})
)
ExpenseCategory = Literal[EXPENSE_CATEGORIES]  # type: ignore[valid-type]

CATEGORY_HELP = (
    "MITA category of the expense, exactly one of the listed values. Choose by what "
    "was bought, not only where: groceries for food and drink for home, gas for "
    "fuel, public_transport for tickets and passes, dining for restaurants and "
    "cafés, healthcare for medicine and doctors, clothing for clothes, shopping for "
    "household and other goods. If more than one could fit, ask the user; use "
    "'other' only when the user says it fits nothing else."
)


def money(
    description: str,
    *,
    minimum: Decimal = FinancialConstants.MIN_TRANSACTION_AMOUNT,
    maximum: Decimal = FinancialConstants.MAX_TRANSACTION_AMOUNT,
    allow_zero: bool = False,
):
    bounds = dict(ge=Decimal("0")) if allow_zero else dict(ge=minimum)
    return Annotated[
        Decimal,
        Field(
            description=description,
            le=maximum,
            decimal_places=2,
            allow_inf_nan=False,
            **bounds,
        ),
    ]


TransactionAmount = money(
    "Amount spent, in the user's MITA currency, as written by the user "
    "(at most two decimal places, e.g. 36.80)."
)

IdempotencyKey = Annotated[
    str,
    Field(
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
        description=(
            "A unique id you create for this request, e.g. a UUID. If the call fails "
            "or times out and you retry the SAME request, send the SAME key so MITA "
            "does not record it twice. Use a new key for every new request, even one "
            "with the same amount and merchant."
        ),
    ),
]

Merchant = Annotated[
    Optional[str],
    Field(
        min_length=1,
        max_length=200,
        description="Where the money was spent, exactly as the user named it (e.g. 'Lidl'). Omit if not stated.",
    ),
]

EntryMethod = Annotated[
    Literal["conversation", "receipt_image"],
    Field(
        description=(
            "How the expense reached you: 'receipt_image' when you read it from a "
            "receipt photo the user attached in this chat, otherwise 'conversation'. "
            "MITA does not receive or store the image."
        )
    ),
]


# --- how the user buys for a budget line (spending patterns) ------------------

WEEKDAY_NAMES = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

PATTERN_LINE_HELP = (
    "The budget line: one of the user's own lines by name or 'my:' id ('Groceries', "
    "'my:Fuel'), or one of MITA's lines by code or name ('groceries', 'transport "
    "public', 'Medical insurance')."
)
PATTERN_KIND_HELP = (
    "planned: the user buys on known days (groceries every Wednesday) — MITA "
    "splits the line's monthly amount over those real dates; flexible: no fixed "
    "purchase days (coffee, cigarettes, walks) — a monthly limit with daily "
    "guidance, never invented purchases; not_applicable: one of MITA's lines the "
    "user says they do not have (no medical insurance, no public transport) — "
    "MITA leaves it out of the plan. Only what the user said; never guess."
)
FREQUENCY_HELP = (
    "For planned: daily; weekly (one weekday) or weekdays (several, e.g. Mon-Fri) "
    "with weekdays; biweekly with next_date; times_per_month with times_per_month "
    "(weekdays optional); monthly (one day) or dates (several) with days_of_month."
)


class SpendingPatternIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line: Annotated[
        str, Field(min_length=1, max_length=64, description=PATTERN_LINE_HELP)
    ]
    kind: Annotated[
        Literal["planned", "flexible", "not_applicable"],
        Field(description=PATTERN_KIND_HELP),
    ]
    frequency: Annotated[
        Optional[
            Literal[
                "daily",
                "weekly",
                "weekdays",
                "biweekly",
                "times_per_month",
                "monthly",
                "dates",
            ]
        ],
        Field(description=FREQUENCY_HELP),
    ] = None
    weekdays: Annotated[
        Optional[List[Literal[WEEKDAY_NAMES]]],  # type: ignore[valid-type]
        Field(max_length=7, description="Days of the week the purchases happen."),
    ] = None
    days_of_month: Annotated[
        Optional[List[Annotated[int, Field(ge=1, le=31)]]],
        Field(
            max_length=31,
            description="Days of the month (1-31; 31 means the month's last day).",
        ),
    ] = None
    times_per_month: Annotated[
        Optional[int], Field(ge=1, le=31, description="For times_per_month.")
    ] = None
    next_date: Annotated[
        Optional[date],
        Field(description="For biweekly: the next purchase date (YYYY-MM-DD)."),
    ] = None
    typical_amount: Optional[
        money(
            "What one purchase usually costs, if the user said (shown with the plan; "
            "the line's monthly amount stays what it is)."
        )
    ] = None

    def pattern(self):
        from app.services.core.engine.spending_schedule import SpendingPattern

        return SpendingPattern(
            kind=self.kind,
            frequency=self.frequency,
            weekdays=tuple(WEEKDAY_NAMES.index(d) for d in (self.weekdays or ())),
            days_of_month=tuple(self.days_of_month or ()),
            times_per_month=self.times_per_month,
            anchor_date=self.next_date,
            typical_amount=self.typical_amount,
        )
