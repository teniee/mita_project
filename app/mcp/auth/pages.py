"""What a person sees during the ChatGPT connection: MITA's sign-in /
sign-up / consent page and its error pages.

Presentation only. ``login.py`` owns the flow (CSRF, lockout, rate limits,
sign-up rules, code issuance) and hands this module values it has already
validated; ``browser_errors.py`` uses ``problem_page`` for the authorization
endpoint. Rules:

* **No JavaScript.** No ``<script>``, no inline handlers; the CSP has no
  ``script-src`` (docs/chatgpt-app/oauth-security-audit.md, XSS row). Motion
  is CSS and stops under ``prefers-reduced-motion``; the permission details
  are a native ``<details>``.
* **Nothing third-party.** Fonts and the favicon come from this service
  (``/oauth/assets/``); the logo is the master vector from the MITA Brand
  Guidelines (Figma), inlined. Brand values: docs/brand/AUTH-UI-DESIGN.md.
* **Every dynamic value is escaped** with ``html.escape`` at the point of use.
* **Copy states facts only** (docs/chatgpt-app/data-inventory.md): MITA keeps
  structured financial records, never conversations or receipt images, and
  cannot move money. Demo figures are fictional, labelled as such, and are
  what MITA's forecast engine returns for them (``PaceDay``).
* **Mobile first.** The base styles are the phone layout (ChatGPT opens this
  page in its in-app browser); wider screens add columns to the same order.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple
from urllib.parse import urlencode, urlparse

from app.core.password_policy import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.mcp.auth.scopes import SCOPE_DESCRIPTIONS, SCOPE_TITLES

e = html.escape

LOGIN_PATH = "/oauth/login"
ASSET_PREFIX = "/oauth/assets/"
STATIC_DIR = Path(__file__).with_name("static")
REGISTER = "register"
# Longest e-mail or sign-in password accepted; login.py truncates to it.
MAX_FIELD = 320

# Shown under the new-password field. Each line is one check of
# app/core/password_policy.py; tests_mcp/test_auth_ui.py holds them together.
PASSWORD_RULES: Tuple[str, ...] = (
    f"At least {MIN_PASSWORD_LENGTH} characters",
    "Upper- and lower-case letters",
    "At least one number",
    "At least one symbol",
)
# Safari's password generator reads this; same four checks.
PASSWORD_RULES_ATTR = (
    f"minlength: {MIN_PASSWORD_LENGTH}; maxlength: {MAX_PASSWORD_LENGTH}; "
    "required: lower; required: upper; required: digit; required: special;"
)

USAGE_STATS_LABEL = (
    "Help improve MITA: record which features I use. MITA never records my "
    "conversations, amounts or merchant names. I can turn this off anytime."
)
CANNOT_MOVE_MONEY = (
    "MITA cannot move money, make payments or connect to your bank, and it "
    "cannot buy investments or crypto."
)
# The visible line of the consent box; the full sentence is in its details.
CANNOT_MOVE_MONEY_SHORT = "MITA can’t move money or access banks."
FORGERY_WARNING_LEAD = (
    "Only continue if you just chose to connect MITA in your own ChatGPT account."
)
FORGERY_WARNING = (
    "If someone sent you this link, press Cancel — approving it could give "
    "their ChatGPT access to your MITA data."
)
# A database or network failure during sign-in. True in every case it covers:
# no code was issued, whatever was saved before the failure.
UNAVAILABLE_TITLE = "MITA is temporarily unavailable"
UNAVAILABLE = "ChatGPT was not connected. Please try again in a moment."


# --- static assets ------------------------------------------------------------

_CONTENT_TYPES = {".woff2": "font/woff2", ".svg": "image/svg+xml"}


class AssetCatalog:
    """The files under ``static/`` the pages reference, read once and served
    by exact name only — a request can never name a path on disk."""

    def __init__(self, files: Dict[str, Tuple[bytes, str]]) -> None:
        self._files = dict(files)
        self._versions = {
            name: hashlib.sha256(data).hexdigest()[:12]
            for name, (data, _) in self._files.items()
        }

    @classmethod
    def load(cls, root: Path = STATIC_DIR) -> "AssetCatalog":
        files: Dict[str, Tuple[bytes, str]] = {}
        for path in sorted(root.rglob("*")):
            content_type = _CONTENT_TYPES.get(path.suffix)
            if not path.is_file() or content_type is None:
                continue
            if path.name in files:
                raise ValueError(f"duplicate asset name {path.name}")
            files[path.name] = (path.read_bytes(), content_type)
        return cls(files)

    def names(self) -> Tuple[str, ...]:
        return tuple(self._files)

    def get(self, name: str) -> Optional[Tuple[bytes, str]]:
        return self._files.get(name)

    def url(self, name: str) -> str:
        # Versioned by content: the response is cached as immutable.
        return f"{ASSET_PREFIX}{name}?v={self._versions[name]}"


ASSETS = AssetCatalog.load()


# --- headers --------------------------------------------------------------------


def security_headers(redirect_uri: Optional[str] = None) -> Dict[str, str]:
    """The headers every page here is sent with. ``form-action`` names the
    client's redirect origin only while a consent form is on screen."""
    form_action = "'self'"
    if redirect_uri:
        parsed = urlparse(redirect_uri)
        form_action += f" {parsed.scheme}://{parsed.netloc}"
    return {
        "Content-Security-Policy": (
            "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
            f"font-src 'self'; form-action {form_action}; frame-ancestors 'none'; "
            "base-uri 'none'"
        ),
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
    }


# --- brand ----------------------------------------------------------------------

