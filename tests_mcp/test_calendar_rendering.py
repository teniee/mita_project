"""The calendar component, rendered: what a date's cell actually shows.

Two briefs, one rule. 2026-11-11 (test L): with a category filter the v3
component drew a flexible budget's stored daily share on every date
(Restaurants 3.33 / 3.34, Groceries 10.67, Car maintenance 6.67), and the
exported image did the same for every date ahead. 2026-11-13 (MCP 2.11.0,
component v5): the fix of 2.10.0 left the calendar almost empty for
flexible spending, and a phone drew a €1.50 coffee as "2". So a date shows
two layers, never merged (docs/chatgpt-app/calendar-guidance-layer.md):

* activity — what was recorded on it and what is scheduled for it (planned
  purchases, bills): the cell's amount, every cent of it;
* the average left per day — on today and the dates ahead: MITA's
  ``summary.flexible_per_day`` for all categories, a flexible budget's own
  ``left_per_day`` under its filter. A pill of its own marked "≈", in words
  in the date's label; never the amount, never in a total; said to be an
  average, never a recommendation (owner brief 2026-11-16: MITA has no
  method that personalizes a daily figure); the user can hide it.

``test_flexible_envelopes_calendar.py`` and ``test_calendar_guidance_layer.py``
prove what MITA sends; this proves what the component DRAWS from it. The
real component runs in an iframe sandboxed with ``allow-scripts`` only under
the MCP Apps restrictive CSP — the host page of
``scripts/mcp/calendar_widget_review.py`` — and is fed real tool results:
every ``tools/call`` it makes goes to MITA's real tools, in process, on the
test's own PostgreSQL transaction. Phone (WebKit, 390 and 320 px) and desktop
(Chromium), light and dark; the exported image is checked through what it
draws (every ``fillText``), not by pixels.

Dependencies: ``requirements-mcp-render.txt`` (playwright 1.50.0, Pillow) and
``playwright install chromium webkit``. MCP CI installs them and sets
``MITA_RENDERING_REQUIRED=1``, which turns a missing dependency into a
failure instead of a skip. ``MITA_CALENDAR_SHOTS`` = a directory keeps
screenshots (``docs/chatgpt-app/review/calendar-v5/``); ``MITA_AXE`` = an
``axe.min.js`` (axe-core 4.10) adds WCAG 2.2 AA checks; ``MITA_SETTLE_SCALE``
stretches the harness's fixed waits on a slow machine.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import os
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pytest

if os.environ.get("MITA_RENDERING_REQUIRED") != "1":
    pytest.importorskip(
        "playwright.sync_api",
        reason="needs requirements-mcp-render.txt (+ `playwright install chromium webkit`)",
    )
    pytest.importorskip("PIL", reason="needs requirements-mcp-render.txt (Pillow)")

from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from app.mcp.ui import calendar_html  # noqa: E402
from tests_mcp.test_flexible_envelopes_calendar import (  # noqa: E402
    CAR,
    COFFEE,
    COFFEE_DAILY,
    FUN,
    GROCERIES,
    RESTAURANTS,
    call,
    key,
    noon,
    november,
)

D = Decimal
ROOT = Path(__file__).resolve().parents[1]
SHOTS = os.environ.get("MITA_CALENDAR_SHOTS")
AXE = os.environ.get("MITA_AXE")
AXE_RUN = """async () => {
  const r = await axe.run(document, {runOnly: {type: 'tag',
    values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']}});
  return r.violations.map(v => v.id + ' (' + v.impact + '): ' +
    v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(' | '));
}"""
# What 2.9.0 drew on the dates of the four flexible budgets.
DAILY_SHARE = re.compile(r"\b(10\.6[67]|6\.6[67]|3\.3[34])\b")
PHONE = {"width": 390, "height": 844}
NARROW = {"width": 320, "height": 640}
DESKTOP = {"width": 1280, "height": 900}
GUIDE_INK = "#3d44b0"  # the image's guide colour (canvas reports lowercase hex)
SCHEDULED_INK = "#55544f"  # the image's colour for what is scheduled ahead
ROUNDED_NOTE = "Amounts of 100 or more are shown without cents"
# How a date's label says the average left per day (never as advice).
ALL_LABEL = (
    "average left per day for your flexible budgets about €{v}, what is left "
    "divided by the days left, not a plan or a recommendation"
)


def _harness():
    spec = importlib.util.spec_from_file_location(
        "calendar_widget_review", ROOT / "scripts" / "mcp" / "calendar_widget_review.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InProcessBridge:
    """What the harness's host page needs from an MCP session: ``call(tool,
    args)`` returning the ``tools/call`` result as JSON. The browser runs in
    a worker thread; each call runs MITA's real tool on the test's event
    loop, one at a time (the test's database connection is one session)."""

    def __init__(self, loop, m, token: str):
        self.loop, self.m, self.token = loop, m, token
        self.lock = asyncio.Lock()
        self.calls: List[str] = []

    async def _call(self, tool: str, arguments: dict):
        async with self.lock:
            return await self.m.call(self.token, tool, arguments)

    def call(self, tool: str, args: Optional[dict] = None) -> dict:
        self.calls.append(tool)
        result = asyncio.run_coroutine_threadsafe(
            self._call(tool, args or {}), self.loop
        ).result(60)
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)


CELLS = """() => [...document.querySelectorAll('.grid .cell[data-date]')].map(c => {
  const amt = c.querySelector('.amt');
  const v = c.querySelector('.amt .v');
  const g = c.querySelector('.guide');
  return {day: Number(c.dataset.date.slice(-2)), text: amt ? amt.textContent.trim() : '',
          exact: v ? v.dataset.amount : null, label: c.getAttribute('aria-label'),
          over: c.classList.contains('over'), meter: !!c.querySelector('.meter'),
          guide: g ? g.dataset.guide : null, guideText: g ? g.textContent.trim() : null};
})"""
MINI = """() => [...document.querySelectorAll('.mini .mcell:not(.blank)')].map(c => {
  const a = c.querySelector('.ma'); const g = c.querySelector('.guide');
  return {amount: a ? a.textContent.trim() : '', guide: g ? g.textContent.trim() : '',
          value: g ? g.dataset.guide : null};
})"""
# A guide inside an amount, or an amount inside a guide: the layers merged.
MERGED = """() => document.querySelectorAll(
  '.guide [data-amount], .guide .v, .amt .guide, .ma .guide, .v .guide').length"""
# Every text the exported image draws, with where and in which colour.
RECORD_FILLS = """() => {
  window.__fills = [];
  const fill = CanvasRenderingContext2D.prototype.fillText;
  CanvasRenderingContext2D.prototype.fillText = function (t, x, y) {
    window.__fills.push({t: String(t), x: x, y: y, ink: String(this.fillStyle)});
    return fill.apply(this, arguments);
  };
}"""


def cells(host) -> Dict[int, dict]:
    return {c["day"]: c for c in host.frame.evaluate(CELLS)}


def shown(host) -> Dict[int, str]:
    """``{day: the exact amount in its cell}`` for the cells that hold one."""
    return {
        day: c["exact"] for day, c in cells(host).items() if c["text"] and c["exact"]
    }


def guides(host) -> Dict[int, str]:
    """``{day: MITA's guide figure}`` for the cells that show the average left per day."""
    return {day: c["guide"] for day, c in cells(host).items() if c["guide"] is not None}


def from_day(first: int, value: str, last: int = 30) -> Dict[int, str]:
    return {day: value for day in range(first, last + 1)}


def text_of(host, selector: str) -> str:
    return host.frame.evaluate(
        "(s) => { const n = document.querySelector(s); return n ? n.innerText : ''; }",
        selector,
    )


def page_text(host) -> str:
    return host.frame.evaluate("() => document.body.innerText")


def set_filter(host, label: Optional[str]) -> None:
    if label is None:
        host.frame.click("#filter-all")
    else:
        more = host.frame.query_selector("#filter-more[aria-expanded=false]")
        if more is not None:
            more.click()
        host.frame.click(f'.filters .fchip:has-text("{label}")')
    host.settle(250)


def switch_guide(host, on: bool) -> None:
    toggle = host.frame.query_selector("#guide-toggle")
    assert toggle is not None, "no daily average switch"
    if (toggle.get_attribute("aria-checked") == "true") != on:
        toggle.click()
        host.settle(250)
    assert host.frame.get_attribute("#guide-toggle", "aria-checked") == (
        "true" if on else "false"
    )


def accessible(host, where: str) -> None:
    """No WCAG 2.2 AA violation in what is on screen (when MITA_AXE is set)."""
    if not AXE:
        return
    host.frame.add_script_tag(content=Path(AXE).read_text())
    violations = host.frame.evaluate(AXE_RUN)
    assert not violations, (where, violations)


def wait_title(host, month: str) -> None:
    """Until the component shows that month (the frame's CSP forbids the
    string evaluation ``wait_for_function`` uses, so poll)."""
    for _ in range(100):
        title = host.frame.evaluate(
            "() => (document.querySelector('.fhead .title') || {}).textContent || ''"
        )
        if month in title:
            return
        host.page.wait_for_timeout(100)
    raise AssertionError(f"the calendar never showed {month}")


def keep(host, name: str, *, full: bool = False) -> None:
    if not SHOTS:
        return
    out = Path(SHOTS)
    out.mkdir(parents=True, exist_ok=True)
    if full:
        host.frame_shot(out, name)
    else:
        host.shot(out, name, full=True)


def export(host) -> List[dict]:
    """Save as PNG; returns every text the image drew."""
    host.frame.evaluate(RECORD_FILLS)
    before = len(host.downloads)
    host.frame.click("#export")
    for _ in range(60):
        if len(host.downloads) > before:
            break
        host.settle(100)
    assert len(host.downloads) == before + 1, "no image was delivered"
    image = Image.open(io.BytesIO(host.downloads[-1]))
    assert image.format == "PNG" and image.width == 1080 and image.height > 900
    return host.frame.evaluate("() => window.__fills")


def no_console_error(host) -> None:
    assert not [m for m in host.console if "error" in m.lower()], host.console


def amount_at(text: str, exact: str) -> bool:
    """A phone cell's amount: the exact figure ("271.50", "40" for 40.00), or —
    only for 100 or more, when it cannot fit — whole units."""
    value = D(exact)
    whole = f"{int(value.quantize(D('1'), ROUND_HALF_UP)):,}"
    exact_text = f"{value:,.2f}".removesuffix(".00")
    return text == exact_text or (value >= 100 and text == whole)


def calc_rows(host) -> Dict[str, str]:
    """The rows of "How is this worked out?", ``{label: value}``."""
    rows = host.frame.evaluate(
        "() => [...document.querySelectorAll('#calc > div')].map("
        "d => [...d.children].map(s => s.textContent.trim()))"
    )
    return {label: value for label, value in rows}


def _review_with_coffee(harness, bridge, result: dict) -> None:
    """12 Nov. Coffee every day (stated), 40.00 at a restaurant on the 10th,
    two coffees, the two loans ahead; Groceries, Car maintenance,
    Entertainment and Restaurants are flexible budgets.

    The guide, by hand: 19 days from the 12th to the 30th, today included —
    Restaurants 60.00 / 19 = 3.16, Groceries 320 / 19 = 16.84, Car maintenance
    200 / 19 = 10.53, Entertainment 100 / 19 = 5.26; together 35.79 (680.00
    left). The safe average a day is 722.00 / 18 = 40.11 (1,605 planned − 43
    spent − 500 savings − 340 held for the loans, ÷ the 18 days after
    today): more, so the guide is the envelopes' own sum."""
    month = result["_meta"]["mita/calendar"]["month"]
    summary = month["summary"]
    assert summary["flexible_per_day"] == "35.79"
    assert summary["flexible_left"] == "680.00"
    assert summary["average_per_day"] == "40.11"
    assert summary["flexible_per_day_capped"] is False
    per_line = {c["category"]: c for c in month["categories"]}
    assert {
        code: per_line[code]["left_per_day"]
        for code in (RESTAURANTS, GROCERIES, CAR, FUN)
    } == {RESTAURANTS: "3.16", GROCERIES: "16.84", CAR: "10.53", FUN: "5.26"}
    assert per_line[COFFEE]["spending_type"] == "planned"
    widget = calendar_html()
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        webkit = p.webkit.launch()
        try:
            # --- desktop, inline then fullscreen, light ---------------------
            host = harness.HostPage(
                chromium, bridge, widget, result, {}, viewport=DESKTOP, theme="light"
            )
            host.wait_for(".inline")
            mini = host.frame.evaluate(MINI)
            assert len(mini) == 30
            # the inline card shows the guide too, from today, labelled
            assert [c["value"] for c in mini] == [None] * 11 + ["35.79"] * 19
            assert all(c["guide"] == "≈35.79" for c in mini[11:])
            assert "Average left per day in your flexible budgets" in text_of(
                host, "#mini-guide-note"
            )
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(400)

            # All categories, ACTIVITY: spent so far, scheduled ahead — the
            # coffee the user said they buy every day, and the two loans on
            # their dates. (A begun date whose planned coffee was not
            # recorded shows 0.)
            everything = shown(host)
            assert everything == {
                **{day: "0" for day in (1, 2, 5, 6, 7, 8, 9, 11, 12)},
                3: "1.50",
                4: "1.50",
                10: "40.00",
                **{day: "1.50" for day in range(13, 31)},
                15: "271.50",
                25: "71.50",
            }
            # GUIDANCE: one aggregate on today and every date ahead, apart.
            assert guides(host) == from_day(12, "35.79")
            assert host.frame.evaluate(MERGED) == 0
            found = cells(host)
            assert all(found[d]["guideText"] == "≈35.79" for d in range(12, 31))
            assert ALL_LABEL.format(v="35.79") in found[15]["label"]
            assert "average left per day" not in found[10]["label"]  # past: history
            # labelled where it is drawn
            caption = text_of(host, "#grid-caption")
            assert (
                "≈ marks the average left per day from today: an average of what is "
                "left, not a plan." in caption
            )
            assert "Average left per day: not a plan or a recommendation" in text_of(
                host, ".legend"
            )
            # an average is never presented as advice (owner brief 2026-11-16)
            visible = page_text(host).lower()
            assert "guidance" not in visible and "daily guide" not in visible
            assert "recommended" not in visible
            note = text_of(host, "#flex-note")
            assert "Flexible budgets are monthly limits with no purchase dates" in note
            assert (
                "Average left per day in your flexible budgets: €680.00 left ÷ 19 "
                "days (today included) ≈ €35.79 a day." in note
            )
            guidance = text_of(host, "#flex-guidance")
            assert "Flexible budgets (monthly limits, no dates)" in guidance
            assert "≈ €35.79 a day on average" in guidance
            assert "an average, not a recommendation or a daily limit" in guidance
            # never in a scheduled total: the tile counts the dates ahead's
            # planned purchases and bills only (18 × 1.50 + 270 + 70)
            assert summary["scheduled_after_today"] == "367.00"
            tiles = page_text(host)
            assert "Scheduled on the days left" in tiles and "€367.00" in tiles
            assert "€1,011.22" not in tiles  # 367.00 + 18 × 35.79
            keep(host, "desktop-all-categories", full=True)

            # How it is worked out: both daily figures, both divisors named.
            host.frame.click("#calc-toggle")
            host.settle(200)
            assert calc_rows(host) == {
                "Plan": "€1,605.00",
                "− Spent": "€43.00",
                "− Protected savings": "€500.00",
                "− Held for bills": "€340.00",
                "= Left to spend": "€722.00",
                "÷ Days after today": "18",
                "= On average a day": "€40.11",
                "Flexible budgets left": "€680.00",
                "÷ Days left, today included": "19",
                "= Average left per day": "≈ €35.79",
            }
            assert "never part of a date’s amount" in text_of(host, "#calc-guide")
            host.frame.click("#calc-toggle")
            host.settle(150)

            # Each flexible budget, filtered: only what was really spent is
            # an amount (2.9.0 drew 3.33 / 3.34, 10.67 and 6.67 on all of
            # them); its own average left per day is on today and every date ahead.
            per_filter = {}
            for label, code, spent in (
                ("Restaurants", RESTAURANTS, {10: "40.00"}),
                ("Groceries", GROCERIES, {}),
                ("Car maintenance", CAR, {}),
                ("Entertainment", FUN, {}),
            ):
                set_filter(host, label)
                found = cells(host)
                per_filter[code] = shown(host)
                assert per_filter[code] == spent, label
                assert guides(host) == from_day(12, per_line[code]["left_per_day"])
                assert host.frame.evaluate(MERGED) == 0
                assert not DAILY_SHARE.search(
                    " ".join(c["text"] for c in found.values())
                ), label
                assert all(not c["over"] and not c["meter"] for c in found.values())
                assert all(not DAILY_SHARE.search(c["label"]) for c in found.values())
                banner = text_of(host, "#filter-banner")
                assert "flexible budget" in banner and "no purchase dates" in banner
                assert f"≈ €{per_line[code]['left_per_day']} a day on average" in banner
                assert "all flexible budgets together" not in banner  # not capped
                flex_note = text_of(host, "#flex-note")
                assert f"{label} is a flexible budget" in flex_note
                assert f"Average left per day for {label}:" in flex_note
                if label == "Restaurants":
                    assert "spent €40.00 of €100.00 this month" in banner
                    assert "€60.00 left" in banner
                    assert (
                        "Average left per day for Restaurants: €60.00 left ÷ 19 days "
                        "(today included) = €3.16 a day." in flex_note
                    )
                    # a date ahead, read out: no amount, why, and the guide
                    assert "nothing is planned for this date" in found[20]["label"]
                    assert (
                        "average left per day for Restaurants about €3.16, what is left "
                        "divided by the days left, not a plan or a recommendation"
                        in found[20]["label"]
                    )
                    assert "spent €40.00 from its monthly budget" in found[10]["label"]
                    # a filter changes no scheduled event: the 15th still holds
                    # the loan and the coffee, and its guide is the line's
                    host.frame.click("#day-2026-11-15")
                    host.settle(300)
                    detail = text_of(host, "#day-detail")
                    assert "Scheduled for the date" in detail and "€271.50" in detail
                    day_guide = text_of(host, "#day-guide")
                    assert "≈ €3.16" in day_guide
                    assert "a day on average for Restaurants" in day_guide
                    assert "All your flexible budgets together: ≈ €35.79 a day." in (
                        day_guide
                    )
                    assert "not part of the €271.50 scheduled for this date" in (
                        day_guide
                    )
                    keep(host, "desktop-filter-restaurants", full=True)
                    accessible(host, "desktop, Restaurants filter")

            # The coffee: a stated daily purchase, on every date ahead — its
            # money is on its dates already, so it has no guide of its own.
            set_filter(host, "Coffee")
            per_filter[COFFEE] = shown(host)
            assert {d: a for d, a in per_filter[COFFEE].items() if d >= 13} == {
                day: "1.50" for day in range(13, 31)
            }
            assert per_filter[COFFEE][3] == per_filter[COFFEE][4] == "1.50"
            assert "flexible budget" not in text_of(host, "#filter-banner")
            assert guides(host) == {}
            keep(host, "desktop-filter-coffee", full=True)

            # The loans: on their due dates only, no guide.
            set_filter(host, "Car loan")
            per_filter["car loan"] = shown(host)
            assert per_filter["car loan"] == {15: "270.00"}
            assert guides(host) == {}
            set_filter(host, "Laptop loan")
            per_filter["laptop loan"] = shown(host)
            assert per_filter["laptop loan"] == {25: "70.00"}

            # J, drawn: the filters' dates add up to "All categories"; the
            # flexible budgets' guides add up to the aggregate (not capped).
            set_filter(host, None)
            for day, amount in everything.items():
                parts = sum(
                    (D(view[day]) for view in per_filter.values() if day in view),
                    D("0"),
                )
                assert parts == D(amount), day
            for view in per_filter.values():
                for day, amount in view.items():
                    if D(amount) > 0:
                        assert day in everything, day
            assert sum(
                D(per_line[c]["left_per_day"])
                for c in (RESTAURANTS, GROCERIES, CAR, FUN)
            ) == D(summary["flexible_per_day"])

            # A date ahead, selected: what is scheduled (activity), then the
            # average left per day, then the budgets as the month's.
            host.frame.click("#day-2026-11-20")
            host.settle(300)
            detail = text_of(host, "#day-detail")
            assert "PLANNED FOR THIS DATE" in detail.upper()
            assert "€1.50" in detail and "planned purchases and bills" in detail
            day_guide = text_of(host, "#day-guide")
            assert "≈ €35.79" in day_guide
            assert "a day on average in your flexible budgets" in day_guide
            assert "not a recommendation" in day_guide
            assert "not part of the €1.50 scheduled for this date" in day_guide
            assert "nothing is taken from your balance" in day_guide
            budgets = text_of(host, "#flex-budgets")
            assert "FLEXIBLE BUDGETS · THIS MONTH" in budgets.upper()
            assert "nothing here is planned for this date" in budgets
            assert "€60.00 left of €100.00 this month" in budgets
            assert "≈ €3.16 a day" in budgets and "≈ €16.84 a day" in budgets
            assert "To spend on flexible budgets" not in detail
            assert not DAILY_SHARE.search(detail)
            # activity first, then the guidance
            upper = detail.upper()
            assert upper.index("PLANNED FOR THIS DATE") < upper.index(
                "AVERAGE LEFT PER DAY"
            )
            keep(host, "desktop-date-ahead", full=True)
            accessible(host, "desktop, a date ahead")

            # The loan's date: purchases + bills = what is scheduled; the
            # guide apart, never added (271.50 + 35.79 = 307.29 is nowhere).
            host.frame.click("#day-2026-11-15")
            host.settle(300)
            detail = text_of(host, "#day-detail")
            assert "Planned purchases" in detail and "Scheduled for the date" in detail
            assert "€271.50" in detail and "€270.00" in detail
            assert "Everyday plan" not in detail
            assert "not part of the €271.50 scheduled for this date" in text_of(
                host, "#day-guide"
            )
            assert "307.29" not in page_text(host)

            # The restaurant's date: the expense; nothing "left for the date";
            # a past date has no guide.
            host.frame.click("#day-2026-11-10")
            host.settle(600)
            detail = text_of(host, "#day-detail")
            assert "€40.00" in detail and "of €1.50 planned" in detail
            assert "Within what was planned and your monthly budgets" in detail
            assert "of the everyday plan left" not in detail
            assert "daily share" not in detail
            assert "from its monthly budget" in detail
            assert "Bistro" in detail  # the expense itself, from list_transactions
            assert host.frame.query_selector("#day-guide") is None
            keep(host, "desktop-date-spent", full=True)

            # What the model is told about the selection: no per-date share;
            # the guide, said to be guidance.
            context = " ".join(
                item["content"][0]["text"] for item in host.log()["context"][-1:]
            )
            assert "monthly limits on no date" in context
            assert "daily share" not in context
            assert (
                "The calendar shows the average left per day (about 35.79 EUR a day)"
                in context
            )
            assert "never part of a date's amount" in context

            # The image: the guide in its own pill beside, never inside, a
            # date's amount — every text it draws is recorded.
            fills = export(host)
            texts = [f["t"] for f in fills]
            guide_fills = [f for f in fills if f["t"] == "≈ 35.79"]
            assert len(guide_fills) == 19  # the 12th to the 30th
            assert {f["ink"].lower() for f in guide_fills} == {GUIDE_INK}
            ahead = [f for f in fills if f["ink"].lower() == SCHEDULED_INK]
            assert sorted(
                f["t"] for f in ahead if f["t"] in ("1.50", "71.50", "271.50")
            ) == (sorted(["1.50"] * 16 + ["71.50", "271.50"]))
            loan = next(f for f in fills if f["t"] == "271.50")
            assert any(
                abs(g["x"] - (loan["x"] + 4)) < 0.5 and 0 < g["y"] - loan["y"] < 40
                for g in guide_fills
            ), "the 15th has its own guide pill under its amount"
            for merged in ("307.29", "37.29", "107.29", "35.79 + "):
                assert not any(merged in t for t in texts), merged
            assert (
                "Average left per day: flexible budgets’ left ÷ days left — not a plan "
                "or a recommendation" in texts
            )
            if SHOTS:
                Path(SHOTS, "exported-month.png").write_bytes(host.downloads[-1])

            # The switch: activity alone, identical; the choice is said, and
            # the image follows it.
            switch_guide(host, False)
            assert guides(host) == {}
            assert shown(host) == everything
            assert "The daily average is hidden." in text_of(host, "#grid-caption")
            assert "Average left per day:" not in text_of(host, ".legend")
            host.frame.click("#day-2026-11-20")
            host.settle(300)
            assert host.frame.query_selector("#day-guide") is None
            assert "€60.00 left" in text_of(host, "#flex-budgets")
            assert "≈" not in text_of(host, "#day-detail")
            context = host.log()["context"][-1]["content"][0]["text"]
            assert "The user hid the daily average" in context
            fills = export(host)
            assert not [f for f in fills if f["t"].startswith("≈")]
            assert "271.50" in [f["t"] for f in fills]
            keep(host, "desktop-guide-off", full=True)
            switch_guide(host, True)
            assert guides(host) == from_day(12, "35.79")

            # Month navigation: December has no plan (no guide); back again.
            host.frame.click("#next-month")
            wait_title(host, "December 2026")
            host.settle(300)
            assert "No saved plan for December 2026" in page_text(host)
            assert shown(host) == {} and guides(host) == {}
            assert host.frame.query_selector("#guide-toggle") is None
            host.frame.click("#prev-month")
            wait_title(host, "November 2026")
            host.settle(300)
            assert shown(host) == everything
            assert guides(host) == from_day(12, "35.79")
            no_console_error(host)
            host.close()

            # --- phone: inline and fullscreen, light and dark ---------------
            for theme in ("light", "dark"):
                host = harness.HostPage(
                    webkit,
                    bridge,
                    widget,
                    result,
                    {},
                    viewport=PHONE,
                    theme=theme,
                    mobile=True,
                )
                host.wait_for(".inline")
                host.settle(500)
                applied = host.frame.evaluate(
                    "() => document.documentElement.getAttribute('data-theme')"
                )
                assert applied == theme
                mini = host.frame.evaluate(MINI)
                assert len(mini) == 30
                # every cent on a phone: the coffee is 1.50, never "2"
                amounts = [c["amount"] for c in mini]
                assert amounts[19] == "1.50" and amounts[12] == "1.50"
                assert amounts[2] == amounts[3] == "1.50" and amounts[9] == "40"
                assert amount_at(amounts[14], "271.50") and amounts[24] == "71.50"
                assert amounts[0] == ""
                assert "2" not in [a for i, a in enumerate(amounts) if i not in (14,)]
                # the guide: whole units on a phone ("about"), from today
                assert [c["guide"] for c in mini] == [""] * 11 + ["≈36"] * 19
                fit = host.frame.evaluate(harness.NARROW_FIT)
                assert fit["overflow"] <= 0 and not fit["cut"], fit
                keep(host, f"phone-inline-{theme}")

                host.frame.click("#open-full")
                host.wait_for(".full")
                host.settle(500)
                found = cells(host)
                assert found[20]["text"] == "1.50" and found[3]["text"] == "1.50"
                assert amount_at(found[15]["text"], "271.50")
                assert found[25]["text"] == "71.50" and found[10]["text"] == "40"
                assert guides(host) == from_day(12, "35.79")
                assert found[20]["guideText"] == "≈36"
                set_filter(host, "Restaurants")
                found = cells(host)
                assert {d: c["text"] for d, c in found.items() if c["text"]} == {
                    10: "40"
                }
                assert guides(host) == from_day(12, "3.16")
                assert found[20]["guideText"] == "≈3"
                fit = host.frame.evaluate(harness.NARROW_FIT)
                assert fit["overflow"] <= 0 and not fit["cut"], fit
                keep(host, f"phone-filter-restaurants-{theme}", full=True)
                accessible(host, f"phone {theme}, Restaurants filter")
                switch_guide(host, False)
                assert guides(host) == {}
                fit = host.frame.evaluate(harness.NARROW_FIT)
                assert fit["overflow"] <= 0 and not fit["cut"], fit
                no_console_error(host)
                host.close()

            # --- the switch is the user's choice, kept by the host ----------
            # (ChatGPT's widget state: a card opened again starts as it was)
            host = harness.HostPage(
                webkit,
                bridge,
                widget,
                result,
                {},
                viewport=PHONE,
                mobile=True,
                init_script=(
                    "window.openai = {widgetState: {privateContent: {guide: false}},"
                    " setWidgetState: function (s) { (window.__saved = window.__saved"
                    " || []).push(s); }};"
                ),
            )
            host.wait_for(".inline")
            host.settle(400)
            assert [c["guide"] for c in host.frame.evaluate(MINI)] == [""] * 30
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(400)
            assert guides(host) == {}
            assert host.frame.get_attribute("#guide-toggle", "aria-checked") == "false"
            switch_guide(host, True)
            assert guides(host) == from_day(12, "35.79")
            saved = host.frame.evaluate("() => window.__saved || []")
            assert saved and saved[-1]["privateContent"]["guide"] is True
            host.close()

            # --- the narrowest phone (a 360 dp Android's chat column) -------
            # Every date's detail, with and without a filter, guide on and
            # off: nothing may push the page sideways or cut a figure, and an
            # amount under 100 keeps its cents.
            host = harness.HostPage(
                webkit,
                bridge,
                widget,
                result,
                {},
                viewport=NARROW,
                theme="light",
                mobile=True,
            )
            host.wait_for(".inline")
            host.settle(400)
            mini = host.frame.evaluate(MINI)
            assert mini[19]["amount"] == "1.50" and mini[9]["amount"] == "40"
            assert amount_at(mini[14]["amount"], "271.50")
            fit = host.frame.evaluate(harness.NARROW_FIT)
            assert fit["overflow"] <= 0 and not fit["cut"], fit
            keep(host, "narrow-inline")
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(500)
            found = cells(host)
            assert found[20]["text"] == "1.50" and found[25]["text"] == "71.50"
            assert amount_at(found[15]["text"], "271.50")
            if found[15]["text"] != "271.50":  # rounded to fit: said so
                assert ROUNDED_NOTE in page_text(host)
            assert guides(host) == from_day(12, "35.79")
            keep(host, "narrow-fullscreen", full=True)
            for on in (True, False):
                switch_guide(host, on)
                for label in (None, "Restaurants", "Coffee"):
                    set_filter(host, label)
                    for day in (10, 12, 15, 20):
                        host.frame.click(f"#day-2026-11-{day:02d}")
                        host.settle(250)
                        fit = host.frame.evaluate(harness.NARROW_FIT)
                        assert fit["overflow"] <= 0 and not fit["cut"], (
                            on,
                            label,
                            day,
                            fit,
                        )
            no_console_error(host)
            host.close()
        finally:
            chromium.close()
            webkit.close()


def _review_empty_month(harness, bridge, result: dict) -> None:
    """2 Nov, no pattern stated for anything: every line is a flexible
    budget. The dates have no amount but the two loans — and the guide on
    every date from today: 29 days, today included — Groceries 320 / 29 =
    11.03, Car maintenance 6.90, Entertainment and Restaurants 3.45 each,
    Coffee 45 / 29 = 1.55; together 26.38 (765.00 left), under the safe
    average 765.00 / 28 = 27.32."""
    summary = result["_meta"]["mita/calendar"]["month"]["summary"]
    assert summary["flexible_per_day"] == "26.38"
    assert summary["average_per_day"] == "27.32"
    assert summary["flexible_per_day_capped"] is False
    widget = calendar_html()
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            host = harness.HostPage(
                chromium, bridge, widget, result, {}, viewport=DESKTOP, theme="light"
            )
            host.wait_for(".inline")
            mini = host.frame.evaluate(MINI)
            assert [c["amount"] for c in mini if c["amount"]] == ["270.00", "70.00"]
            assert [c["value"] for c in mini] == [None] + ["26.38"] * 29
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(400)
            assert shown(host) == {15: "270.00", 25: "70.00"}
            empty = [d for d, c in cells(host).items() if not c["text"]]
            assert len(empty) == 28
            # not an empty calendar: the guide is on every date from today
            assert guides(host) == from_day(2, "26.38")
            # an empty date, selected: nothing scheduled — it says why — and
            # the guide, apart
            host.frame.click("#day-2026-11-20")
            host.settle(300)
            detail = text_of(host, "#day-detail")
            assert "Nothing scheduled" in detail
            assert "No purchase or bill is planned for this date." in detail
            assert "Your flexible budgets are monthly limits" in detail
            day_guide = text_of(host, "#day-guide")
            assert (
                "≈ €26.38" in day_guide and "nothing is scheduled for it" in day_guide
            )
            assert "€320.00 left of €320.00 this month" in text_of(
                host, "#flex-budgets"
            )
            label = cells(host)[20]["label"]
            assert "no purchase or bill planned" in label
            assert ALL_LABEL.format(v="26.38") in label
            for name, guide in (
                ("Groceries", "11.03"),
                ("Car maintenance", "6.90"),
                ("Entertainment", "3.45"),
                ("Coffee", "1.55"),
            ):
                set_filter(host, name)
                assert shown(host) == {}, name
                assert guides(host) == from_day(2, guide), name
            set_filter(host, None)
            keep(host, "desktop-empty-dates", full=True)
            accessible(host, "desktop, empty dates")
            no_console_error(host)
            host.close()

            # Spending outside the flexible budgets: €300 of shopping nobody
            # planned. The budgets still show 765.00, but the month as a
            # whole has 465.00 left after bills and savings: 465.00 / 28 =
            # 16.61 a day, under their 26.38 — so the guide is the safe
            # average, and the calendar says why.
            bridge.call(
                "add_transaction",
                {
                    "amount": "300.00",
                    "category": "shopping",
                    "date": "2026-11-02",
                    "idempotency_key": key(),
                },
            )
            capped = bridge.call("show_financial_calendar", {"year": 2026, "month": 11})
            summary = capped["_meta"]["mita/calendar"]["month"]["summary"]
            assert summary["flexible_left"] == "765.00"
            assert summary["average_per_day"] == "16.61"
            assert summary["flexible_per_day"] == "16.61"
            assert summary["flexible_per_day_capped"] is True
            host = harness.HostPage(
                chromium, bridge, widget, capped, {}, viewport=DESKTOP, theme="light"
            )
            host.wait_for(".inline")
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(400)
            assert guides(host) == from_day(2, "16.61")
            note = text_of(host, "#flex-note")
            assert (
                "€16.61 a day — the safe average a day: after bills and savings the "
                "month as a whole has less left than the €765.00 they still show."
                in note
            )
            assert "(the safe average)" in text_of(host, "#flex-guidance")
            set_filter(host, "Groceries")
            assert guides(host) == from_day(2, "11.03")  # the line's own
            banner = text_of(host, "#filter-banner")
            assert (
                "all flexible budgets together ≈ €16.61 a day (the safe average)"
                in banner
            )
            keep(host, "desktop-guide-capped", full=True)
            no_console_error(host)
            host.close()
        finally:
            chromium.close()


async def test_the_rendered_calendar_keeps_activity_and_guidance_apart(mcp, seed):
    harness = _harness()
    loop = asyncio.get_running_loop()

    # 1. The brief's November with a stated daily coffee, seen on the 12th.
    _user, token, _draft = await november(mcp, seed, patterns=[COFFEE_DAILY])
    m12 = mcp.at(noon(12))
    for amount, line, day, merchant in (
        ("1.50", "Coffee", 3, None),
        ("1.50", "Coffee", 4, None),
        ("40.00", "Restaurants", 10, "Bistro"),
    ):
        arguments = {
            "amount": amount,
            "budget_line": line,
            "date": f"2026-11-{day:02d}",
            "idempotency_key": key(),
        }
        if merchant:
            arguments["merchant"] = merchant
        await call(m12, token, "add_transaction", arguments)
    bridge = InProcessBridge(loop, m12, token)
    result = await asyncio.to_thread(
        bridge.call, "show_financial_calendar", {"year": 2026, "month": 11}
    )
    assert result["_meta"]["mita/calendar"]["version"] == 2
    await asyncio.to_thread(_review_with_coffee, harness, bridge, result)
    # the component asked only for MITA's two read tools
    assert set(bridge.calls) <= {
        "show_financial_calendar",
        "get_calendar_month",
        "list_transactions",
    }

    # 2. The same month with nothing said about when: no amount on a date
    #    but the loans, and the guide on every date from today.
    _user2, token2, _draft2 = await november(mcp, seed)
    m2 = mcp.at(noon(2))
    bridge2 = InProcessBridge(loop, m2, token2)
    result2 = await asyncio.to_thread(
        bridge2.call, "show_financial_calendar", {"year": 2026, "month": 11}
    )
    await asyncio.to_thread(_review_empty_month, harness, bridge2, result2)
