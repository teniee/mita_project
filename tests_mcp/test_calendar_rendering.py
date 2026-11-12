"""The calendar component, rendered: what a date's cell actually shows.

Brief of 2026-11-11, test L. ``test_flexible_envelopes_calendar.py`` proves
what MITA sends; this proves what the component DRAWS from it, which is where
the defect of 2.9.0 was visible: with a category filter the component drew a
flexible budget's stored daily share on every date (Restaurants 3.33 / 3.34,
Groceries 10.67, Car maintenance 6.67), and the exported image did the same
for every date ahead.

The real component runs in an iframe sandboxed with ``allow-scripts`` only
under the MCP Apps restrictive CSP — the host page of
``scripts/mcp/calendar_widget_review.py`` — and is fed real tool results:
every ``tools/call`` it makes goes to MITA's real tools, in process, on the
test's own PostgreSQL transaction. Phone (WebKit, 390 px) and desktop
(Chromium), light and dark.

Dev-only dependencies, as for the harness (not in ``requirements-mcp*``, so
MCP CI skips this module): ``pip install playwright==1.49.1 Pillow`` and
``playwright install chromium webkit``. Set ``MITA_CALENDAR_SHOTS`` to a
directory to keep screenshots (``docs/chatgpt-app/review/calendar-v4/``) and
``MITA_AXE`` to an ``axe.min.js`` (axe-core 4.10) to add WCAG 2.2 AA checks
of the filtered views and the empty date.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pytest

pytest.importorskip(
    "playwright.sync_api",
    reason="dev-only: playwright==1.49.1 (+ `playwright install chromium webkit`)",
)
pytest.importorskip("PIL", reason="dev-only: Pillow")

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
DESKTOP = {"width": 1280, "height": 900}


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
  return {day: Number(c.dataset.date.slice(-2)), text: amt ? amt.textContent.trim() : '',
          exact: v ? v.dataset.amount : null, label: c.getAttribute('aria-label'),
          over: c.classList.contains('over'), meter: !!c.querySelector('.meter')};
})"""
MINI = """() => [...document.querySelectorAll('.mini .mcell:not(.blank)')].map(
  c => (c.querySelector('span') || {textContent: ''}).textContent.trim())"""


def cells(host) -> Dict[int, dict]:
    return {c["day"]: c for c in host.frame.evaluate(CELLS)}


def shown(host) -> Dict[int, str]:
    """``{day: the exact amount in its cell}`` for the cells that hold one."""
    return {
        day: c["exact"] for day, c in cells(host).items() if c["text"] and c["exact"]
    }


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