# Master vectors from the MITA Brand Guidelines (Figma file
# 512WdjnhPJXM8jeHKcg4g8, "Logo Variants": logomark 2011:206, wordmark
# 2011:212 — Manrope ExtraBold, outlined). "Always use master files": these
# paths are the export, unedited.
_MARK_PATHS = (
    '<path fill="#6B73FF" d="M53.8103 34.5945L58.6007 27.9983C61.2338 24.3741 59.9143 19.5591 55.6717 17.3092C51.4291 15.0593 45.7949 16.1862 43.1618 19.8104L38.3714 26.4066L53.8083 34.5925L53.8103 34.5945ZM55.6737 17.3112C59.9163 19.5611 65.5464 18.4401 68.1835 14.81L72.97 8.22177L57.5331 0.0359039L52.7426 6.63007C50.1095 10.2543 51.4331 15.0633 55.6757 17.3132L55.6737 17.3112Z"/>'
    '<path fill="#F44336" d="M0 34.6284H8.67913C13.1077 34.6284 17.3583 30.7269 17.3583 25.9698C17.3583 30.7289 21.269 34.6284 26.0374 34.6284H34.7165V0H26.0374C21.267 0 17.3583 3.89945 17.3583 8.65859C17.3583 3.89945 13.4556 0 8.67913 0H0V34.6284ZM26.0314 17.3112C21.261 17.3112 17.3523 21.2126 17.3523 25.9698C17.3523 21.2106 13.4496 17.3112 8.67314 17.3112H26.0314Z"/>'
    '<path fill="#14B8A6" d="M6.14731e-05 36.3637V53.6828H8.68319V71H26.0435V53.6828H8.68319C13.5296 53.6828 17.3663 49.7555 17.3663 44.9445C17.3663 49.7136 21.279 53.607 26.0495 53.607H34.7326V36.2799C23.1204 36.2799 11.6342 36.3617 0.00605949 36.3617H-0.00193787L6.14731e-05 36.3637Z"/>'
    '<path fill="#FFD25F" d="M55.6837 62.2477V70.8903H72.9999V62.2477C72.9999 57.4985 69.1052 53.605 64.3368 53.605C69.0972 53.605 72.9999 49.7195 72.9999 44.9624V36.3278H47.0205C42.2601 36.3278 38.3574 40.2212 38.3574 44.9704V70.8883H47.0205C51.781 70.8883 55.6837 66.9948 55.6837 62.2457V62.2477ZM47.0205 53.605C51.781 53.605 55.6837 49.7195 55.6837 44.9624C55.6837 49.7116 59.5784 53.605 64.3468 53.605C59.5864 53.605 55.6837 57.4985 55.6837 62.2477C55.6837 57.4985 51.781 53.605 47.0205 53.605Z"/>'
)
_WORDMARK_PATH = '<path fill="#193C57" d="M6.33299e-07 56.595V1.155H9.394L27.72 37.961L46.046 1.155H55.44V56.595H45.661V23.485L29.568 56.595H25.872L9.779 23.485V56.595H6.33299e-07ZM65.4771 9.24V1.19209e-07H75.9491V9.24H65.4771ZM65.4771 56.595V15.015H75.9491V56.595H65.4771ZM110.899 56.595C108.025 57.134 105.201 57.365 102.429 57.288C99.6829 57.2367 97.2189 56.7618 95.0372 55.8635C92.8812 54.9395 91.2386 53.4637 90.1092 51.436C89.0826 49.5367 88.5436 47.6117 88.4922 45.661C88.4409 43.6847 88.4152 41.4517 88.4152 38.962V3.465H98.8872V38.346C98.8872 39.963 98.9001 41.426 98.9257 42.735C98.9771 44.0183 99.2466 45.045 99.7342 45.815C100.658 47.278 102.134 48.0737 104.162 48.202C106.189 48.3303 108.435 48.2277 110.899 47.894V56.595ZM81.3312 23.1V15.015H110.899V23.1H81.3312ZM130.175 57.75C127.198 57.75 124.67 57.1853 122.591 56.056C120.537 54.901 118.972 53.3738 117.894 51.4745C116.841 49.5495 116.315 47.432 116.315 45.122C116.315 43.197 116.61 41.4388 117.201 39.8475C117.791 38.2562 118.741 36.8573 120.05 35.651C121.384 34.419 123.168 33.3923 125.401 32.571C126.941 32.0063 128.776 31.5058 130.907 31.0695C133.037 30.6332 135.45 30.2225 138.145 29.8375C140.84 29.4268 143.804 28.9777 147.038 28.49L143.265 30.569C143.265 28.105 142.675 26.2955 141.494 25.1405C140.313 23.9855 138.337 23.408 135.565 23.408C134.025 23.408 132.421 23.7802 130.753 24.5245C129.084 25.2688 127.916 26.5907 127.249 28.49L117.778 25.487C118.83 22.0477 120.807 19.25 123.707 17.094C126.607 14.938 130.56 13.86 135.565 13.86C139.235 13.86 142.495 14.4247 145.344 15.554C148.193 16.6833 150.349 18.634 151.812 21.406C152.633 22.946 153.121 24.486 153.275 26.026C153.429 27.566 153.506 29.2857 153.506 31.185V56.595H144.343V48.048L145.652 49.819C143.624 52.6167 141.43 54.6443 139.069 55.902C136.733 57.134 133.768 57.75 130.175 57.75ZM132.408 49.511C134.333 49.511 135.95 49.1773 137.259 48.51C138.594 47.817 139.646 47.0342 140.416 46.1615C141.212 45.2888 141.751 44.5573 142.033 43.967C142.572 42.8377 142.88 41.5287 142.957 40.04C143.06 38.5257 143.111 37.268 143.111 36.267L146.191 37.037C143.085 37.5503 140.57 37.9867 138.645 38.346C136.72 38.6797 135.167 38.9877 133.987 39.27C132.806 39.5523 131.766 39.8603 130.868 40.194C129.841 40.6047 129.007 41.0538 128.366 41.5415C127.75 42.0035 127.288 42.5168 126.98 43.0815C126.697 43.6462 126.556 44.275 126.556 44.968C126.556 45.9177 126.787 46.739 127.249 47.432C127.737 48.0993 128.417 48.6127 129.29 48.972C130.162 49.3313 131.202 49.511 132.408 49.511Z"/>'


def logo_lockup(css_class: str = "logo") -> str:
    """Mark + wordmark at the master lockup's spacing (wordmark glyphs at
    +92.39/+14.4 from the mark, baseline on the mark's bottom edge)."""
    return (
        f'<svg class="{css_class}" viewBox="0 0 246 73" role="img" aria-label="MITA">'
        f"{_MARK_PATHS}"
        f'<g transform="translate(92.39 14.4)">{_WORDMARK_PATH}</g></svg>'
    )


def logo_mark(css_class: str = "mark") -> str:
    return (
        f'<svg class="{css_class}" viewBox="0 0 73 71" aria-hidden="true" '
        f'focusable="false">{_MARK_PATHS}</svg>'
    )


_ICONS = {
    "check": '<path d="M5 12.5l4.2 4.2L19 7"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8.2 12.3l2.6 2.6 5-5.2"/>',
    "ban": '<circle cx="12" cy="12" r="9"/><path d="M5.7 5.7l12.6 12.6"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "chart": '<path d="M5 20V11M12 20V5M19 20v-6"/>',
    "calendar": '<rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M4 10h16M9 3v4M15 3v4"/>',
    "shield": '<path d="M12 3l7 3v5c0 4.6-3 8.4-7 10-4-1.6-7-5.4-7-10V6z"/><path d="M9 12l2.2 2.2L15.5 10"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.6h.01"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.4h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    "return": '<path d="M9 14l-4-4 4-4"/><path d="M5 10h9.5a4.5 4.5 0 0 1 0 9H12"/>',
    "database": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.66 3.13 3 7 3s7-1.34 7-3V6"/><path d="M5 12v6c0 1.66 3.13 3 7 3s7-1.34 7-3v-6"/>',
    "pause": '<path d="M9 6v12M15 6v12"/>',
}


def icon(name: str, css_class: str = "i") -> str:
    return (
        f'<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{_ICONS[name]}</svg>'
    )


# --- product story (facts only; demo figures are fictional) -----------------------

