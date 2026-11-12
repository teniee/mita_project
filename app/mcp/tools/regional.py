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
from app.mcp.schemas import (
    ReferenceInputsOut,
    RegionalCategory,
    RegionalContextOut,
    RegionalStatisticOut,
    SpendingReferenceOut,
)
from app.mcp.serializers import optional_money
from app.mcp.tools.common import READ_ONLY_DISCLAIMER, read_only_annotations, tool_meta
from app.regional import catalog
from app.regional import reference as reference_engine

DESCRIPTION = (
    "Official statistics for the country the user confirmed, from MITA's own "
    "regularly refreshed copy (no live lookup): how fast consumer prices are "
    "rising, overall and for food, housing, transport, clothing, recreation and "
    "restaurants (Eurostat HICP for EU, EFTA and candidate countries; OECD CPI "
    "elsewhere); how high the price level is compared with the EU average "
    "(Eurostat purchasing power parities); how households there divide their "
    "spending (Eurostat household budget survey); yearly inflation (World "
    "Bank); and the average price households pay per kWh of electricity and "
    "gas, taxes included (Eurostat, half-yearly); and, with household_spending, "
    "what households there spend a month on food, clothing, home energy and "
    "fuel on average, at recent prices (spending_references: national, low "
    "confidence, in the user's own currency only). MITA has no shop prices. Use "
    "when the user asks how prices or costs in their country "
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
    if row.unit_kind == "currency_amount":
        amount = format(value.normalize(), "f")
        per = " per kWh" if "per kWh" in (row.unit or "") else ""
        return f"{amount} {row.currency}{per}, taxes included, national average"
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
        currency=row.currency,
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


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def reference_out(item: reference_engine.Reference) -> SpendingReferenceOut:
    """One spending reference as the tools return it (get_regional_context
    and the preview's line recommendations)."""
    available = item.status == reference_engine.AVAILABLE
    return SpendingReferenceOut(
        category=item.category,
        category_label=item.label,
        status=item.status,
        reason=item.reason,
        reason_text=(
            reference_engine.REASONS.get(item.reason) if item.reason else None
        ),
        currency=item.currency if available else None,
        per_adult_monthly=optional_money(item.per_adult),
        household_size=item.household_size if available else None,
        household_monthly_low=optional_money(item.household_low),
        household_monthly_high=optional_money(item.household_high),
        households=(
            (
                "households_that_buy_it"
                if item.buying_percent is not None
                else "all_households"
            )
            if available
            else None
        ),
        survey_year=item.survey_year,
        price_year=item.price_year,
        inputs=(
            ReferenceInputsOut(
                yearly_per_adult=_plain(item.yearly_per_adult),
                share_per_mille=_plain(item.share_per_mille),
                price_factor=format(item.price_factor, "f"),
                buying_percent=(
                    _plain(item.buying_percent)
                    if item.buying_percent is not None
                    else None
                ),
            )
            if available
            else None
        ),
        confidence=item.confidence,
        quality_flags=list(item.quality_flags),
        source=(
            "Source: Eurostat (hbs_exp_t111, hbs_str_t211, prc_hicp_aind"
            + (
                ", hbs_exp_t123b"
                if item.category in reference_engine.BUYERS_ONLY
                else ""
            )
            + ")"
        ),
        method=reference_engine.METHOD,
        limitation=reference_engine.LIMITATION,
    )


def context_out(
    ctx,
    result: regional.RegionalContext,
    references: Optional[regional.SpendingReferences] = None,
    category: Optional[str] = None,
) -> RegionalContextOut:
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
    shown_references = [
        reference_out(item)
        for key, item in (references.references.items() if references else ())
        if category is None or key == category
    ]
    if any(r.status == reference_engine.AVAILABLE for r in shown_references):
        notes.append(
            "spending_references are national averages of every household "
            "carried to recent prices (low confidence): say what they are, give "
            "the survey and price years, and never present one as the user's "
            "cost, a city figure or a shop price."
        )
    return RegionalContextOut(
        status=result.status,
        country=result.country,
        country_name=country_name(result.country) if result.country else None,
        statistics=[statistic_out(s) for s in result.statistics],
        spending_references=(
            shown_references if result.status == regional.STATUS_AVAILABLE else []
        ),
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
                    "Narrow the answer: inflation, price_levels, "
                    "household_spending or prices (average electricity and gas "
                    "prices households pay). Omit for all."
                ),
                pattern=r"^(inflation|price_levels|household_spending|prices)$",
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
            references = (
                regional.spending_references(session, user_ctx)
                if topic in (None, "household_spending")
                and result.status == regional.STATUS_AVAILABLE
                else None
            )
            return context_out(user_ctx, result, references, category)

        return await runtime.execute(
            "get_regional_context",
            FINANCE_READ,
            body,
            ctx=ctx,
            intent="regional_context",
        )
