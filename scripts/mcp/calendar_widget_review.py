#!/usr/bin/env python3
"""Review harness for MITA's calendar component (MCP Apps), outside ChatGPT.

    python scripts/mcp/calendar_widget_review.py --base-url https://localhost:8765 \\
        --out docs/chatgpt-app/review/calendar-v1 [--database-url postgresql://...] \\
        [--axe path/to/axe.min.js]

What it does, against a RUNNING MCP service (local or staging, never production):

1. Creates a NEW fictional account through the real OAuth sign-up page
   (``e2e_v2.connect``) and fills one fictional family month through MITA's
   own tools: profile, regular payments, the reviewed budget for this month and
   the next, a savings goal, a month of expenses and last month's expenses.
2. Renders the component exactly as an MCP Apps host does: reads the ``ui://``
   resource over MCP, loads it into an iframe sandboxed with ``allow-scripts``
   only and the spec's restrictive CSP (no network, no external asset),
   answers the JSON-RPC bridge (``ui/initialize``, tool input and result,
   display modes, size changes, model context, downloads) and forwards every
   ``tools/call`` to the server with the account's token, like ChatGPT does.
3. Checks the component against the tool's figures, its bridge traffic, the
   exported PNG, keyboard navigation and accessibility (axe-core, optional),
   and saves screenshots. The host chrome says "Local MCP Apps host — not
   ChatGPT": these are not ChatGPT screenshots.

With --database-url the account is deleted at the end (everything cascades).
Never prints the token, password or e-mail. Refuses production hosts.

Dev-only dependencies (not in requirements-mcp*): playwright==1.49.1 with
``playwright install chromium webkit``, Pillow.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import secrets
import sys
import threading
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "mcp"))
sys.path.insert(0, str(ROOT))
from _target_guard import assert_writable_target  # noqa: E402
from e2e_v2 import connect  # noqa: E402

CALENDAR_URI = "ui://mita/financial-calendar-v1.html"
# The spec's default when a resource declares no domains (SEP-1865, "Host
# Behavior"), minus 'self' — the review frame has an opaque origin.
VIEW_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data:; media-src data:; object-src 'none'; connect-src 'none'; "
    "frame-src 'none'; base-uri 'none'; form-action 'none'"
)
CHECKS: List[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        print(f"FAIL  {name}  {detail[:400]}")
        raise SystemExit(1)
    CHECKS.append(name)
    print(f"PASS  {name}")


# --- the MCP side: one client session on a background loop -----------------------


class McpBridge:
    """An MCP client session the browser thread can call synchronously. One
    long-lived task owns the session (anyio scopes must close in the task
    that opened them); calls run as their own tasks on the same loop."""

    def __init__(self, base: str, token: str):
        self.base, self.token = base, token
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.calls: List[str] = []
        self._ready = threading.Event()
        self._stop: Optional[asyncio.Event] = None
        self._owner = asyncio.run_coroutine_threadsafe(self._own(), self.loop)
        if not self._ready.wait(60):
            raise SystemExit("could not open the MCP session")

    def run(self, coro, timeout: float = 120):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    async def _own(self):
        self._stop = asyncio.Event()
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {self.token}"}, timeout=60
        ) as http:
            async with Client(
                streamable_http_client(f"{self.base}/mcp", http_client=http)
            ) as client:
                self.client = client
                self._ready.set()
                await self._stop.wait()

    def close(self):
        if self._stop is not None:
            self.loop.call_soon_threadsafe(self._stop.set)
        try:
            self._owner.result(30)
        finally:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def call(self, tool: str, args: Optional[dict] = None) -> Dict[str, Any]:
        self.calls.append(tool)
        result = self.run(
            self.client.call_tool(
                tool, args or {}, meta={"openai/session": "calendar-review"}
            )
        )
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)

    def ok(self, tool: str, args: Optional[dict] = None) -> Dict[str, Any]:
        result = self.call(tool, args)
        check(f"{tool} succeeds", not result.get("isError"), str(result)[:300])
        return result

    def resource(self, uri: str) -> Dict[str, Any]:
        read = self.run(self.client.read_resource(uri))
        return read.model_dump(mode="json", by_alias=True, exclude_none=True)


# --- the fictional month ------------------------------------------------------------


def _key() -> str:
    return uuid.uuid4().hex


def seed(mcp: McpBridge, today: date) -> None:
    """A fictional family's month, entered as a user would in ChatGPT."""
    mcp.ok(
        "update_financial_profile",
        {
            "monthly_net_income": "3200.00",
            "currency": "EUR",
            "timezone": "Europe/Sofia",
            "household_size": 3,
            "monthly_savings_target": "400.00",
        },
    )
    for name, amount, category, day in (
        ("Apartment rent", "850.00", "rent", 1),
        ("Kindergarten", "180.00", "childcare", 5),
        ("Electricity and water", "95.00", "utilities", 18),
        ("Home internet", "30.00", "subscriptions", 27),
    ):
        mcp.ok(
            "add_recurring_expense",
            {
                "name": name,
                "amount": amount,
                "category": category,
                "recurrence": "monthly",
                "day_of_month": day,
                "idempotency_key": _key(),
            },
        )
    nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
    for month in (today.strftime("%Y-%m"), nxt.strftime("%Y-%m")):
        preview = mcp.ok("preview_monthly_budget", {"month": month})
        token = preview["structuredContent"]["draft_token"]
        mcp.ok("save_monthly_budget", {"draft_token": token})
    mcp.ok(
        "create_savings_goal",
        {
            "title": "Family holiday",
            "target_amount": "1200.00",
            "target_date": f"{today.year + 1}-06-30",
            "category": "travel",
            "idempotency_key": _key(),
        },
    )

    first = today.replace(day=1)

    def on(day: int) -> str:
        return (first + timedelta(days=day - 1)).isoformat()

    spending = [
        (1, "850.00", "rent", "Apartment rent"),
        (1, "38.40", "groceries", "Lidl"),
        (2, "6.80", "dining", "Coffee corner"),
        (3, "64.20", "groceries", "Kaufland"),
        (4, "18.00", "entertainment", "Cinema"),
        (5, "180.00", "childcare", "Kindergarten"),
        (6, "22.15", "groceries", "Billa"),
        (7, "55.00", "gas", "Shell"),
        (8, "12.40", "dining", "Bakery"),
        (9, "41.90", "groceries", "Lidl"),
        (10, "74.50", "dining", "Pizza Lab"),
        (11, "29.99", "shopping", "H&M"),
        (12, "16.30", "healthcare", "Pharmacy"),
        (13, "33.75", "groceries", "Kaufland"),
        (14, "7.20", "public_transport", "Metro card"),
        (15, "48.60", "groceries", "Lidl"),
        (16, "21.40", "dining", "Happy"),
        (17, "86.30", "groceries", "Kaufland"),
        (18, "95.00", "utilities", "Electricity and water"),
        (19, "9.50", "dining", "Coffee corner"),
        (20, "27.80", "groceries", "Billa"),
        (21, "52.00", "gas", "Shell"),
        (22, "14.90", "entertainment", "Streaming"),
        (23, "39.60", "groceries", "Lidl"),
    ]
    items = [
        {"amount": amount, "category": category, "date": on(day), "merchant": merchant}
        for day, amount, category, merchant in spending
        if day <= today.day
    ]
    if today.day >= 24:
        items.append(
            {
                "amount": "23.40",
                "category": "groceries",
                "date": today.isoformat(),
                "merchant": "Billa",
            }
        )
    for start in range(0, len(items), 25):
        mcp.ok(
            "add_transactions",
            {"expenses": items[start : start + 25], "idempotency_key": _key()},
        )
    previous = (first - timedelta(days=1)).replace(day=1)
    mcp.ok(
        "add_transactions",
        {
            "expenses": [
                {
                    "amount": "61.30",
                    "category": "groceries",
                    "date": (previous + timedelta(days=4)).isoformat(),
                    "merchant": "Lidl",
                },
                {
                    "amount": "24.00",
                    "category": "dining",
                    "date": (previous + timedelta(days=11)).isoformat(),
                    "merchant": "Happy",
                },
            ],
            "idempotency_key": _key(),
        },
    )


