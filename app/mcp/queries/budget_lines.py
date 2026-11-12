"""The user's own budget lines (F-11): what ChatGPT can refer to by name.

A line is ``"my:<label>"`` in the plan and the ledger
(``app/services/core/engine/user_budget_lines.py``); ``mcp_budget_lines``
keeps, per user, which of MITA's own lines each one replaces. Names are
matched case-insensitively against the user's existing lines, so "fuel" and
"Fuel" are one line and the first spelling the user chose is kept.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import McpBudgetLine
from app.mcp.errors import ValidationError
from app.mcp.queries.periods import UserContext
from app.services.core.engine.user_budget_lines import (
    ENGINE_BUCKETS,
    MAX_LABEL_CHARS,
    line_key,
)


def stored_lines(db: Session, ctx: UserContext) -> Dict[str, Tuple[str, ...]]:
    """``{line key: MITA lines it replaces}`` for every line the user saved."""
    rows = db.execute(
        select(McpBudgetLine.line_key, McpBudgetLine.replaces).where(
            McpBudgetLine.user_id == ctx.user_id
        )
    ).all()
    return {
        key: tuple(code for code in (replaces or []) if code in ENGINE_BUCKETS)
        for key, replaces in rows
    }


def key_for(name: str, known: Iterable[str]) -> str:
    """The line key for a name the user (or ChatGPT) gave: an existing line
    when one matches case-insensitively, otherwise a new ``"my:<name>"``."""
    try:
        key = line_key(name)
    except ValueError:
        raise ValidationError(
            f"A budget line needs a name of 1 to {MAX_LABEL_CHARS} characters, as "
            "the user said it (for example 'Fuel' or 'Cigarettes')."
        ) from None
    folded = key.casefold()
    for existing in known:
        if existing.casefold() == folded:
            return existing
    return key


def existing_key(db: Session, ctx: UserContext, name: str) -> Optional[str]:
    """The key of a line the user already has, or None."""
    lines = stored_lines(db, ctx)
    key = key_for(name, lines)
    return key if key in lines else None