# The example month. Fictional figures, as MITA's forecast engine
# (budget_forecast_engine.compute_forecast, i.e. get_budget_forecast) returns
# them for a 2,325.00 plan that sets 400.00 aside as Savings: today counts as
# elapsed, "days left" are the days after today, and the amount per day is
# what is left of the plan, minus the savings, divided by those days — one
# amount for every remaining day, not a separate budget per date.
# tests_mcp/test_auth_ui.py recomputes each figure with it. The forecast's
# status (on track / warning / danger) is deliberately not shown: its linear
# pace counts rent paid on the 1st as daily spending, so it can mislead until
# the forecast model is fixed (docs/brand/AUTH-UI-DESIGN.md).
DEMO_MONTH = "October"
DEMO_DAYS_IN_MONTH = 31
DEMO_FIRST_WEEKDAY = 3  # 1 October falls on a Thursday (Monday = 0), as in 2026
DEMO_PLANNED = "2,325.00"  # total_planned
DEMO_SAVINGS = "400.00"  # the plan's Savings line: savings_set_aside
WEEKDAY_LETTERS = ("M", "T", "W", "T", "F", "S", "S")


@dataclass(frozen=True)
class PaceDay:
    """One day of the example month, in get_budget_forecast's terms."""

    day: int  # day of the month (days_elapsed)
    weekday: str
    spent: str  # total_spent, today included
    left: str  # remaining_budget (the whole plan, savings included)
    spendable: str  # remaining_budget - savings_set_aside
    per_day: str  # safe_daily_limit = spendable / days_left
    days_left: int  # days_remaining


MONDAY = PaceDay(19, "Monday", "1,124.60", "1,200.40", "800.40", "66.70", 12)
FRIDAY = PaceDay(23, "Friday", "1,342.20", "982.80", "582.80", "72.85", 8)

# The question the page leads with, and the examples under "Try asking".
# Each is answered by a published tool (tests_mcp/test_auth_ui.PROMPT_TOOLS).
PACE_QUESTION = "How much can I safely spend per day?"
PROMPTS: Tuple[Tuple[str, str], ...] = (
    ("teal", PACE_QUESTION),
    ("yellow", "Help me build my monthly budget."),
    ("red", "I spent €36.80 on groceries today."),
    ("red", "Add the expenses from this receipt to MITA."),
    ("yellow", "How am I doing against my budget?"),
    ("purple", "Create an Emergency Fund goal for €3,000."),
    ("purple", "How has my spending changed over the last six months?"),
)

STEPS: Tuple[Tuple[str, str, str], ...] = (
    ("red", "Connect MITA", "Sign in or create your MITA account on this page."),
    (
        "purple",
        "Talk naturally",
        "Tell ChatGPT what you spent, what you earn and what you are planning.",
    ),
    (
        "teal",
        "MITA keeps the records",
        "Saved as structured data in your MITA account, so ChatGPT can use them in a new conversation.",
    ),
)

TRUST: Tuple[Tuple[str, str, str], ...] = (
    (
        "ban",
        "Can’t move money",
        "No payments, transfers or trades, and no connection to your bank.",
    ),
    (
        "receipt",
        "Receipt photos stay in ChatGPT",
        "ChatGPT reads the photo; MITA saves only the date, amount, category and merchant — never the image.",
    ),
    (
        "user",
        "Only your account",
        "ChatGPT works with the MITA account you connect here. Disconnect it in ChatGPT at any time; changing your MITA password also ends its access.",
    ),
    (
        "chart",
        "Usage statistics are optional",
        "Untick the box to opt out, or ask ChatGPT to turn them off later — that deletes the usage events linked to you.",
    ),
)


# --- styles ---------------------------------------------------------------------

