"""What MITA knows about how the user spends, line by line.

For conversational onboarding (``get_setup_status.spending``) and for saving
what the user says (``save_spending_patterns``). Only stated facts: a line
has a pattern when the user described it; otherwise MITA plans it as a
flexible budget and says the pattern is not known — it never guesses one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.category_priority import is_set_aside
from app.mcp.categories import PLAN_LABELS, label
from app.mcp.errors import ValidationError
from app.mcp.queries import budget_lines
from app.mcp.queries.periods import UserContext
from app.services.core.engine.spending_schedule import (
    KIND_NOT_APPLICABLE,
    SpendingPattern,
)
from app.services.core.engine.user_budget_lines import (
    ENGINE_BUCKETS,
    is_user_line,
    line_key,
)
from app.services.monthly_plan_service import month_base_plan
from app.services.obligation_lines import is_bill_key
from app.services.spending_patterns import stored_patterns

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class SpendingLine:
    key: str
    planned: Optional[Decimal]  # in the current month's saved plan, if any
    pattern: Optional[SpendingPattern]


@dataclass(frozen=True)
class SpendingProfile:
    month: Tuple[int, int]
    plan_exists: bool
    lines: List[SpendingLine]
    not_applicable: Tuple[str, ...]
    patterns: Dict[str, SpendingPattern]

    @property
    def missing(self) -> List[str]:
        """Spending lines of the plan with no stated pattern (flexible)."""
        return [line.key for line in self.lines if line.pattern is None]


def spending_profile(db: Session, ctx: UserContext) -> SpendingProfile:
    """The current month's spending lines (user lines and MITA's suggestions
    — not bills, not savings) with what the user said about each."""
    year, month = ctx.today.year, ctx.today.month
    patterns = stored_patterns(db, ctx.user_id)
    totals: Dict[str, Decimal] = {}
    for (_day, line), amount in month_base_plan(db, ctx.user_id, year, month).items():
        totals[line] = totals.get(line, ZERO) + amount
    spending = {
        line: amount
        for line, amount in totals.items()
        if amount > ZERO and not is_bill_key(line) and not is_set_aside(line)
    }
    keys = sorted(
        set(spending)
        | {
            k
            for k, p in patterns.items()
            if p.kind != KIND_NOT_APPLICABLE and k not in spending
        },
        key=lambda k: (not is_user_line(k), -(spending.get(k) or ZERO), k),
    )
    return SpendingProfile(
        month=(year, month),
        plan_exists=bool(totals),
        lines=[SpendingLine(k, spending.get(k), patterns.get(k)) for k in keys],
        not_applicable=tuple(
            sorted(k for k, p in patterns.items() if p.kind == KIND_NOT_APPLICABLE)
        ),
        patterns=patterns,
    )


def resolve_pattern_line(db: Session, ctx: UserContext, name: str) -> str:
    """The line a name refers to when the user describes how they buy:

    * one of the user's own lines (saved, or in this or next month's plan),
      by name or ``my:`` id;
    * otherwise one of MITA's lines, by code or display name ("Groceries");
    * otherwise a line of the user's own not created yet ("Cat food" — its
      amount comes with ``preview_monthly_budget(budget_lines=…)``).
    """
    text = " ".join(str(name or "").split())
    folded = text.casefold()
    own = set(budget_lines.stored_lines(db, ctx))
    year, month = ctx.today.year, ctx.today.month
    following = (year + 1, 1) if month == 12 else (year, month + 1)
    for y, m in ((year, month), following):
        own |= {
            c for (_d, c) in month_base_plan(db, ctx.user_id, y, m) if is_user_line(c)
        }
    own |= {k for k in stored_patterns(db, ctx.user_id) if is_user_line(k)}
    for key in own:
        if folded in (key.casefold(), label(key).casefold()):
            return key
    for code in ENGINE_BUCKETS:
        if folded in (code.casefold(), PLAN_LABELS.get(code, "").casefold()):
            return code
    try:
        return line_key(text)
    except ValueError:
        raise ValidationError(
            "Name the budget line as the user said it (1 to 40 characters), or "
            "one of MITA's lines."
        ) from None


def next_purchases(pattern: SpendingPattern, today: date, count: int = 4) -> List[date]:
    from app.services.core.engine.spending_schedule import next_dates

    return next_dates(pattern, today)[:count]
