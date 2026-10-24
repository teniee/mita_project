"""MITA's UI components for ChatGPT (MCP Apps, ``io.modelcontextprotocol/ui``).

One component: the financial calendar (``financial_calendar.html``), a single
HTML document with its own CSS and script, rendered by the host in a
sandboxed iframe. Rules (docs/chatgpt-app/financial-calendar.md):

* **It loads nothing and connects nowhere.** The resource declares an empty
  CSP allowlist, so the host's restrictive default applies (no network, no
  third-party assets). Data reaches it only from tool results the host
  delivers, and it asks for more only by calling MITA's own read tools
  through the host (``tools/call``).
* **It writes nothing.** The component calls read tools only; there is no
  write tool it can reach and no form that submits anywhere.
* **Untrusted input.** Every value from a tool result is set as text, never
  parsed as HTML.
* **The URI is the cache key.** Bump the ``-vN`` suffix for a breaking change
  to the component, so no host serves a stale template to new tool results.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from mcp.server.apps import APP_MIME_TYPE, Apps
from mcp.server.mcpserver.resources import TextResource

from app.mcp.config import McpSettings

CALENDAR_URI = "ui://mita/financial-calendar-v1.html"
CALENDAR_FILE = Path(__file__).with_name("financial_calendar.html")
DISPLAY_MODES = ("inline", "fullscreen")

# ChatGPT reads this when the component loads, so it does not narrate what is
# already on screen.
CALENDAR_DESCRIPTION = (
    "MITA's financial calendar for one month of the signed-in user's own account is "
    "on screen: each date's plan and recorded spending, saved bills, the categories "
    "and the month's summary. The user can pick a date, filter by category, change "
    "month and save an image. Do not repeat every figure; answer the user's questions "
    "with MITA's tools."
)


@lru_cache(maxsize=1)
def calendar_html() -> str:
    return CALENDAR_FILE.read_text(encoding="utf-8")


def calendar_resource_meta(settings: McpSettings) -> Dict[str, Any]:
    ui: Dict[str, Any] = {
        "prefersBorder": True,
        # Declared empty on purpose: no fetch/XHR and no external asset.
        "csp": {"connectDomains": [], "resourceDomains": []},
    }
    if settings.widget_domain:
        ui["domain"] = settings.widget_domain
    return {
        "ui": ui,
        "openai/ui": {"availableDisplayModes": list(DISPLAY_MODES)},
        "openai/widgetDescription": CALENDAR_DESCRIPTION,
    }


def apps_extension(settings: McpSettings) -> Apps:
    """The MCP Apps extension with MITA's component templates; passed to the
    server at construction, which also advertises the extension."""
    apps = Apps()
    apps.add_resource(
        TextResource(
            uri=CALENDAR_URI,
            name="mita-financial-calendar",
            title="MITA financial calendar",
            description=CALENDAR_DESCRIPTION,
            mime_type=APP_MIME_TYPE,
            meta=calendar_resource_meta(settings),
            text=calendar_html(),
        )
    )
    return apps


def render_tool_meta(**extra: Any) -> Dict[str, Any]:
    """``_meta`` keys that bind a render tool to the calendar component: the
    MCP Apps field and ChatGPT's compatibility alias for older clients."""
    return {
        "ui": {"resourceUri": CALENDAR_URI},
        "openai/outputTemplate": CALENDAR_URI,
        **extra,
    }


def component_callable_meta(**extra: Any) -> Dict[str, Any]:
    """``_meta`` for a data tool the component may call through the host
    (visible to both the model and the component; ChatGPT's legacy flag too)."""
    return {
        "ui": {"visibility": ["model", "app"]},
        "openai/widgetAccessible": True,
        **extra,
    }
