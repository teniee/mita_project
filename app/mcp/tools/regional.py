"""Regional statistics for the user's country (2.8, Milestone 2).

One read-only tool over MITA's own copy of official statistics
(``app/mcp/queries/regional.py``): never a live provider call, never an
input that locates the user (the country is the one they confirmed), never a
number that changes a budget. A statistic is context to compare with — the
user's own amounts always win (docs/chatgpt-app/personalization-2.8.md §7).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, List, Optional

from mcp.server.mcpserver import Context, MCPServer
from mcp_types import CallToolResult
from pydantic import Field

from app.mcp.auth.scopes import FINANCE_READ
from app.mcp.countries import country_name
from app.mcp.queries import regional
from app.mcp.runtime import McpRuntime
from app.mcp.schemas import RegionalCategory, RegionalContextOut, RegionalStatisticOut
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta
from app.regional import catalog

DESCRIPTION = (
    "Official statistics for the country the user confirmed, from MITA's own "
    "regularly refreshed copy (no live lookup): how fast consumer prices are "
    "rising, overall and for food, housing, transport, clothing, recreation and "
    "restaurants (Eurostat HICP for EU, EFTA and candidate countries; OECD CPI "
    "elsewhere); how high the price level is compared with the EU average "
    "(Eurostat purchasing power parities); how households there divide their "
    "spending (Eurostat household budget survey); and yearly inflation (World "
    "Bank). Use when the user asks how prices or costs in their country "
    "compare or change, or to put a budget line in context. Every figure has "
    "its source, period, unit and limitation, and stale figures say so: they "
    "are national averages to compare with — not prices at a shop, not city "
    "figures, not the user's own costs, and never a reason to change an "
    "amount the user set. Needs a country the user confirmed "
    "(update_financial_profile country). " + READ_ONLY_DISCLAIMER
)

NOTE_COMPARISON = (
    "These are national averages for comparison. They never change the user's "
    "budget: MITA's figures and the user's own amounts stay as they are."
)


def display(row) -> str:
    value = Decimal(str(row.value))
    if row.unit_kind == "percent_change":
        rounded = value.quantize(Decimal("0.1"), ROUND_HALF_UP)
        return f"{rounded} % over 12 months"
    if row.unit_kind == "price_level_index":
        return f"{value.quantize(Decimal('0.1'), ROUND_HALF_UP)} (EU average = 100)"
    if row.unit_kind == "per_mille":
        share = (value / 10).quantize(Decimal("0.1"), ROUND_HALF_UP)
        return f"{share} % of household spending"
    return format(value.normalize(), "f")


def _value(row) -> str:
    text = format(Decimal(str(row.value)).normalize(), "f")
    return text


def statistic_out(item: regional.Statistic) -> RegionalStatisticOut:
    row, spec = item.row, item.spec
    return RegionalStatisticOut(
        indicator=row.indicator,
        indicator_label=spec.label,
        category=item.category_key,
        category_label=row.category_label or "All items",
        value=_value(row),
        display=display(row),
        unit_kind=row.unit_kind,
        unit=row.unit,
        base_period=row.base_period,
        period=row.period,
        stale=item.stale,
        quality_flags=list(row.quality_flags or []),
        geographic_scope="country",
        source=f"{catalog.ATTRIBUTION[row.provider]} ({row.dataset})",
        provider=row.provider,
        dataset=row.dataset,
        source_url=row.source_url,
        published_at=row.published_at,
        retrieved_at=row.retrieved_at,
        license=row.license,
        limitation=spec.limitation,
    )


def context_out(ctx, result: regional.RegionalContext) -> RegionalContextOut:
    notes: List[str] = []
    if result.status == regional.STATUS_NO_COUNTRY:
        notes.append(
            "The user has not confirmed the country where they usually live and "
            "spend money. Ask (get_setup_status shows ChatGPT's approximate country "
            "as a suggestion) and save only their answer."
        )
    elif result.status == regional.STATUS_TURNED_OFF:
        notes.append(
            "The user turned regional statistics off; show none. They can turn "
            "them on again (update_financial_profile regional_comparisons true)."
        )
    elif result.status == regional.STATUS_UNAVAILABLE:
        notes.append(
            "MITA has no official statistics for this country yet. Say so; never "
            "estimate a figure."
        )
    else:
        notes.append(NOTE_COMPARISON)
        if any(s.stale for s in result.statistics):
            notes.append(
                "Some figures are stale (stale: true): give their period and do "
                "not call them current."
            )
    return RegionalContextOut(
        status=result.status,
        country=result.country,
        country_name=country_name(result.country) if result.country else None,
        statistics=[statistic_out(s) for s in result.statistics],
        notes=notes,
    )


def register(server: MCPServer, runtime: McpRuntime) -> None:
    @server.tool(
        name="get_regional_context",
        title="Get official statistics for my country",
        description=DESCRIPTION,
        annotations=read_only_annotations("Get official statistics for my country"),
        meta=tool_meta(
            FINANCE_READ,
            "Looking up official statistics…",
            "Looked up official statistics",
        ),
    )
    async def get_regional_context(
        ctx: Context,
        topic: Annotated[
            Optional[str],
            Field(
                description=(
                    "Narrow the answer: inflation, price_levels or "
                    "household_spending. Omit for all three."
                ),
                pattern=r"^(inflation|price_levels|household_spending)$",
            ),
        ] = None,
        category: Annotated[
            Optional[RegionalCategory],
            Field(description="Narrow to one spending category. Omit for all."),
        ] = None,
    ) -> Annotated[CallToolResult, RegionalContextOut]:
        def body(session, user_ctx):
            result = regional.regional_context(
                session, user_ctx, topic=topic, category=category
            )
            return context_out(user_ctx, result)

        return await runtime.execute(
            "get_regional_context",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="regional_context",
        )