def _review_with_coffee(harness, bridge, result: dict) -> None:
    """12 Nov. Coffee every day (stated), 40.00 at a restaurant on the 10th,
    two coffees, the two loans ahead; Groceries, Car maintenance,
    Entertainment and Restaurants are flexible budgets."""
    widget = calendar_html()
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        webkit = p.webkit.launch()
        try:
            # --- desktop, fullscreen, light --------------------------------
            host = harness.HostPage(
                chromium, bridge, widget, result, {}, viewport=DESKTOP, theme="light"
            )
            host.wait_for(".inline")
            assert "≈" not in page_text(host)
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(400)

            # All categories: spent so far, scheduled ahead — the coffee the
            # user said they buy every day, and the two loans on their dates.
            # (A begun date whose planned coffee was not recorded shows 0.)
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
            assert "≈" not in page_text(host)
            assert "Flexible budgets are monthly limits with no purchase dates" in (
                text_of(host, "#flex-note")
            )
            guidance = text_of(host, "#flex-guidance")
            assert "Flexible budgets (monthly limits, no dates)" in guidance
            assert "as guidance, not a daily limit" in guidance
            keep(host, "desktop-all-categories", full=True)

            # Each flexible budget, filtered: only what was really spent is
            # on a date. 2.9.0 drew 3.33 / 3.34, 10.67 and 6.67 on all of them.
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
                assert not DAILY_SHARE.search(
                    " ".join(c["text"] for c in found.values())
                ), label
                assert all(not c["over"] and not c["meter"] for c in found.values())
                assert all(not DAILY_SHARE.search(c["label"]) for c in found.values())
                banner = text_of(host, "#filter-banner")
                assert "flexible budget" in banner and "no purchase dates" in banner
                assert f"{label} is a flexible budget" in text_of(host, "#flex-note")
                if label == "Restaurants":
                    assert "spent €40.00 of €100.00 this month" in banner
                    assert "€60.00 left" in banner and "as guidance" in banner
                    # a date ahead, read out: no amount, and why
                    assert "nothing is planned for this date" in found[20]["label"]
                    assert "spent €40.00 from its monthly budget" in found[10]["label"]
                    keep(host, "desktop-filter-restaurants", full=True)
                    accessible(host, "desktop, Restaurants filter")

            # The coffee: a stated daily purchase, on every date ahead.
            set_filter(host, "Coffee")
            per_filter[COFFEE] = shown(host)
            assert {d: a for d, a in per_filter[COFFEE].items() if d >= 13} == {
                day: "1.50" for day in range(13, 31)
            }
            assert per_filter[COFFEE][3] == per_filter[COFFEE][4] == "1.50"
            assert "flexible budget" not in text_of(host, "#filter-banner")
            keep(host, "desktop-filter-coffee", full=True)

            # The loans: on their due dates only.
            set_filter(host, "Car loan")
            per_filter["car loan"] = shown(host)
            assert per_filter["car loan"] == {15: "270.00"}
            set_filter(host, "Laptop loan")
            per_filter["laptop loan"] = shown(host)
            assert per_filter["laptop loan"] == {25: "70.00"}

            # J, drawn: the filters' dates add up to "All categories".
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

            # A date ahead, selected: what is scheduled, and the budgets as
            # the month's — never an amount for this date.
            host.frame.click("#day-2026-11-20")
            host.settle(300)
            detail = text_of(host, "#day-detail")
            assert "PLANNED FOR THIS DATE" in detail.upper()
            assert "€1.50" in detail and "planned purchases and bills" in detail
            budgets = text_of(host, "#flex-budgets")
            assert "FLEXIBLE BUDGETS · THIS MONTH" in budgets.upper()
            assert "nothing here is planned for this date" in budgets
            assert "€60.00 left of €100.00 this month" in budgets
            assert "≈" not in detail and "To spend on flexible budgets" not in detail
            assert not DAILY_SHARE.search(detail.replace("€3.33 a day exactly", ""))
            keep(host, "desktop-date-ahead", full=True)
            accessible(host, "desktop, a date ahead")

            # The loan's date: purchases + bills = what is scheduled.
            host.frame.click("#day-2026-11-15")
            host.settle(300)
            detail = text_of(host, "#day-detail")
            assert "Planned purchases" in detail and "Scheduled for the date" in detail
            assert "€271.50" in detail and "€270.00" in detail
            assert "Everyday plan" not in detail

            # The restaurant's date: the expense; nothing "left for the date".
            host.frame.click("#day-2026-11-10")
            host.settle(600)
            detail = text_of(host, "#day-detail")
            assert "€40.00" in detail and "of €1.50 planned" in detail
            assert "Within what was planned and your monthly budgets" in detail
            assert "of the everyday plan left" not in detail
            assert "daily share" not in detail
            assert "from its monthly budget" in detail
            assert "Bistro" in detail  # the expense itself, from list_transactions
            keep(host, "desktop-date-spent", full=True)

            # What the model is told about the selection: no per-date share.
            context = " ".join(
                item["content"][0]["text"] for item in host.log()["context"][-1:]
            )
            assert "monthly limits on no date" in context
            assert "daily share" not in context

            # Month navigation: December has no plan; back to November.
            host.frame.click("#next-month")
            wait_title(host, "December 2026")
            host.settle(300)
            assert "No saved plan for December 2026" in page_text(host)
            assert shown(host) == {}
            host.frame.click("#prev-month")
            wait_title(host, "November 2026")
            host.settle(300)
            assert shown(host) == everything

            # Save as PNG, through the host download.
            host.frame.click("#export")
            host.settle(1200)
            assert host.downloads, "no image was delivered"
            image = Image.open(io.BytesIO(host.downloads[-1]))
            assert image.format == "PNG" and image.width == 1080 and image.height > 900
            if SHOTS:
                Path(SHOTS, "exported-month.png").write_bytes(host.downloads[-1])
            assert not [m for m in host.console if "error" in m.lower()], host.console
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
                assert len(mini) == 30 and "≈" not in " ".join(mini)
                # whole euros on a phone: spent on the 3rd, 4th and 10th;
                # ahead the coffee (1.50 -> 2) and the loans' dates
                assert mini[9] == "40" and mini[14] == "272" and mini[24] == "72"
                assert mini[0] == "" and mini[19] == "2"
                fit = host.frame.evaluate(harness.NARROW_FIT)
                assert fit["overflow"] <= 0 and not fit["cut"], fit
                keep(host, f"phone-inline-{theme}")

                host.frame.click("#open-full")
                host.wait_for(".full")
                host.settle(500)
                set_filter(host, "Restaurants")
                found = cells(host)
                assert {d: c["text"] for d, c in found.items() if c["text"]} == {
                    10: "40"
                }
                assert "≈" not in page_text(host)
                fit = host.frame.evaluate(harness.NARROW_FIT)
                assert fit["overflow"] <= 0 and not fit["cut"], fit
                keep(host, f"phone-filter-restaurants-{theme}", full=True)
                accessible(host, f"phone {theme}, Restaurants filter")
                assert not [m for m in host.console if "error" in m.lower()]
                host.close()

            # --- the narrowest phone (a 360 dp Android's chat column) -------
            # Every date's detail, with and without a filter: nothing may
            # push the page sideways (a no-wrap amount column once did).
            host = harness.HostPage(
                webkit,
                bridge,
                widget,
                result,
                {},
                viewport={"width": 320, "height": 640},
                theme="light",
                mobile=True,
            )
            host.wait_for(".inline")
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(500)
            for label in (None, "Restaurants", "Coffee"):
                if label:
                    set_filter(host, label)
                for day in (10, 12, 15, 20):
                    host.frame.click(f"#day-2026-11-{day:02d}")
                    host.settle(250)
                    fit = host.frame.evaluate(harness.NARROW_FIT)
                    assert fit["overflow"] <= 0 and not fit["cut"], (label, day, fit)
            host.close()
        finally:
            chromium.close()
            webkit.close()