# Mobile first: everything up to the first @media is the phone layout. From
# 1040 px the sign-in card is a right-hand column that starts level with the
# logo (the bar keeps only the lockup), so its button fits a 1280×800 screen.
_CSS = """
:root{--navy:#193C57;--navy-2:#2B5876;--yellow:#FFD25F;--red:#F44336;--teal:#14B8A6;--purple:#6B73FF;--cream:#FFF9F0;
--ink:#193C57;--ink-2:#4C6679;--surface:#FFFFFF;--line:rgba(25,60,87,.14);--line-2:rgba(25,60,87,.24);--field:#7A8E9E;
--error:#BA1A1A;--error-bg:#FEECEB;--notice:rgba(255,210,95,.31);
--t-red:#FDE1DF;--t-purple:#E4E6FF;--t-teal:#D5F2EF;--t-yellow:#FFF1CD;--past:rgba(25,60,87,.07);
--r-m:16px;--r-l:24px;--pill:999px;
--shadow-s:0 1px 2px rgba(25,60,87,.06);--shadow:0 1px 2px rgba(25,60,87,.06),0 16px 40px rgba(25,60,87,.10);
--ui:"Manrope",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
--display:"Sora","Manrope",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
--mono:"Space Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color-scheme:light}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;min-height:100vh;color:var(--ink);font:400 1rem/1.55 var(--ui);-webkit-font-smoothing:antialiased;
background-color:var(--cream);background-image:radial-gradient(52rem 34rem at 0% -6%,rgba(255,210,95,.30),transparent 62%),radial-gradient(44rem 30rem at 100% 0%,rgba(107,115,255,.10),transparent 62%),radial-gradient(rgba(25,60,87,.06) 1px,transparent 1.4px);
background-size:auto,auto,22px 22px;background-repeat:no-repeat,no-repeat,repeat}
a{color:var(--ink)}
p,h1,h2,h3,ul,ol,dl,dd,figure{margin:0}
.vh{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.i{width:20px;height:20px;flex:none}
.page{max-width:1200px;margin:0 auto;padding:12px 16px 32px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:560px;margin:0 auto 12px}
.brand{display:flex;align-items:center}
.logo{display:block;height:26px;width:auto}
.tag{font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);padding:6px 9px;border:1px solid var(--line-2);border-radius:var(--pill);background:rgba(255,255,255,.6);white-space:nowrap}
.layout{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"hero" "auth" "story" "ask" "how" "trust";gap:20px;max-width:560px;margin:0 auto}
.hero{grid-area:hero}.auth{grid-area:auth}.story{grid-area:story}.ask{grid-area:ask}.how{grid-area:how}.trust{grid-area:trust}
.hero h1{font:700 clamp(1.75rem,1.15rem + 2.6vw,3.35rem)/1.08 var(--display);letter-spacing:-.025em;text-wrap:balance}
.hl{background:linear-gradient(transparent 62%,rgba(255,210,95,.9) 62%,rgba(255,210,95,.9) 92%,transparent 92%);padding:0 .05em;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.lede{margin-top:8px;max-width:34rem;font-size:.9375rem;line-height:1.5;color:var(--ink-2);text-wrap:pretty}
.example{padding:3px 7px;border:1px solid var(--line-2);border-radius:var(--pill);font:700 .5625rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
.bubble{margin:0 0 6px auto;max-width:88%;width:fit-content;padding:6px 12px;border-radius:16px 16px 5px 16px;background:var(--navy);color:#fff;font-weight:500;font-size:.875rem;line-height:1.4}
.reply{display:grid;grid-template-columns:28px minmax(0,1fr);gap:8px;align-items:start}
.avatar{width:28px;height:28px;border-radius:9px;display:grid;place-items:center;background:var(--surface);border:1px solid var(--line)}
.avatar .mark{width:17px;height:17px}
.teaser{margin-top:10px;padding:10px 12px 11px;border-radius:20px;background:rgba(255,255,255,.88);border:1px solid var(--line);box-shadow:var(--shadow)}
.sum{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px}
.fig{font:700 1.5rem/1.1 var(--mono);letter-spacing:-.02em}
.per{font-weight:700;font-size:.875rem}
.sum .example{margin-left:auto;align-self:center}
.meta{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:1px;font-size:.8125rem;line-height:1.4;color:var(--ink-2)}
.strip{display:grid;grid-template-columns:repeat(31,minmax(0,1fr));gap:2px;align-items:center;margin-top:8px}
.strip i{height:8px;border-radius:2px;background:rgba(25,60,87,.16)}
.strip .t{height:14px;background:var(--navy);box-shadow:0 0 0 1.5px var(--yellow)}
.strip .f{background:var(--teal)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-l);box-shadow:var(--shadow)}
.auth-card{padding:14px 16px 20px}
.auth-card h2{font:700 1.25rem/1.25 var(--display);letter-spacing:-.015em}
.sub{margin-top:4px;color:var(--ink-2);font-size:.875rem;line-height:1.45}
.tabs{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:10px 0 0;padding:4px;border-radius:var(--pill);background:rgba(25,60,87,.06)}
.tabs a{display:flex;align-items:center;justify-content:center;min-height:40px;border-radius:var(--pill);font-weight:700;font-size:.9375rem;color:var(--ink-2);text-decoration:none}
.tabs a:hover{color:var(--ink)}
.tabs a[aria-current=page]{background:var(--surface);color:var(--ink);box-shadow:0 1px 3px rgba(25,60,87,.14),0 0 0 1px var(--line)}
.alert{display:flex;gap:10px;align-items:flex-start;margin-top:14px;padding:12px 14px;border-radius:14px;background:var(--error-bg);border:1px solid rgba(244,67,54,.4);color:var(--error);font-weight:600;font-size:.9375rem;line-height:1.45}
.alert .i{margin-top:1px}
.field{margin-top:10px}
.field label{display:block;margin-bottom:4px;font-weight:700;font-size:.875rem}
.input{display:block;width:100%;min-height:48px;padding:11px 14px;border:1px solid var(--field);border-radius:14px;background:var(--surface);color:var(--ink);font:500 1rem/1.4 var(--ui)}
.input:hover{border-color:var(--navy-2)}
.input:focus{outline:3px solid var(--purple);outline-offset:1px;border-color:var(--navy)}
.input[aria-invalid=true]{border:2px solid var(--error);padding:10px 13px}
.rules{list-style:none;padding:0;margin-top:8px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:3px 12px;font-size:.8125rem;color:var(--ink-2)}
.rules li{display:flex;align-items:center;gap:7px}
.rules li::before{content:"";width:6px;height:6px;border-radius:2px;background:var(--teal);flex:none}
.consent{margin-top:12px;padding:11px 12px;border-radius:var(--r-m);background:var(--cream);border:1px solid var(--line)}
.consent h3{margin-bottom:6px;font:700 .875rem/1.3 var(--ui)}
.scopes{list-style:none;padding:0;display:grid;gap:4px}
.scopes li{display:grid;grid-template-columns:18px minmax(0,1fr);gap:8px;align-items:start;font-weight:600;font-size:.8125rem;line-height:1.35}
.scopes .i{width:18px;height:18px;color:var(--teal)}
.limits{display:grid;grid-template-columns:18px minmax(0,1fr);gap:8px;align-items:start;margin-top:8px;padding-top:8px;border-top:1px dashed var(--line-2);font-weight:600;font-size:.8125rem;line-height:1.35}
.limits .i{width:18px;height:18px}
.perm{margin-top:6px;font-size:.8125rem}
.perm summary{display:inline-flex;align-items:center;gap:7px;min-height:24px;cursor:pointer;font-weight:700;list-style:none;text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px;text-decoration-color:var(--yellow)}
.perm summary::-webkit-details-marker{display:none}
.perm summary::after{content:"";width:6px;height:6px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:translateY(-2px) rotate(45deg)}
.perm[open] summary::after{transform:translateY(1px) rotate(-135deg)}
.perm dl{display:grid;gap:7px;margin-top:8px}
.perm dt{font-weight:700}
.perm dd{margin-top:1px;line-height:1.45;color:var(--ink-2)}
.perm .money{margin-top:8px;line-height:1.45;color:var(--ink-2)}
.check{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;align-items:start;margin-top:10px;font-size:.78125rem;line-height:1.45;color:var(--ink-2);cursor:pointer}
.check input{width:18px;height:18px;margin:1px 0 0;accent-color:var(--navy)}
.actions{display:grid;gap:8px;margin-top:12px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:12px 22px;border-radius:var(--pill);border:1px solid transparent;font:700 1rem/1.2 var(--ui);text-decoration:none;cursor:pointer;transition:background-color .15s ease,box-shadow .15s ease,transform .15s ease}
.btn-primary{min-height:52px;background:var(--navy);color:var(--yellow);box-shadow:0 6px 18px rgba(25,60,87,.24)}
.btn-primary:hover{background:var(--navy-2)}
.btn-primary:active{transform:translateY(1px);box-shadow:0 2px 8px rgba(25,60,87,.24)}
.btn-quiet{min-height:44px;background:transparent;color:var(--ink);border-color:var(--line-2)}
.btn-quiet:hover{background:rgba(25,60,87,.05)}
.btn:focus-visible,.tabs a:focus-visible,a:focus-visible,.check input:focus-visible,.perm summary:focus-visible{outline:3px solid var(--purple);outline-offset:2px}
.return{display:flex;justify-content:center;gap:8px;margin-top:12px;font-size:.8125rem;line-height:1.5;color:var(--ink-2);text-align:center}
.return .i{width:16px;height:16px;margin-top:2px}
.notice{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;margin-top:14px;padding:12px 14px;border-radius:14px;background:var(--notice);font-size:.8125rem;line-height:1.5}
.switch{margin-top:16px;text-align:center;font-size:.9375rem;color:var(--ink-2)}
.switch a,.help a{font-weight:700;text-decoration-thickness:2px;text-underline-offset:3px;text-decoration-color:var(--yellow)}
.help{margin-top:8px;text-align:center;font-size:.8125rem;color:var(--ink-2)}
.section-title{font:700 1.25rem/1.25 var(--display);letter-spacing:-.012em}
.section-lede{margin-top:4px;font-size:.9375rem;color:var(--ink-2)}
.story-fig{margin-top:14px}
.convo{padding:14px 12px;border-radius:22px;background:rgba(255,255,255,.82);border:1px solid var(--line);box-shadow:var(--shadow)}
.convo-label{display:flex;align-items:center;justify-content:space-between;gap:8px;font:700 .6875rem/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.stage{display:flex;align-items:center;gap:7px;margin:18px 0 8px;font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.stage::before{content:"";width:8px;height:8px;border-radius:2px;background:var(--k)}
.result{padding:12px;border-radius:16px;background:var(--surface);border:1px solid var(--line)}
.result-head{display:flex;align-items:center;gap:8px;font-weight:700;font-size:.9375rem;line-height:1.3}
.result-head .i{width:18px;height:18px;color:var(--teal)}
.result-src{margin-left:auto;font:700 .625rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px}
.chip{padding:4px 10px;border-radius:var(--pill);background:var(--cream);border:1px solid var(--line);font-size:.8125rem;font-weight:600}
.amount{margin-left:auto;font:700 1.0625rem/1.2 var(--mono)}
.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
.figures dt{font-size:.75rem;color:var(--ink-2)}
.figures dd{margin-top:2px;font:700 .8125rem/1.2 var(--mono);white-space:nowrap}
.meter{height:8px;margin-top:12px;border-radius:var(--pill);background:rgba(25,60,87,.08);overflow:hidden}
.meter span{display:block;height:100%;width:var(--w);border-radius:inherit;background:var(--teal);transform-origin:left center}
.meter-note{margin-top:6px;font-size:.75rem;color:var(--ink-2)}
.pace-grid{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"sum" "cal" "key";gap:12px;margin-top:10px}
.pace-sum{grid-area:sum}.cal{grid-area:cal}.key{grid-area:key}
.pace .fig{font-size:1.75rem}
.cal{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px;max-width:300px}
.cal span{display:flex;align-items:center;justify-content:center;aspect-ratio:1;border-radius:8px;font:700 .75rem/1 var(--mono)}
.cal .h{aspect-ratio:auto;padding:2px 0 3px;font-size:.625rem;color:var(--ink-2)}
.cal .p{background:var(--past);color:var(--ink-2)}
.cal .t{background:var(--navy);color:var(--yellow);box-shadow:0 0 0 2px var(--surface),0 0 0 4px var(--yellow)}
.cal .f{background:var(--t-teal);color:var(--ink);box-shadow:inset 0 -3px 0 var(--teal)}
.key ul{display:grid;gap:7px;list-style:none;padding:0;font-size:.8125rem;line-height:1.35}
.key li{display:grid;grid-template-columns:14px minmax(0,1fr) auto;gap:8px;align-items:center}
.key li::before{content:"";width:14px;height:14px;border-radius:4px;background:var(--sw);box-shadow:var(--sw-x,none)}
.key b{font:700 .8125rem/1.2 var(--mono);white-space:nowrap}
.sw-p{--sw:var(--past);--sw-x:inset 0 0 0 1px var(--line-2)}.sw-t{--sw:var(--navy);--sw-x:inset 0 0 0 2px var(--yellow)}.sw-f{--sw:var(--t-teal);--sw-x:inset 0 -3px 0 var(--teal)}
.calc{margin-top:10px;padding-top:9px;border-top:1px dashed var(--line-2);font:400 .75rem/1.55 var(--mono);color:var(--ink-2)}
.kept{display:grid;grid-template-columns:16px minmax(0,1fr);gap:8px;align-items:start;margin-top:10px;padding:8px 10px;border-radius:12px;background:var(--t-teal);font-weight:600;font-size:.78125rem;line-height:1.4}
.kept .i{width:16px;height:16px;margin-top:1px}
.memory{display:flex;align-items:center;gap:10px;margin:2px 0 2px 24px;padding:10px 0;font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.memory::before{content:"";align-self:stretch;width:2px;min-height:26px;background:repeating-linear-gradient(var(--line-2) 0 4px,transparent 4px 8px)}
.memory .i{width:16px;height:16px;color:var(--teal)}
.story figcaption{margin-top:10px;font-size:.75rem;line-height:1.5;color:var(--ink-2)}
.prompts{list-style:none;padding:0;margin-top:12px;display:grid;grid-template-columns:minmax(0,1fr);gap:8px}
.prompt{display:grid;grid-template-columns:10px minmax(0,1fr);gap:10px;align-items:baseline;padding:10px 12px;border-radius:14px;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow-s);font-weight:600;font-size:.875rem;line-height:1.45}
.prompt::before{content:"";width:10px;height:10px;border-radius:3px;background:var(--k)}
.prompt q{quotes:"\\201C" "\\201D"}
.k-yellow{--k:var(--yellow);--kt:var(--t-yellow)}.k-red{--k:var(--red);--kt:var(--t-red)}.k-teal{--k:var(--teal);--kt:var(--t-teal)}.k-purple{--k:var(--purple);--kt:var(--t-purple)}
.steps{list-style:none;padding:0;margin-top:12px;display:grid;grid-template-columns:minmax(0,1fr);gap:8px}
.step{display:grid;grid-template-columns:34px minmax(0,1fr);gap:12px;align-items:start;padding:12px;border-radius:16px;background:rgba(255,255,255,.66);border:1px solid var(--line)}
.num{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:var(--kt);font:700 .8125rem/1 var(--mono)}
.step h3,.trust-item h3{font:700 .9375rem/1.3 var(--ui)}
.step p{margin-top:2px;font-size:.8125rem;line-height:1.5;color:var(--ink-2)}
.privacy{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;margin-top:10px;padding:12px 14px;border-radius:14px;background:var(--t-teal);font-size:.8125rem;line-height:1.5;font-weight:600}
.trust-list{list-style:none;padding:0;margin-top:12px;display:grid;grid-template-columns:minmax(0,1fr);gap:14px}
.trust-item{display:grid;grid-template-columns:34px minmax(0,1fr);gap:12px;align-items:start}
.trust-icon{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;background:var(--surface);border:1px solid var(--line)}
.trust-icon .i{width:18px;height:18px}
.trust-item p{margin-top:2px;font-size:.8125rem;line-height:1.5;color:var(--ink-2)}
.foot{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;max-width:560px;margin:40px auto 0;padding-top:16px;border-top:1px solid var(--line);font-size:.8125rem;color:var(--ink-2)}
.foot-brand{display:flex;align-items:center;gap:8px}
.foot .mark{width:18px;height:18px}
.problem{display:grid;place-items:center;min-height:calc(100vh - 200px);padding:8px 0 24px}
.problem-card{width:100%;max-width:520px;padding:32px 24px;text-align:center}
.problem-icon{width:56px;height:56px;margin:0 auto 18px;border-radius:18px;display:grid;place-items:center;background:var(--notice)}
.problem-icon .i{width:26px;height:26px}
.problem h1{font:700 1.625rem/1.2 var(--display);letter-spacing:-.015em;text-wrap:balance}
.problem p{margin-top:12px;color:var(--ink-2);text-wrap:pretty}
.problem .actions{max-width:320px;margin:24px auto 0}
.ref{margin-top:22px!important;font:400 .75rem/1.4 var(--mono)}
@media (max-width:359px){.figures{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:560px){
.page{padding:20px 24px 36px}.topbar{margin-bottom:24px}.logo{height:30px}.layout{gap:40px}.consent{padding:12px 14px}
.lede{font-size:1.0625rem}.teaser{padding:14px 16px 15px}.auth-card{padding:24px 24px 22px}.auth-card h2{font-size:1.375rem}
.figures dd{font-size:.9375rem}.convo{padding:16px}.result{padding:12px 14px}
.pace-grid{grid-template-columns:minmax(0,1fr) minmax(0,240px);grid-template-areas:"sum cal" "key cal";column-gap:20px;align-items:start}
.prompts,.trust-list{grid-template-columns:repeat(2,minmax(0,1fr))}.steps{grid-template-columns:repeat(3,minmax(0,1fr))}
.step{grid-template-columns:minmax(0,1fr);gap:10px}.problem-card{padding:40px 40px 32px}}
@media (min-width:1040px){
.page{padding:22px 40px 40px}.topbar{max-width:none;height:36px;margin-bottom:0;justify-content:flex-start;gap:14px}.logo{height:32px}
.layout{max-width:none;margin-top:-36px;grid-template-columns:minmax(0,1fr) minmax(400px,448px);grid-template-areas:"hero auth" "story auth" "ask auth" "how auth" "trust auth";grid-template-rows:auto auto auto auto 1fr;column-gap:64px;row-gap:44px}
.auth{align-self:start}.hero{padding-top:66px}.lede{margin-top:14px;font-size:1.1875rem}.teaser{max-width:520px;margin-top:26px}
.story,.ask,.how,.trust{max-width:640px}.foot{max-width:none}
.auth-card{padding:24px 28px 22px}}
@media (min-width:1040px) and (min-height:1020px){.auth{position:sticky;top:24px}}
@media (prefers-reduced-motion:no-preference) and (min-width:1040px){
.rise{animation:rise .6s cubic-bezier(.2,.7,.2,1) both;animation-delay:var(--d,0s)}
.meter span{animation:grow 1.1s cubic-bezier(.2,.7,.2,1) both;animation-delay:.9s}}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media (forced-colors:active){.meter span,.strip .f,.cal .f{background:Highlight}.strip .t,.cal .t{background:CanvasText;color:Canvas}.btn-primary,.tabs a[aria-current=page]{border:1px solid ButtonText}.rules li::before,.stage::before,.prompt::before,.key li::before{background:CanvasText}}
"""


