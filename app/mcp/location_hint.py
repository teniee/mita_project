"""ChatGPT's approximate location, reduced to what MITA may use: a country.

OpenAI's plugin reference lists ``_meta["openai/userLocation"]`` as a "coarse
location hint (``city``, ``region``, ``country``, ``timezone``,
``longitude``, ``latitude``)" sent with tool calls; servers "should never
rely on them for authorization decisions and must tolerate their absence".
Where someone is right now is not where they usually live and spend money,
so MITA treats the hint as a question to ask, never as a fact:

* only ``country`` is read, and only when it is an ISO 3166-1 alpha-2 code
  (or a country's English name) MITA knows — city, region and coordinates
  are dropped here and never reach a tool body, a log, analytics or a result;
* it lives only for the current call (a context variable bound by the
  runtime around the tool body);
* ``get_setup_status`` offers it as a suggestion and
  ``update_financial_profile`` records whether the country the user
  confirmed is the suggested one (``chatgpt_location_confirmed``).
"""

from __future__ import annotations

import contextvars
from typing import Any, Mapping, Optional

from app.mcp.countries import COUNTRIES, country_code

META_KEY = "openai/userLocation"

_NAMES = {name.casefold(): code for code, name in COUNTRIES.items()}

_current: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "mita_location_hint_country", default=None
)


def country_from_meta(meta: Mapping[str, Any]) -> Optional[str]:
    """The hint's country as an ISO code, or None (absent, malformed, unknown)."""
    raw = meta.get(META_KEY) if isinstance(meta, Mapping) else None
    if not isinstance(raw, Mapping):
        return None
    value = raw.get("country")
    if not isinstance(value, str) or not 0 < len(value) <= 64:
        return None
    return country_code(value) or _NAMES.get(" ".join(value.split()).casefold())


def bind(country: Optional[str]) -> contextvars.Token:
    return _current.set(country)


def unbind(token: contextvars.Token) -> None:
    _current.reset(token)


def current_country() -> Optional[str]:
    """The country of ChatGPT's approximate location for this call, if any."""
    return _current.get()