def _review_empty_month(harness, bridge, result: dict) -> None:
    """2 Nov, no pattern stated for anything: every line is a flexible
    budget. The dates are empty but for the two loans."""
    widget = calendar_html()
    with sync_playwright() as p:
        chromium = p.chromium.launch()
        try:
            host = harness.HostPage(
                chromium, bridge, widget, result, {}, viewport=DESKTOP, theme="light"
            )
            host.wait_for(".inline")
            mini = host.frame.evaluate(MINI)
            assert [a for a in mini if a] == ["270.00", "70.00"]
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.settle(400)
            assert shown(host) == {15: "270.00", 25: "70.00"}
            empty = [d for d, c in cells(host).items() if not c["text"]]
            assert len(empty) == 28
            assert "≈" not in page_text(host)
            # an empty date, selected: nothing scheduled — and it says why
            host.frame.click("#day-2026-11-20")
            host.settle(300)
            detail = text_of(host, "#day-detail")
            assert "Nothing scheduled" in detail
            assert "No purchase or bill is planned for this date." in detail
            assert "Your flexible budgets are monthly limits" in detail
            assert "€320.00 left of €320.00 this month" in text_of(
                host, "#flex-budgets"
            )
            assert "no purchase or bill planned" in cells(host)[20]["label"]
            assert "guidance" not in cells(host)[20]["label"]
            for label in ("Groceries", "Car maintenance", "Entertainment", "Coffee"):
                set_filter(host, label)
                assert shown(host) == {}, label
            keep(host, "desktop-empty-dates", full=True)
            accessible(host, "desktop, empty dates")
            assert not [m for m in host.console if "error" in m.lower()], host.console
            host.close()
        finally:
            chromium.close()


async def test_the_rendered_calendar_puts_no_flexible_budget_on_a_date(mcp, seed):
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

    # 2. The same month with nothing said about when: empty dates.
    _user2, token2, _draft2 = await november(mcp, seed)
    m2 = mcp.at(noon(2))
    bridge2 = InProcessBridge(loop, m2, token2)
    result2 = await asyncio.to_thread(
        bridge2.call, "show_financial_calendar", {"year": 2026, "month": 11}
    )
    await asyncio.to_thread(_review_empty_month, harness, bridge2, result2)