def _fonts_css(assets: AssetCatalog) -> str:
    faces = (
        ("Manrope", "manrope.woff2", "400 700"),
        ("Sora", "sora.woff2", "400 700"),
        ("Space Mono", "space-mono-400.woff2", "400"),
        ("Space Mono", "space-mono-700.woff2", "700"),
    )
    return "".join(
        f'@font-face{{font-family:"{family}";src:url({assets.url(file)}) format("woff2");'
        f"font-weight:{weight};font-style:normal;font-display:swap}}"
        for family, file, weight in faces
    )


def _document(title: str, body: str, assets: AssetCatalog) -> str:
    preloads = "".join(
        f'<link rel="preload" href="{assets.url(name)}" as="font" type="font/woff2" crossorigin>'
        for name in ("manrope.woff2", "sora.woff2")
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        '<meta name="robots" content="noindex, nofollow">'
        f"<title>{e(title)}</title>"
        f'<link rel="icon" href="{assets.url("mita-mark.svg")}" type="image/svg+xml">'
        f"{preloads}<style>{_fonts_css(assets)}{_CSS}</style></head>"
        f'<body><div class="page">{body}</div></body></html>'
    )


def _footer(support_url: str = "") -> str:
    help_link = (
        f'<a href="{e(support_url)}" target="_blank" rel="noopener noreferrer">Help</a>'
        if support_url
        else ""
    )
    return (
        f'<footer class="foot"><span class="foot-brand">{logo_mark()}'
        "<span>MITA Finance · Control your money. Daily.</span></span>"
        f"{help_link}</footer>"
    )