# --- the host page --------------------------------------------------------------------

HOST_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Local MCP Apps host</title>
<style>
:root{color-scheme:light;--bg:#f4f4f2;--ink:#0d0d0d;--ink2:#5d5d5a;--card:#fff;--line:rgba(0,0,0,.1)}
:root[data-theme=dark]{color-scheme:dark;--bg:#181818;--ink:#f2f2f0;--ink2:#a9a8a2;--card:#212121;--line:rgba(255,255,255,.12)}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.label{position:fixed;top:0;left:0;right:0;z-index:20;padding:4px 10px;font-size:11px;font-weight:600;letter-spacing:.02em;color:#7a6200;background:#fff4c7;text-align:center}
.chat{max-width:780px;margin:0 auto;padding:40px 16px 40px}
.user{margin:0 0 18px auto;width:fit-content;max-width:80%;padding:10px 14px;border-radius:18px;background:var(--line)}
.who{display:flex;align-items:center;gap:8px;margin:0 0 8px;font-weight:600;font-size:14px}
.who i{width:22px;height:22px;border-radius:6px;background:#193C57;display:inline-block}
.frame{border:1px solid var(--line);border-radius:18px;background:var(--card);overflow:hidden}
iframe{display:block;width:100%;border:0;background:transparent}
.after{margin-top:14px;color:var(--ink2);font-size:14px}
.fs{position:fixed;inset:0;z-index:10;background:var(--card);display:none;flex-direction:column}
.fs .bar{height:52px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:22px 16px 0;font-weight:600;border-bottom:1px solid var(--line)}
.fs .slot{flex:1;min-height:0}
.fs iframe{height:100%}
.composer{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);width:min(720px,calc(100% - 24px));padding:12px 16px;border-radius:24px;background:var(--card);border:1px solid var(--line);color:var(--ink2);box-shadow:0 8px 24px rgba(0,0,0,.12);z-index:13;display:none}
body.fullscreen .fs{display:flex}body.fullscreen .composer{display:block}body.fullscreen{overflow:hidden}
</style></head>
<body>
<div class="label">Local MCP Apps host — not ChatGPT · the component and MITA's data are real</div>
<div class="chat">
  <p class="user">Show my financial calendar for this month.</p>
  <p class="who"><i></i>MITA</p>
  <div class="frame" id="inline-slot"></div>
  <p class="after">Here is your month in MITA.</p>
</div>
<div class="fs"><div class="bar"><span>MITA</span><span aria-hidden="true">×</span></div><div class="slot" id="fs-slot"></div></div>
<div class="composer">Ask anything about your month</div>
<script>
(function(){
  var iframe = null, mode = "inline", initialized = false;
  window.__log = {requests: [], sizes: [], context: [], messages: [], links: [], downloads: [], modes: [], initialize: null, errors: []};
  function send(msg){ iframe.contentWindow.postMessage(msg, "*"); }
  function context(){
    var c = JSON.parse(JSON.stringify(window.__hostContext));
    c.displayMode = mode;
    if (mode === "fullscreen") {
      var slot = document.getElementById("fs-slot");
      c.containerDimensions = {width: slot.clientWidth, height: slot.clientHeight};
    } else {
      c.containerDimensions = {width: document.getElementById("inline-slot").clientWidth, maxHeight: window.innerHeight};
    }
    return c;
  }
  window.__mount = function(html){
    iframe = document.createElement("iframe");
    iframe.setAttribute("sandbox", "allow-scripts");
    iframe.setAttribute("title", "MITA financial calendar");
    iframe.style.height = "160px";
    iframe.srcdoc = html;
    document.getElementById("inline-slot").appendChild(iframe);
  };
  function setMode(next){
    mode = next;
    window.__log.modes.push(next);
    document.body.classList.toggle("fullscreen", next === "fullscreen");
    // Moving an iframe in the DOM reloads it; hosts keep one frame, so the
    // same frame is laid over the page instead.
    if (next === "fullscreen") {
      iframe.style.position = "fixed"; iframe.style.left = "0"; iframe.style.right = "0";
      iframe.style.top = "53px"; iframe.style.bottom = "0"; iframe.style.height = "calc(100% - 53px)"; iframe.style.zIndex = "12";
      iframe.style.background = getComputedStyle(document.body).getPropertyValue("--card");
    } else {
      iframe.style.position = ""; iframe.style.top = ""; iframe.style.bottom = ""; iframe.style.left = ""; iframe.style.right = "";
      iframe.style.zIndex = ""; iframe.style.background = "";
      var last = window.__log.sizes[window.__log.sizes.length - 1];
      if (last) iframe.style.height = last.height + "px";
    }
  }
  window.addEventListener("message", function(event){
    if (!iframe || event.source !== iframe.contentWindow) return;
    var m = event.data;
    if (!m || m.jsonrpc !== "2.0") return;
    if (m.method) window.__log.requests.push(m.method);
    var reply = function(result){ send({jsonrpc: "2.0", id: m.id, result: result}); };
    switch (m.method) {
      case "ui/initialize":
        window.__log.initialize = m.params;
        reply({protocolVersion: m.params.protocolVersion, hostInfo: {name: "mita-local-host", version: "1"},
               hostCapabilities: window.__hostCapabilities, hostContext: context()});
        return;
      case "ui/notifications/initialized":
        initialized = true;
        send({jsonrpc: "2.0", method: "ui/notifications/tool-input", params: {arguments: window.__toolInput}});
        if (window.__toolResult) send({jsonrpc: "2.0", method: "ui/notifications/tool-result", params: window.__toolResult});
        return;
      case "tools/call":
        window.mitaHost("callTool", JSON.stringify(m.params)).then(function(r){ reply(JSON.parse(r)); });
        return;
      case "ui/request-display-mode":
        setMode(m.params.mode);
        reply({mode: mode});
        send({jsonrpc: "2.0", method: "ui/notifications/host-context-changed", params: {displayMode: mode, containerDimensions: context().containerDimensions}});
        return;
      case "ui/notifications/size-changed":
        window.__log.sizes.push(m.params);
        if (mode === "inline") iframe.style.height = m.params.height + "px";
        return;
      case "ui/download-file":
        window.__log.downloads.push(m.params);
        window.mitaHost("download", JSON.stringify(m.params)).then(function(){ reply({}); });
        return;
      case "ui/update-model-context":
        window.__log.context.push(m.params); reply({}); return;
      case "ui/message":
        window.__log.messages.push(m.params); reply({}); return;
      case "ui/open-link":
        window.__log.links.push(m.params); reply({}); return;
      default:
        if (m.id !== undefined && m.method) send({jsonrpc: "2.0", id: m.id, error: {code: -32601, message: "Method not found"}});
    }
  });
  window.__deliver = function(result){ window.__toolResult = result; if (initialized) send({jsonrpc: "2.0", method: "ui/notifications/tool-result", params: result}); };
  window.__theme = function(theme){
    document.documentElement.setAttribute("data-theme", theme);
    window.__hostContext.theme = theme;
    if (initialized) send({jsonrpc: "2.0", method: "ui/notifications/host-context-changed", params: {theme: theme}});
  };
})();
</script>
</body></html>"""

HOST_CAPABILITIES = {
    "serverTools": {},
    "openLinks": {},
    "downloadFile": {},
    "updateModelContext": {"text": {}, "structuredContent": {}},
    "message": {"text": {}},
    "logging": {},
}


def view_html(widget: str) -> str:
    """The component as the sandbox loads it, under the restrictive CSP."""
    marker = '<meta charset="utf-8">'
    assert marker in widget
    return widget.replace(
        marker,
        marker + f'<meta http-equiv="Content-Security-Policy" content="{VIEW_CSP}">',
        1,
    )


# --- the browser session -----------------------------------------------------------------


class HostPage:
    def __init__(
        self,
        browser,
        mcp: McpBridge,
        widget: str,
        tool_result: dict,
        tool_input: dict,
        *,
        viewport,
        theme: str = "light",
        download_capability: bool = True,
        mobile: bool = False,
        locale: str = "en-GB",
        reduced_motion: str = "no-preference",
    ):
        options = dict(
            viewport=viewport,
            device_scale_factor=2,
            color_scheme=theme,
            reduced_motion=reduced_motion,
        )
        if mobile:
            options.update(is_mobile=True, has_touch=True)
        self.context = browser.new_context(**options)
        self.page = self.context.new_page()
        self.mcp = mcp
        self.downloads: List[bytes] = []
        self.console: List[str] = []
        self.page.on(
            "console",
            lambda msg: (
                self.console.append(f"{msg.type}: {msg.text}")
                if msg.type in ("error", "warning")
                else None
            ),
        )
        self.page.on("pageerror", lambda exc: self.console.append(f"pageerror: {exc}"))
        self.page.expose_function("mitaHost", self._host_call)
        self.page.set_content(HOST_HTML)
        capabilities = dict(HOST_CAPABILITIES)
        if not download_capability:
            capabilities.pop("downloadFile")
        self.page.evaluate(
            """([caps, ctx, input, theme]) => {
                window.__hostCapabilities = caps; window.__hostContext = ctx;
                window.__toolInput = input; document.documentElement.setAttribute('data-theme', theme);
            }""",
            [
                capabilities,
                {
                    "theme": theme,
                    "availableDisplayModes": ["inline", "fullscreen"],
                    "locale": locale,
                    "timeZone": "Europe/Sofia",
                    "platform": "mobile" if mobile else "web",
                    "deviceCapabilities": {"touch": mobile, "hover": not mobile},
                },
                tool_input,
                theme,
            ],
        )
        self.page.evaluate("(r) => window.__deliver(r)", tool_result)
        self.page.evaluate("(h) => window.__mount(h)", view_html(widget))
        self.frame = None
        for _ in range(100):
            frames = [f for f in self.page.frames if f != self.page.main_frame]
            if frames:
                self.frame = frames[0]
                break
            self.page.wait_for_timeout(50)
        check("component frame mounted", self.frame is not None)

    def _host_call(self, kind: str, payload: str) -> str:
        params = json.loads(payload)
        if kind == "callTool":
            return json.dumps(self.mcp.call(params["name"], params.get("arguments")))
        if kind == "download":
            item = params["contents"][0]["resource"]
            self.downloads.append(base64.b64decode(item["blob"]))
            return "{}"
        return "{}"

    def log(self) -> dict:
        return self.page.evaluate("() => window.__log")

    def wait_for(self, selector: str, timeout: int = 15000):
        self.frame.wait_for_selector(selector, timeout=timeout)

    def settle(self, ms: int = 350):
        self.page.wait_for_timeout(ms)

    def shot(self, out: Path, name: str, *, full: bool = False):
        path = out / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=full)
        return path

    def frame_shot(self, out: Path, name: str):
        """The fullscreen component, whole (it scrolls inside its frame)."""
        element = self.page.query_selector("iframe")
        height = self.frame.evaluate("() => document.documentElement.scrollHeight")
        viewport = self.page.viewport_size
        self.page.set_viewport_size({"width": viewport["width"], "height": height + 53})
        self.settle(250)
        path = out / f"{name}.png"
        element.screenshot(path=str(path))
        self.page.set_viewport_size(viewport)
        self.settle(150)
        return path

    def close(self):
        self.context.close()


# --- the run --------------------------------------------------------------------------------


def money_text(frame, selector: str) -> str:
    return frame.inner_text(selector).strip()


def run(args) -> None:
    base = assert_writable_target(
        args.base_url, purpose="calendar_widget_review"
    ).rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    email = f"calendar-review-{secrets.token_hex(4)}@example.com"
    password = "Review-" + secrets.token_urlsafe(12) + "9!"
    tokens = asyncio.run(connect(base, email, password, register=True))
    check("account created through the sign-up page", bool(tokens.get("access")))
    mcp = McpBridge(base, tokens["access"])
    try:
        mcp.ok("get_profile")
        today_cal = mcp.ok("get_calendar_month")["structuredContent"]
        today = date.fromisoformat(today_cal["today"])
        seed(mcp, today)
        _review(args, mcp, out, today)
    finally:
        mcp.close()
        if args.database_url:
            _delete(args.database_url, email)
    print(f"\n{len(CHECKS)} checks passed. Screenshots in {out}")


def _delete(url: str, email: str) -> None:
    import psycopg2  # local review only

    conn = psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE email = %s", (email,))
        check("review account deleted", cur.rowcount == 1)
    conn.close()


def _review(args, mcp: McpBridge, out: Path, today: date) -> None:
    month_data = mcp.ok("get_calendar_month")["structuredContent"]
    shown = mcp.ok("show_financial_calendar", {})
    view = shown["structuredContent"]
    payload = shown["_meta"]["mita/calendar"]
    check(
        "render tool: the model gets a short view, the component the month",
        "days" not in view and len(payload["month"]["days"]) == len(month_data["days"]),
    )
    check(
        "render tool and data tool agree",
        payload["month"]["summary"] == month_data["summary"] == view["summary"],
    )
    resource = mcp.resource(CALENDAR_URI)
    content = resource["contents"][0]
    check(
        "component resource is an MCP App",
        content["mimeType"] == "text/html;profile=mcp-app"
        and content["_meta"]["ui"]["csp"]
        == {"connectDomains": [], "resourceDomains": []},
    )
    widget = content["text"]
    tool_input: dict = {}
    summary = month_data["summary"]

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        webkit = p.webkit.launch()

        # 1. Inline on a phone, light and dark (WebKit: ChatGPT's iOS engine).
        for theme in ("light", "dark"):
            host = HostPage(
                webkit,
                mcp,
                widget,
                shown,
                tool_input,
                viewport={"width": 390, "height": 844},
                theme=theme,
                mobile=True,
            )
            host.wait_for(".inline")
            host.settle(500)
            hero = money_text(host.frame, ".hero-fig")
            check(
                f"inline ({theme}): the daily average is MITA's figure",
                (
                    hero.replace(",", "").endswith(summary["average_per_day"])
                    if summary["average_per_day"]
                    else True
                ),
                hero,
            )
            log = host.log()
            init = log["initialize"] or {}
            check(
                f"inline ({theme}): ui/initialize declares inline and fullscreen",
                init.get("appCapabilities", {}).get("availableDisplayModes")
                == ["inline", "fullscreen"]
                and bool(init.get("protocolVersion")),
                json.dumps(init),
            )
            check(
                f"inline ({theme}): the component reported its size",
                bool(log["sizes"]) and log["sizes"][-1]["height"] > 300,
                json.dumps(log["sizes"][-3:]),
            )
            host.shot(out, f"01-inline-phone-{theme}", full=True)
            check(
                f"inline ({theme}): no console error",
                not host.console,
                "\n".join(host.console),
            )
            host.close()

        # 2. Inline on desktop.
        host = HostPage(
            chromium,
            mcp,
            widget,
            shown,
            tool_input,
            viewport={"width": 1280, "height": 900},
        )
        host.wait_for(".inline")
        host.settle(400)
        host.shot(out, "02-inline-desktop-light", full=True)
        host.close()

        # 3. Fullscreen on a phone: open, pick an over day, filter, categories.
        host = HostPage(
            webkit,
            mcp,
            widget,
            shown,
            tool_input,
            viewport={"width": 390, "height": 844},
            mobile=True,
        )
        host.wait_for(".inline")
        host.frame.click("#open-full")
        host.wait_for(".full")
        host.settle(500)
        check(
            "fullscreen requested through ui/request-display-mode",
            host.log()["modes"] == ["fullscreen"],
        )
        host.shot(out, "03-fullscreen-phone-top")
        days = {d["date"]: d for d in payload["month"]["days"]}
        over = [d for d in payload["month"]["days"] if d["state"] == "over"]
        target = over[0]["date"] if over else payload["month"]["today"]
        host.frame.click(f'[data-date="{target}"]')
        host.wait_for("#day-detail h2")
        host.frame.wait_for_selector(".detail .rows li, .detail .note", timeout=15000)
        host.settle(800)
        label = host.frame.get_attribute(f'[data-date="{target}"]', "aria-label")
        day = days[target]
        check(
            "a date's label carries MITA's figures",
            day["spent"] is None
            or day["spent"].rstrip("0").rstrip(".") in label.replace(",", ""),
            label,
        )
        detail = host.frame.inner_text("#day-detail")
        tx = mcp.call(
            "list_transactions", {"start_date": target, "end_date": target, "limit": 50}
        )["structuredContent"]["transactions"]
        check(
            "the selected date lists that date's expenses",
            all((t.get("merchant") or t["category_label"]) in detail for t in tx),
            detail[:300],
        )
        context = host.log()["context"]
        check(
            "the selection reaches the model context",
            bool(context) and target in context[-1]["content"][0]["text"],
        )
        host.frame_shot(out, "04-fullscreen-phone-day")
        groceries = next(
            (c for c in payload["month"]["categories"] if c["category"] == "groceries"),
            None,
        )
        if groceries:
            host.frame.click('button.fchip:has-text("Groceries")')
            host.wait_for(".banner")
            host.settle(400)
            banner = host.frame.inner_text(".banner")
            check(
                "the filter shows the category's month",
                groceries["spent"] in banner.replace(",", "")
                or groceries["spent"].replace(".00", "") in banner,
                banner,
            )
            host.shot(out, "05-fullscreen-phone-filter")
            host.frame.click("#clear-filter")
            host.settle(300)
        host.frame.evaluate(
            "() => document.getElementById('bd-title').scrollIntoView()"
        )
        host.settle(300)
        host.shot(out, "06-fullscreen-phone-categories")
        # keyboard: arrows move along the dates
        host.frame.focus(f'[data-date="{target}"]')
        host.page.keyboard.press("ArrowRight")
        host.settle(200)
        moved = host.frame.evaluate(
            "() => document.activeElement && document.activeElement.dataset.date"
        )
        nxt = (date.fromisoformat(target) + timedelta(days=1)).isoformat()
        check("arrow keys move between dates", moved in (nxt, target), str(moved))
        check(
            "fullscreen (phone): no console error",
            not host.console,
            "\n".join(host.console),
        )
        host.close()

        # 4. Fullscreen desktop, light and dark; month navigation; export.
        for theme in ("light", "dark"):
            host = HostPage(
                chromium,
                mcp,
                widget,
                shown,
                tool_input,
                viewport={"width": 1280, "height": 860},
                theme=theme,
            )
            host.wait_for(".inline")
            host.frame.click("#open-full")
            host.wait_for(".full")
            host.frame.click(f'[data-date="{target}"]')
            host.frame.wait_for_selector(
                ".detail .rows li, .detail .note", timeout=15000
            )
            host.settle(800)
            host.shot(out, f"07-fullscreen-desktop-{theme}")
            if theme == "light":
                host.frame_shot(out, "08-fullscreen-desktop-whole")
                host.frame.click("#next-month")
                host.frame.wait_for_selector(
                    ".calendar[aria-busy=false]", timeout=20000
                )
                host.settle(700)
                title = host.frame.inner_text(".fhead .title")
                nxt_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
                check(
                    "next month loads through get_calendar_month",
                    nxt_month.strftime("%B") in title
                    and "get_calendar_month" in host.mcp.calls[-3:],
                    title,
                )
                host.shot(out, "09-fullscreen-desktop-next-month")
                host.frame.click("#this-month")
                host.frame.wait_for_selector(
                    ".calendar[aria-busy=false]", timeout=20000
                )
                host.settle(400)
                host.frame.click("#prev-month")
                host.frame.wait_for_selector(
                    ".calendar[aria-busy=false]", timeout=20000
                )
                host.settle(700)
                host.shot(out, "10-fullscreen-desktop-month-without-plan")
                host.frame.click("#this-month")
                host.frame.wait_for_selector(
                    ".calendar[aria-busy=false]", timeout=20000
                )
                host.settle(400)
                host.frame.click("#export")
                for _ in range(100):
                    if host.downloads:
                        break
                    host.settle(100)
                check(
                    "Save as PNG goes through ui/download-file",
                    len(host.downloads) == 1,
                )
                image = Image.open(io.BytesIO(host.downloads[0]))
                check(
                    "the image is a PNG 1080 px wide, as tall as its content",
                    image.format == "PNG"
                    and image.size[0] == 1080
                    and 1200 <= image.size[1] <= 2200,
                    str(image.size),
                )
                (out / "11-export.png").write_bytes(host.downloads[0])
                text = host.downloads[0]
                check("the image is self-contained", len(text) > 50_000)
            check(
                f"fullscreen desktop ({theme}): no console error",
                not host.console,
                "\n".join(host.console),
            )
            host.close()

        # 5. A host without ui/download-file: the image shows in place.
        host = HostPage(
            chromium,
            mcp,
            widget,
            shown,
            tool_input,
            viewport={"width": 1280, "height": 900},
            download_capability=False,
        )
        host.wait_for(".inline")
        host.frame.click("#export")
        host.wait_for("#png-preview img")
        host.settle(400)
        check("without a host download, the image is shown to keep", not host.downloads)
        host.shot(out, "12-export-fallback", full=True)
        host.close()

        # 6. Reduced motion and accessibility.
        if args.axe:
            axe_source = Path(args.axe).read_text()
            for name, engine, viewport, theme, full in (
                ("inline light", webkit, {"width": 390, "height": 844}, "light", False),
                ("inline dark", webkit, {"width": 390, "height": 844}, "dark", False),
                (
                    "fullscreen light",
                    chromium,
                    {"width": 1280, "height": 860},
                    "light",
                    True,
                ),
                (
                    "fullscreen dark",
                    chromium,
                    {"width": 1280, "height": 860},
                    "dark",
                    True,
                ),
            ):
                host = HostPage(
                    engine,
                    mcp,
                    widget,
                    shown,
                    tool_input,
                    viewport=viewport,
                    theme=theme,
                    reduced_motion="reduce",
                )
                host.wait_for(".inline")
                if full:
                    host.frame.click("#open-full")
                    host.wait_for(".full")
                    host.frame.click(f'[data-date="{target}"]')
                    host.frame.wait_for_selector(
                        ".detail .rows li, .detail .note", timeout=15000
                    )
                host.settle(400)
                host.frame.add_script_tag(content=axe_source)
                result = host.frame.evaluate(
                    """async () => { const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});
                    return r.violations.map(v => v.id + ' (' + v.impact + '): ' + v.nodes.slice(0,3).map(n => n.target.join(' ')).join(' | ')); }"""
                )
                check(
                    f"axe: no WCAG 2.2 AA violation ({name})",
                    not result,
                    "\n".join(result),
                )
                host.close()

        chromium.close()
        webkit.close()

    called = set(mcp.calls)
    check(
        "the component called read tools only",
        called
        <= {
            # the harness's own calls
            "get_profile",
            "get_calendar_month",
            "show_financial_calendar",
            "update_financial_profile",
            "add_recurring_expense",
            "preview_monthly_budget",
            "save_monthly_budget",
            "create_savings_goal",
            "add_transactions",
            # the component's
            "list_transactions",
        },
        str(called),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--axe", default="", help="path to axe.min.js (optional)")
    run(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
