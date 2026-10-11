"""Input types shared by the write tools.

Bounds come from the same constants the API validates against
(``app/core/financial_constants.py``), so ChatGPT can never store a value the
mobile app would have refused. Money is accepted as a JSON number or a
decimal string and must have at most two decimal places — nothing is
rounded silently; NaN and Infinity are refused.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import Field

from app.core.financial_constants import FinancialConstants

# Every category a recorded expense may have: the API's own list, minus
# "income" — MITA's ledger holds expenses only, and an "income" row would be
# counted as spending by every total.
EXPENSE_CATEGORIES = tuple(
    sorted(FinancialConstants.VALID_TRANSACTION_CATEGORIES - {"income"})
)
ExpenseCategory = Literal[EXPENSE_CATEGORIES]  # type: ignore[valid-type]

CATEGORY_HELP = (
    "MITA category of the expense, exactly one of the listed values. Choose the "
    "one that plainly fits what the user said (groceries for a supermarket, gas "
    "for fuel, dining for restaurants and cafés). If more than one could fit, "
    "ask the user; use 'other' only when the user says it fits nothing else."
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