# --- the sign-in / sign-up / consent page -------------------------------------------


@dataclass(frozen=True)
class LoginView:
    """Everything the page shows. Already validated by login.py."""

    req: str
    csrf: str
    client_name: str
    redirect_host: str
    scopes: Sequence[str]
    register: bool = False
    email: str = ""
    error: Optional[str] = None
    # Which field the error is about: "email", "password", "password_confirm",
    # "credentials" (both sign-in fields, identically for every cause), or
    # None (about the form as a whole).
    error_field: Optional[str] = None
    usage_stats: bool = True
    support_url: str = ""


def _login_href(req: str, register: bool) -> str:
    query = {"req": req, **({"mode": REGISTER} if register else {})}
    return f"{LOGIN_PATH}?{urlencode(query)}"


def _field_state(
    view: LoginView, field: str, *, describedby: Sequence[str] = ()
) -> str:
    """aria attributes and autofocus for one input."""
    ids = list(describedby)
    invalid = view.error is not None and (
        view.error_field == field
        or (view.error_field == "credentials" and field in ("email", "password"))
    )
    if invalid:
        ids.insert(0, "form-error")
    attrs = ""
    if ids:
        attrs += f' aria-describedby="{" ".join(ids)}"'
    if invalid:
        attrs += ' aria-invalid="true"'
    first_invalid = {"credentials": "password"}.get(
        view.error_field or "", view.error_field
    )
    if invalid and field == first_invalid:
        attrs += " autofocus"
    return attrs


def _consent(view: LoginView) -> str:
    """The scopes being granted: every title on screen, the detail of each
    one a tap away (``<details>``, no script)."""
    client = e(view.client_name)
    titles = "".join(
        f'<li>{icon("check-circle")}<span>{e(SCOPE_TITLES.get(s, s))}</span></li>'
        for s in view.scopes
    )
    details = "".join(
        f"<div><dt>{e(SCOPE_TITLES.get(s, s))}</dt>"
        f"<dd>{e(SCOPE_DESCRIPTIONS.get(s, ''))}</dd></div>"
        for s in view.scopes
    )
    return f"""<div class="consent" role="group" aria-labelledby="consent-title">
<h3 id="consent-title">{client} will be able to</h3>
<ul class="scopes">{titles}</ul>
<p class="limits">{icon("ban")}<span>{e(CANNOT_MOVE_MONEY_SHORT)}</span></p>
<details class="perm"><summary>View permission details</summary>
<dl>{details}</dl><p class="money">{e(CANNOT_MOVE_MONEY)}</p></details>
</div>"""


