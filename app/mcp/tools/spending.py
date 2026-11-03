"""How the user spends: saving what they say about each budget line.

Conversational onboarding (docs/chatgpt-app/behavioral-budget.md): ChatGPT
asks short questions — by voice or text — and MITA stores the answers as
validated patterns (``spending_patterns``), so a later conversation never
asks again. Saving a pattern never changes a saved plan: like a new income,
it applies when the user previews a month and saves it (``plans_to_review``
names the months that still use the earlier way).
"""

from __future__ import annotations

from typing import Annotated, List

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp import analytics
from app.mcp.auth.scopes import FINANCE_WRITE
from app.mcp.categories import label as category_label
from app.mcp.errors import ValidationError
from app.mcp.queries.spending import next_purchases, resolve_pattern_line
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import SpendingPatternSavedOut, SpendingPatternsOut
from app.mcp.serializers import optional_money
from app.mcp.tools.common import NO_MONEY_MOVEMENT, tool_meta, write_annotations
from app.mcp.tools.inputs import SpendingPatternIn
from app.services.core.engine.spending_schedule import (
    KIND_NOT_APPLICABLE,
    KIND_PLANNED,
    PatternError,
    dates_are_stated,
    describe,
    line_kinds_of,
)
from app.services.core.engine.user_budget_lines import ENGINE_BUCKETS, is_user_line
from app.services.monthly_plan_service import _month_rows
from app.services.spending_patterns import save_pattern, stored_patterns

MAX_PATTERNS = 40

DESCRIPTION = (
    "Save how the user buys for their budget lines, as they describe it — by "
    "voice or text — e.g. 'I shop for groceries every Wednesday', 'fuel every "
    "Friday', 'a big shop twice a month', 'coffee and cigarettes whenever', 'I "
    "have no medical insurance', 'I drive, no public transport'. For each line: "
    "planned (on known days: frequency with weekdays, days of the month or a "
    "number a month), flexible (no purchase dates: a monthly limit with daily "
    "guidance) or not_applicable (one of MITA's suggested lines the user does not "
    "have; MITA leaves it out). Send only what the user said; if the days are "
    "unclear, ask — never guess. MITA keeps it for every future month and "
    "conversation; get_setup_status shows what is known. Overwrites that line's "
    "earlier pattern. It does not change a saved monthly plan: to apply it, "
    "preview the month (preview_monthly_budget) and save it after the user "
    "confirms. Amounts are not set here: the user's own monthly amounts go in "
    "preview_monthly_budget budget_lines. " + NO_MONEY_MOVEMENT
)


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="save_spending_patterns",
        title="Save how the user spends",
        description=DESCRIPTION,
        annotations=write_annotations(
            "Save how the user spends", destructive=True, idempotent=True
        ),
        meta=tool_meta(
            FINANCE_WRITE,
            "Saving how you spend…",
            "Saved how you spend",
        ),
    )
    async def save_spending_patterns(
        ctx: Context,
        patterns: Annotated[
            List[SpendingPatternIn],
            Field(
                min_length=1,
                max_length=MAX_PATTERNS,
                description="One item per budget line the user described.",
            ),
        ],
    ) -> Annotated[CallToolResult, SpendingPatternsOut]:
        async def body(session, user_ctx, call):
            def write(s) -> SpendingPatternsOut:
                resolved = []
                seen = set()
                for item in patterns:
                    line = resolve_pattern_line(s, user_ctx, item.line)
                    if line in seen:
                        raise ValidationError(
                            f"{category_label(line)} is described twice; send one "
                            "pattern per line."
                        )
                    seen.add(line)
                    try:
                        pattern = item.pattern().validated()
                    except PatternError as error:
                        raise ValidationError(
                            f"{category_label(line)}: {error}"
                        ) from None
                    if (
                        pattern.kind == KIND_NOT_APPLICABLE
                        and line not in ENGINE_BUCKETS
                    ):
                        raise ValidationError(
                            f"{category_label(line)} is not one of MITA's suggested "
                            "lines, so it cannot be marked as not applying. To take "
                            "one of the user's own lines out of a plan, preview it "
                            "with remove_lines."
                        )
                    resolved.append((line, pattern))

                changed = [
                    line
                    for line, pattern in resolved
                    if save_pattern(s, user_ctx.user_id, line, pattern, call.now)
                ]
                s.flush()
                stored = stored_patterns(s, user_ctx.user_id)

                # Saved plans of this and next month laid out another way.
                year, month = user_ctx.today.year, user_ctx.today.month
                following = (year + 1, 1) if month == 12 else (year, month + 1)
                review = []
                for y, m in ((year, month), following):
                    rows = _month_rows(s, user_ctx.user_id, y, m)
                    budget = [r for r in rows if r.goal_id is None]
                    if not budget:
                        continue
                    kinds = line_kinds_of(budget)
                    lines = {r.category for r in budget}
                    # Any change to a line the plan holds, except a line that
                    # is flexible there and stays flexible.
                    if any(
                        line in lines
                        and not (
                            pattern.kind == "flexible" and kinds.get(line) == "flexible"
                        )
                        for line, pattern in resolved
                    ):
                        review.append(f"{y:04d}-{m:02d}")
                s.commit()
                if changed:
                    analytics.emit("spending_patterns_saved", item_count=len(changed))

                notes: List[str] = []
                if review:
                    notes.append(
                        "The saved plan for "
                        + " and ".join(review)
                        + " still uses the earlier way of spending. Preview that "
                        "month (preview_monthly_budget) to show the user the new "
                        "plan and save it if they confirm."
                    )
                if any(
                    p.kind == KIND_PLANNED and not dates_are_stated(p)
                    for _line, p in resolved
                ):
                    notes.append(
                        "For a number of purchases a month without days, MITA "
                        "spaces them evenly over the month; tell the user which "
                        "dates that gives (next_purchases)."
                    )
                if any(is_user_line(line) for line, _p in resolved):
                    notes.append(
                        "A line of the user's own gets its monthly amount from "
                        "preview_monthly_budget budget_lines."
                    )
                return SpendingPatternsOut(
                    status="saved" if changed else "unchanged",
                    saved=[
                        SpendingPatternSavedOut(
                            category=line,
                            category_label=category_label(line),
                            kind=stored[line].kind,
                            pattern=describe(stored[line]),
                            next_purchases=(
                                next_purchases(stored[line], user_ctx.today)
                                if stored[line].kind == KIND_PLANNED
                                else []
                            ),
                            purchase_dates_stated=(
                                dates_are_stated(stored[line])
                                if stored[line].kind == KIND_PLANNED
                                else None
                            ),
                            typical_amount=optional_money(stored[line].typical_amount),
                        )
                        for line, _pattern in resolved
                    ],
                    plans_to_review=review,
                    notes=notes,
                )

            return await session.run_sync(write)

        return await runtime.execute_write(
            "save_spending_patterns",
            FINANCE_WRITE,
            body,
            ctx=ctx,
            intent="spending_patterns",
        )
