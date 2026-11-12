"""Budget lines the user names and sets themselves (F-11).

A user can tell MITA "Fuel is €200 a month" or "Cigarettes €200": a line with
their own label and an exact monthly amount. ChatGPT understands what the
words mean and which of MITA's own lines, if any, the user's line takes the
place of; MITA only does the money:

* the line is stored like any other plan line, under the key
  ``"my:" + label`` — as ``daily_plan.category`` for its amounts and as
  ``transactions.category`` for the expenses recorded against it — so the
  ledger, the rollover, the forecast and the calendar treat it like every
  other line, with no taxonomy to extend;
* its amount is the user's: the engine allocates only the money left after
  bills, savings and the user's lines (``generate_budget_from_answers``), and
  redistribution never moves money into or out of it (``realtime_rebalancer``);
* it is never a bill: it is not an expense category a payment can be saved
  under, so the bills reserve (R3) never holds it;
* bills + savings + the user's lines over the income is refused with every
  part named (``PlanDoesNotFit``) — nothing is scaled to make it fit.

Pure and dependency-free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, FrozenSet, Mapping, Optional

ZERO = Decimal("0.00")
USER_LINE_PREFIX = "my:"
# transactions.category is VARCHAR(50): the prefix plus the label must fit.
MAX_LABEL_CHARS = 40

# Every line ``budget_logic.generate_budget_from_answers`` allocates on its own
# (its ``discretionary_breakdown`` keys) — the lines a user's line may replace.
ENGINE_BUCKETS: FrozenSet[str] = frozenset(
    {
        "groceries",
        "dining out",
        "transport public",
        "transport gas",
        "entertainment events",
        "clothing",
        "hobbies",
        "flights",
        "insurance medical",
        "out of pocket medical",
        "coffee",
    }
)

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def is_user_line(category: Optional[str]) -> bool:
    """True for a budget line the user named and set (``"my:<label>"``)."""
    return bool(category) and str(category).startswith(USER_LINE_PREFIX)


def label_of(key: str) -> str:
    """The user's label of a line key."""
    return key[len(USER_LINE_PREFIX) :] if is_user_line(key) else key


def line_key(label: str) -> str:
    """``"my:" + label``, whitespace collapsed. A key passed back as a label
    (``"my:Fuel"``) is the same line. Raises ValueError for an empty label,
    one longer than ``MAX_LABEL_CHARS`` or one with control characters."""
    text = str(label or "")
    if _CONTROL.search(text):
        raise ValueError("a budget line name cannot contain control characters")
    text = " ".join(text.split())
    if text.lower().startswith(USER_LINE_PREFIX):
        text = " ".join(text[len(USER_LINE_PREFIX) :].split())
    if not text or len(text) > MAX_LABEL_CHARS:
        raise ValueError(
            f"a budget line name must have 1 to {MAX_LABEL_CHARS} characters"
        )
    return USER_LINE_PREFIX + text


@dataclass(frozen=True)
class PlanConflict:
    """The user's stated amounts do not fit their income. Nothing is saved."""

    income: Decimal
    bills: Decimal
    savings: Decimal
    user_set: Decimal

    @property
    def excess(self) -> Decimal:
        return self.bills + self.savings + self.user_set - self.income

    def details(self) -> Dict[str, str]:
        return {
            "stated_monthly_income": format(self.income, "f"),
            "bills_and_fixed_payments": format(self.bills, "f"),
            "savings_target": format(self.savings, "f"),
            "amounts_set_by_user": format(self.user_set, "f"),
            "exceeds_income_by": format(self.excess, "f"),
        }


class PlanDoesNotFit(ValueError):
    """Bills, savings and the user's lines add up to more than the income."""

    def __init__(self, conflict: PlanConflict) -> None:
        super().__init__(
            f"plan exceeds stated monthly income by {format(conflict.excess, 'f')}"
        )
        self.conflict = conflict


def check_fits(
    income: Decimal,
    bills: Decimal,
    savings: Decimal,
    user_set: Mapping[str, Decimal],
) -> Optional[PlanConflict]:
    """None when bills + savings + the user's amounts fit in the income."""
    conflict = PlanConflict(
        income=Decimal(income),
        bills=Decimal(bills),
        savings=Decimal(savings),
        user_set=sum((Decimal(a) for a in user_set.values()), ZERO),
    )
    return conflict if conflict.excess > ZERO else None