def _auth_card(view: LoginView) -> str:
    client = e(view.client_name)
    if view.register:
        title = "Create your MITA account"
        sub = "Your budget, expenses and goals will live here."
        submit_value, submit_label = REGISTER, "Create account and connect"
        switch = (
            "Already have a MITA account? "
            f'<a href="{e(_login_href(view.req, False))}">Sign in</a>'
        )
    else:
        title = f"Connect MITA to {client}"
        sub = "Use your MITA account — not your ChatGPT login."
        submit_value, submit_label = "allow", "Sign in and connect"
        switch = (
            "New to MITA? "
            f'<a href="{e(_login_href(view.req, True))}">Create an account</a>'
        )

    tabs = ""
    for is_register, label in ((False, "Sign in"), (True, "Create account")):
        current = ' aria-current="page"' if is_register == view.register else ""
        tabs += (
            f'<a href="{e(_login_href(view.req, is_register))}"{current}>{label}</a>'
        )

    error_html = (
        f'<div class="alert">{icon("alert")}'
        f'<p id="form-error" role="alert">{e(view.error)}</p></div>'
        if view.error
        else ""
    )

    email = (
        '<div class="field"><label for="email">Email</label>'
        f'<input class="input" id="email" name="email" type="email" required maxlength="{MAX_FIELD}" '
        f'value="{e(view.email)}" autocomplete="username" inputmode="email" autocapitalize="none" '
        f'spellcheck="false"{_field_state(view, "email")}></div>'
    )
    if view.register:
        rules = "".join(f"<li>{e(rule)}</li>" for rule in PASSWORD_RULES)
        password = (
            '<div class="field"><label for="password">Password</label>'
            f'<input class="input" id="password" name="password" type="password" required '
            f'minlength="{MIN_PASSWORD_LENGTH}" maxlength="{MAX_PASSWORD_LENGTH}" autocomplete="new-password" '
            f'passwordrules="{e(PASSWORD_RULES_ATTR)}"'
            f'{_field_state(view, "password", describedby=["password-rules"])}>'
            f'<ul class="rules" id="password-rules" aria-label="Password requirements">{rules}</ul></div>'
            '<div class="field"><label for="password_confirm">Confirm password</label>'
            f'<input class="input" id="password_confirm" name="password_confirm" type="password" required '
            f'minlength="{MIN_PASSWORD_LENGTH}" maxlength="{MAX_PASSWORD_LENGTH}" autocomplete="new-password"'
            f'{_field_state(view, "password_confirm")}></div>'
        )
        mode_field = f'<input type="hidden" name="mode" value="{REGISTER}">'
    else:
        password = (
            '<div class="field"><label for="password">Password</label>'
            f'<input class="input" id="password" name="password" type="password" required '
            f'maxlength="{MAX_FIELD}" autocomplete="current-password"'
            f'{_field_state(view, "password")}></div>'
        )
        mode_field = ""

    checked = " checked" if view.usage_stats else ""
    help_html = (
        f'<p class="help">Need help? <a href="{e(view.support_url)}" target="_blank" '
        'rel="noopener noreferrer">Contact MITA support</a></p>'
        if view.support_url
        else ""
    )

    return f"""<section class="auth" aria-labelledby="auth-title"><div class="card auth-card">
<h2 id="auth-title">{title}</h2>
<p class="sub">{sub}</p>
<nav class="tabs" aria-label="MITA account">{tabs}</nav>
{error_html}
<form method="post" action="{LOGIN_PATH}" autocomplete="on">
<input type="hidden" name="req" value="{e(view.req)}">
<input type="hidden" name="csrf" value="{e(view.csrf)}">
{mode_field}{email}{password}
{_consent(view)}
<label class="check"><input type="checkbox" name="usage_stats" value="1"{checked}><span>{e(USAGE_STATS_LABEL)}</span></label>
<div class="actions">
<button class="btn btn-primary" type="submit" name="action" value="{submit_value}">{submit_label}</button>
<button class="btn btn-quiet" type="submit" name="action" value="deny" formnovalidate>Cancel</button>
</div>
<p class="return">{icon("return")}<span>After you continue, you’ll return to <strong>{e(view.redirect_host)}</strong>. Then try: “Help me build my monthly budget.”</span></p>
<div class="notice">{icon("shield")}<p><strong>{e(FORGERY_WARNING_LEAD)}</strong> {e(FORGERY_WARNING)}</p></div>
</form>
<p class="switch">{switch}</p>{help_html}
</div></section>"""


def _day_state(today: PaceDay, day: int) -> str:
    """p — passed, t — today, f — one of the days left."""
    return "p" if day < today.day else "t" if day == today.day else "f"


def _strip(today: PaceDay) -> str:
    cells = "".join(
        f'<i class="{_day_state(today, day)}"></i>'
        for day in range(1, DEMO_DAYS_IN_MONTH + 1)
    )
    return f'<div class="strip" aria-hidden="true">{cells}</div>'


def _calendar(today: PaceDay) -> str:
    """The example month as a calendar: days passed, today, days left. One
    shade for every day left — the forecast gives one amount for each of them,
    not a budget per date. Decorative; the key beside it says the same."""
    cells = [f'<span class="h">{d}</span>' for d in WEEKDAY_LETTERS]
    cells += ["<span></span>"] * DEMO_FIRST_WEEKDAY
    cells += [
        f'<span class="{_day_state(today, day)}">{day}</span>'
        for day in range(1, DEMO_DAYS_IN_MONTH + 1)
    ]
    return f'<div class="cal" aria-hidden="true">{"".join(cells)}</div>'


def _used_percent(day: PaceDay) -> Decimal:
    planned = Decimal(DEMO_PLANNED.replace(",", ""))
    return Decimal(day.spent.replace(",", "")) / planned * 100


def _hero() -> str:
    day = MONDAY
    mita = f'<span class="avatar">{logo_mark()}</span>'
    return f"""<section class="hero" aria-labelledby="hero-title">
<h1 id="hero-title">Your finances, <span class="hl">remembered</span> in ChatGPT.</h1>
<p class="lede">Log expenses by chatting, and ask how much you can spend per day until the month ends.</p>
<figure class="teaser"><figcaption class="vh">Example with fictional figures</figcaption>
<p class="bubble">{e(PACE_QUESTION)}</p>
<div class="reply">{mita}<div>
<p class="sum"><span class="fig">€{day.per_day}</span><span class="per">a day</span><span class="example">Example</span></p>
<p class="meta">for the {day.days_left} days left in {DEMO_MONTH}</p>
{_strip(day)}
</div></div></figure></section>"""


def _story() -> str:
    mon, fri = MONDAY, FRIDAY
    month = DEMO_MONTH
    mita = f'<span class="avatar">{logo_mark()}</span>'
    used = _used_percent(mon)
    return f"""<section class="story" aria-labelledby="story-title">
<h2 class="section-title" id="story-title">What MITA does in ChatGPT</h2>
<p class="section-lede">Record, understand and pace your month — and pick up where you left off.</p>
<figure class="story-fig">
<div class="convo rise" style="--d:.1s">
<p class="convo-label"><span>Conversation · {mon.weekday[:3]} {mon.day} {month[:3]}</span><span class="example">Example</span></p>
<p class="stage k-red">01 · Record</p>
<p class="bubble">I spent €36.80 at Lidl.</p>
<div class="reply">{mita}<div class="result">
<p class="result-head">{icon("check-circle")}Expense recorded<span class="result-src">MITA</span></p>
<p class="chips"><span class="chip">Groceries</span><span class="chip">Lidl</span><span class="amount">€36.80</span></p>
</div></div>
<p class="stage k-yellow">02 · Understand</p>
<p class="bubble">How am I doing this month?</p>
<div class="reply">{mita}<div class="result">
<p class="result-head">{icon("chart")}{month} budget<span class="result-src">MITA</span></p>
<dl class="figures"><div><dt>Budget</dt><dd>€{DEMO_PLANNED}</dd></div><div><dt>Spent</dt><dd>€{mon.spent}</dd></div><div><dt>Left</dt><dd>€{mon.left}</dd></div></dl>
<div class="meter" aria-hidden="true"><span style="--w:{used:.2f}%"></span></div>
<p class="meter-note">{used:.0f}% of {month}’s budget used</p>
</div></div>
<p class="stage k-teal">03 · Pace</p>
<p class="bubble">{e(PACE_QUESTION)}</p>
<div class="reply">{mita}<div class="result pace">
<p class="result-head">{icon("calendar")}Safe to spend per day<span class="result-src">MITA</span></p>
<div class="pace-grid">
<div class="pace-sum"><p class="sum"><span class="fig">€{mon.per_day}</span><span class="per">a day</span></p>
<p class="meta">for the {mon.days_left} days left in {month}</p></div>
{_calendar(mon)}
<div class="key"><ul><li class="sw-p"><span>Spent so far</span><b>€{mon.spent}</b></li>
<li class="sw-t"><span>Today, {mon.weekday} {mon.day}</span></li>
<li class="sw-f"><span>{mon.days_left} days left</span><b>€{mon.per_day} a day</b></li></ul>
<p class="calc">€{mon.left} left − €{DEMO_SAVINGS} savings<br>= €{mon.spendable} ÷ {mon.days_left} days = €{mon.per_day}</p>
<p class="kept">{icon("shield")}<span>Your €{DEMO_SAVINGS} of savings is never counted as money to spend.</span></p></div>
</div></div></div>
</div>
<p class="memory rise" style="--d:.3s">{icon("database")}Saved in your MITA account</p>
<div class="convo rise" style="--d:.45s">
<p class="convo-label"><span>New conversation · {fri.weekday[:3]} {fri.day} {month[:3]}</span><span class="example">Example</span></p>
<p class="stage k-purple">04 · Remember</p>
<p class="bubble">How’s my {month} budget now?</p>
<div class="reply">{mita}<div class="result">
<p class="result-head">{icon("chart")}{month} budget<span class="result-src">MITA</span></p>
<dl class="figures"><div><dt>Per day</dt><dd>€{fri.per_day}</dd></div><div><dt>Days left</dt><dd>{fri.days_left}</dd></div><div><dt>Savings kept</dt><dd>€{DEMO_SAVINGS}</dd></div></dl>
</div></div></div>
<figcaption>All figures are fictional. ChatGPT answers in its own words, using the figures MITA returns.</figcaption>
</figure></section>"""


def _ask() -> str:
    items = "".join(
        f'<li class="prompt k-{color}"><q>{e(text)}</q></li>' for color, text in PROMPTS
    )
    return (
        '<section class="ask" aria-labelledby="ask-title">'
        '<h2 class="section-title" id="ask-title">Try asking</h2>'
        '<p class="section-lede">Once MITA is connected, just talk to ChatGPT.</p>'
        f'<ul class="prompts">{items}</ul></section>'
    )


def _how() -> str:
    items = "".join(
        f'<li class="step k-{color}"><span class="num" aria-hidden="true">{index:02d}</span>'
        f"<div><h3>{e(title)}</h3><p>{e(text)}</p></div></li>"
        for index, (color, title, text) in enumerate(STEPS, start=1)
    )
    return (
        '<section class="how" aria-labelledby="how-title">'
        '<h2 class="section-title" id="how-title">How MITA works</h2>'
        f'<ol class="steps">{items}</ol>'
        f'<p class="privacy">{icon("shield")}<span>MITA stores the financial records its features need. '
        "It does not store your ChatGPT conversations.</span></p></section>"
    )


def _trust() -> str:
    items = "".join(
        f'<li class="trust-item"><span class="trust-icon">{icon(name)}</span>'
        f"<div><h3>{e(title)}</h3><p>{e(text)}</p></div></li>"
        for name, title, text in TRUST
    )
    return (
        '<section class="trust" aria-labelledby="trust-title">'
        '<h2 class="section-title" id="trust-title">Clear limits. Your control.</h2>'
        f'<ul class="trust-list">{items}</ul></section>'
    )


def login_page(view: LoginView, assets: AssetCatalog = ASSETS) -> str:
    title = (
        "Create your MITA account"
        if view.register
        else f"Connect MITA to {view.client_name}"
    )
    body = (
        f'<header class="topbar"><div class="brand">{logo_lockup()}</div>'
        '<span class="tag">for ChatGPT</span></header>'
        '<main class="layout">'
        f"{_hero()}{_auth_card(view)}{_story()}{_ask()}{_how()}{_trust()}"
        f"</main>{_footer()}"
    )
    return _document(title, body, assets)


# --- error pages ------------------------------------------------------------------


def problem_page(
    title: str,
    message: str,
    *,
    icon_name: str = "info",
    reference: Optional[str] = None,
    retry_url: Optional[str] = None,
    support_url: str = "",
    assets: AssetCatalog = ASSETS,
) -> str:
    """A calm, branded page for a connection that cannot continue. Never
    echoes request data: ``reference`` must be a fixed, known error code."""
    retry = (
        f'<div class="actions"><a class="btn btn-primary" href="{e(retry_url)}">Try again</a></div>'
        if retry_url
        else ""
    )
    ref = f'<p class="ref">Error reference: {e(reference)}</p>' if reference else ""
    body = (
        f'<header class="topbar"><div class="brand">{logo_lockup()}</div>'
        '<span class="tag">for ChatGPT</span></header>'
        '<main class="problem"><div class="card problem-card">'
        f'<div class="problem-icon">{icon(icon_name)}</div>'
        f"<h1>{e(title)}</h1><p>{e(message)}</p>{retry}{ref}</div></main>"
        f"{_footer(support_url)}"
    )
    return _document(f"{title} · MITA", body, assets)
