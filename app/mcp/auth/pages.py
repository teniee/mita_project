"""What a person sees during the ChatGPT connection: MITA's sign-in /
sign-up / consent page and its error pages.

Presentation only. ``login.py`` owns the flow (CSRF, lockout, rate limits,
sign-up rules, code issuance) and hands this module values it has already
validated; ``browser_errors.py`` uses ``problem_page`` for the authorization
endpoint. Rules:

* **No JavaScript.** No ``<script>``, no inline handlers; the CSP has no
  ``script-src`` (docs/chatgpt-app/oauth-security-audit.md, XSS row). All
  depth and motion is CSS, and every animation stops under
  ``prefers-reduced-motion`` — the page reads complete without it; the
  permission details are a native ``<details>``.
* **Nothing third-party.** Fonts, the photograph and the favicon come from
  this service (``/oauth/assets/``); the logo is the master vector from the
  MITA Brand Guidelines (Figma), inlined — on the navy hero in the guidelines'
  inverted variant (monochrome yellow). Brand values: docs/brand/AUTH-UI-DESIGN.md.
* **Every dynamic value is escaped** with ``html.escape`` at the point of use.
* **Copy states facts only** (docs/chatgpt-app/data-inventory.md): MITA keeps
  structured financial records, never conversations or receipt images, and
  cannot move money. The example month is fictional, labelled so, and every
  figure in it is what MITA's own code computes for it (``demo.py``). The
  photograph is AI-generated (no real people) and never presented as a
  customer.
* **Mobile first.** The base styles are the phone layout (ChatGPT opens this
  page in its in-app browser): the navy hero — headline, value, the calendar
  example, a jump to the form — then the sign-in card, then what MITA adds and
  closed details. From 1040 px the card is a right-hand column beside the hero.
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
from app.mcp.auth.demo import DEMO
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
# Sign-in only: the box starts unticked, and an unticked box is not a
# withdrawal (that is set_usage_analytics(false), which deletes the linked
# statistics). Owner decision 2026-10-25.
USAGE_STATS_KEEP = "Leaving it unticked keeps any choice I made before."
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

_CONTENT_TYPES = {
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


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
# The guidelines' inverted variant for dark backgrounds: the same master
# vectors in monochrome Mita yellow (Logo Variants, navy panel).
INVERTED_FILL = "#FFD25F"


def _recolor(paths: str, fill: Optional[str]) -> str:
    if fill is None:
        return paths
    for colour in ("#6B73FF", "#F44336", "#14B8A6", "#FFD25F", "#193C57"):
        paths = paths.replace(f'fill="{colour}"', f'fill="{fill}"')
    return paths


def logo_lockup(css_class: str = "logo", fill: Optional[str] = None) -> str:
    """Mark + wordmark at the master lockup's spacing (wordmark glyphs at
    +92.39/+14.4 from the mark, baseline on the mark's bottom edge)."""
    return (
        f'<svg class="{css_class}" viewBox="0 0 246 73" role="img" aria-label="MITA">'
        f"{_recolor(_MARK_PATHS, fill)}"
        f'<g transform="translate(92.39 14.4)">{_recolor(_WORDMARK_PATH, fill)}</g></svg>'
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
    "arrow-down": '<path d="M12 5v14"/><path d="M6 13l6 6 6-6"/>',
    "bill": '<path d="M7 3h10v18l-2.5-1.6L12 21l-2.5-1.6L7 21z"/><path d="M9.5 8h5M9.5 12h5"/>',
    "image": '<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M4 15l4-4 4 4 3-3 5 5"/><path d="M15 9.5h.01"/>',
}


def icon(name: str, css_class: str = "i") -> str:
    return (
        f'<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{_ICONS[name]}</svg>'
    )


# --- copy -------------------------------------------------------------------------

# "Each day", not "today": the forecast's amount is per remaining day.
HEADLINE_LEAD, HEADLINE_MARK, HEADLINE_END = (
    "Know what you can ",
    "safely spend",
    " each\u00a0day.",  # a no-break space keeps "each day." on one line
)
LEDE = "One conversation. Your whole month mapped out."
LEDE_2 = "Track spending, plan each day and protect your savings, right inside ChatGPT."
DIFFERENCE = "ChatGPT answers with your own records and MITA’s figures."
DEMO_CAPTION = (
    "Fictional example, worked out by MITA. Connected, ChatGPT shows your own " "month."
)
PHOTO_ALT = "Illustration: a young family on the sofa, looking at a phone together"

# "What MITA adds to ChatGPT" — each a fact a published tool supports
# (claim table in docs/brand/AUTH-UI-DESIGN.md).
ADDS: Tuple[Tuple[str, str], ...] = (
    (
        "Your records in every chat",
        "Expenses, budget and savings goals stay in your MITA account, so a new "
        "chat starts from them.",
    ),
    (
        "Figures MITA works out",
        "The amount a day comes from your saved plan and recorded expenses, with "
        "money for savings left out.",
    ),
    (
        "Your month on a calendar",
        "Open it in the chat: each date’s plan, bills due and money set aside — "
        "and save it as an image.",
    ),
)

# The questions under "What can I ask ChatGPT?". Each is answered by a
# published tool (tests_mcp/test_auth_ui.PROMPT_TOOLS).
CALENDAR_PROMPT = "Show my financial calendar for this month."
BUDGET_PROMPT = "Help me build my monthly budget."
PROMPTS: Tuple[str, ...] = (
    CALENDAR_PROMPT,
    "How much can I safely spend per day?",
    "I spent €36.80 on groceries today.",
    BUDGET_PROMPT,
    "Create an Emergency Fund goal for €3,000.",
    "How has my spending changed over the last six months?",
)

# "What MITA keeps, and what it doesn’t" (a closed <details>).
KEPT: Tuple[str, ...] = (
    "The expenses, budget and savings goals you record stay in your MITA "
    "account, so ChatGPT can use them in any new conversation.",
    "MITA stores the financial records its features need. It does not store "
    "your ChatGPT conversations.",
    "Receipt photos stay in ChatGPT: it reads the photo, and MITA saves only "
    "the date, amount, category and merchant — never the image.",
    "Usage statistics are optional. Untick the box to opt out, or ask ChatGPT "
    "to turn them off later — that deletes the usage events linked to you.",
    "Disconnect MITA in ChatGPT at any time; changing your MITA password also "
    "ends its access.",
)


# --- the example month (fictional; MITA's own figures — demo.py) -------------------

CENT = Decimal("0.01")


def _amount(value: Decimal) -> str:
    return f"{value.quantize(CENT):,.2f}"


def _cell_amount(value: Decimal) -> str:
    return f"{value:,.0f}" if value >= 1000 else f"{value.quantize(CENT):.2f}"


@dataclass(frozen=True)
class DemoFigures:
    """What the example shows, read from MITA's computation of the month."""

    month: str
    per_day: str  # get_budget_forecast safe_daily_limit
    days_left: int  # days_remaining
    savings: str  # savings_set_aside
    groceries_spent: str
    groceries_planned: str
    bill_name: str
    bill_amount: str
    bill_date: str


def demo_figures() -> DemoFigures:
    groceries = next(line for line in DEMO.lines if line.key == "groceries")
    bill = DEMO.bills[0].occurrence
    return DemoFigures(
        month=DEMO.days[0].day.strftime("%B"),
        per_day=_amount(DEMO.forecast.safe_daily_limit),
        days_left=sum(1 for d in DEMO.days if d.kind == "future"),
        savings=_amount(DEMO.forecast.savings_set_aside),
        groceries_spent=_amount(groceries.spent),
        groceries_planned=_amount(groceries.planned),
        bill_name=bill.merchant or "Bill",
        bill_amount=_amount(bill.amount),
        bill_date=f"{bill.day.day} {bill.day.strftime('%b')}",
    )


FIGURES = demo_figures()


# --- styles ---------------------------------------------------------------------

# Mobile first: everything up to the first @media is the phone layout — the
# navy hero full-bleed at the top, then the sign-in card, then the rest. From
# 1040 px the hero is a navy panel on the left and the card a column on the
# right, starting level with it, so its button fits a 1280×800 screen.
_CSS = """
:root{--navy:#193C57;--navy-2:#2B5876;--navy-deep:#122E44;--yellow:#FFD25F;--red:#F44336;--teal:#14B8A6;--purple:#6B73FF;--cream:#FFF9F0;
--ink:#193C57;--ink-2:#4C6679;--surface:#FFFFFF;--line:rgba(25,60,87,.14);--line-2:rgba(25,60,87,.24);--field:#7A8E9E;
--error:#BA1A1A;--error-bg:#FEECEB;--notice:rgba(255,210,95,.31);
--on-navy:#FFF9F0;--on-navy-2:rgba(255,249,240,.80);--on-navy-line:rgba(255,249,240,.22);
--r-m:16px;--r-l:24px;--pill:999px;
--shadow-s:0 1px 2px rgba(25,60,87,.06);--shadow:0 1px 2px rgba(25,60,87,.06),0 16px 40px rgba(25,60,87,.10);
--lift:0 24px 48px rgba(6,20,32,.42),0 6px 14px rgba(6,20,32,.24);
--ui:"Manrope",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
--display:"Sora","Manrope",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;
--mono:"Space Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color-scheme:light}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;min-height:100vh;color:var(--ink);font:400 1rem/1.55 var(--ui);-webkit-font-smoothing:antialiased;
background-color:var(--cream);background-image:radial-gradient(rgba(25,60,87,.06) 1px,transparent 1.4px);background-size:22px 22px}
a{color:var(--ink)}
p,h1,h2,h3,ul,ol,dl,dd,figure{margin:0}
.vh{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.i{width:20px;height:20px;flex:none}
.page{max-width:1240px;margin:0 auto;padding:0 16px 32px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:560px;margin:12px auto 14px}
.brand{display:flex;align-items:center}
.logo{display:block;height:26px;width:auto}
.tag{font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);padding:6px 9px;border:1px solid var(--line-2);border-radius:var(--pill);background:rgba(255,255,255,.6);white-space:nowrap}
.layout{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"hero" "auth" "adds" "more";gap:18px;max-width:560px;margin:0 auto}
.hero{grid-area:hero}.auth{grid-area:auth}.adds{grid-area:adds}.more{grid-area:more}

/* the navy hero */
.hero{position:relative;margin:0 -16px;padding:14px 16px 22px;border-radius:0 0 30px 30px;color:var(--on-navy);overflow:hidden;isolation:isolate;
background:radial-gradient(70% 46% at 92% 8%,rgba(255,210,95,.18),transparent 70%),radial-gradient(70% 50% at 0% 98%,rgba(107,115,255,.24),transparent 72%),linear-gradient(180deg,#1D4567 0%,#193C57 46%,#14334B 100%)}
.htop{display:flex;align-items:center;justify-content:space-between;gap:12px}
.logo-inv{display:block;height:24px;width:auto}
.htop-r{display:flex;align-items:center;gap:8px}
.pill-cta{display:inline-flex;align-items:center;gap:5px;min-height:34px;padding:6px 12px;border-radius:var(--pill);background:var(--yellow);color:var(--navy);font:700 .8125rem/1 var(--ui);text-decoration:none;white-space:nowrap;box-shadow:0 6px 16px rgba(6,20,32,.3)}
.pill-cta .i{width:14px;height:14px}
.tag-inv{font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--on-navy-2);padding:6px 9px;border:1px solid var(--on-navy-line);border-radius:var(--pill);background:rgba(255,249,240,.06);white-space:nowrap}
.hero h1{margin-top:18px;font:700 clamp(2.05rem,1.2rem + 4.1vw,3.75rem)/1.04 var(--display);letter-spacing:-.032em;text-wrap:balance}
.hl{color:var(--yellow)}
.lede{margin-top:12px;font:700 1.0625rem/1.38 var(--ui);color:var(--on-navy)}
.lede-2{margin-top:4px;max-width:36rem;font-size:.9375rem;line-height:1.5;color:var(--on-navy-2);text-wrap:pretty}

/* the example: a photograph, the month as a slab, MITA's figures around it */
.demo{margin-top:18px}
.scene{position:relative;height:388px;perspective:1100px;perspective-origin:24% 18%}
.photo{position:absolute;top:0;right:-6px;width:86%;aspect-ratio:3/2;border-radius:22px;overflow:hidden;background:#2B5876;box-shadow:var(--lift);transform:rotate(2.2deg);transform-origin:70% 30%}
.photo img{display:block;width:100%;height:100%;object-fit:cover;object-position:38% 42%}
.photo::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(18,46,68,0) 52%,rgba(18,46,68,.55) 100%)}
.slab{position:absolute;left:0;bottom:12px;width:76%;padding:10px 9px 10px;border-radius:18px;background:#FFFFFF;color:var(--ink);box-shadow:0 34px 60px rgba(6,20,32,.48),0 10px 20px rgba(6,20,32,.28),inset 0 0 0 1px rgba(25,60,87,.06);transform:rotateX(16deg) rotateY(-14deg) rotate(-3.5deg);transform-origin:20% 100%;transform-style:preserve-3d}
.slab::before{content:"";position:absolute;inset:0;border-radius:18px;background:linear-gradient(115deg,rgba(255,255,255,.65) 0%,rgba(255,255,255,0) 38%);pointer-events:none}
.slab::after{content:"";position:absolute;left:10px;right:10px;bottom:-8px;height:12px;border-radius:0 0 16px 16px;background:#D7DEE5;transform:translateZ(-1px);z-index:-1}
.slab-top{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:6px}
.slab-m{font:700 .875rem/1 var(--display);letter-spacing:-.01em}
.tag-ex{font:700 .5rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);padding:3px 5px;border:1px solid var(--line-2);border-radius:var(--pill);white-space:nowrap}
.slab-wd,.slab-days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}
.slab-wd span{font:700 .5rem/1 var(--mono);text-align:center;color:var(--ink-2);padding-bottom:3px}
.slab-days{list-style:none;padding:0}
.slab-days li{position:relative;height:31px;border-radius:7px;padding:3px 3px 0;background:#F6F1E8;min-width:0;overflow:hidden}
.slab-days li.b{background:none}
.slab-days b{display:block;font:700 .5625rem/1 var(--ui);color:var(--ink)}
.slab-days i{display:block;margin-top:3px;font:400 .5rem/1 var(--mono);font-style:normal;color:var(--ink);white-space:nowrap}
.slab-days s{position:absolute;left:3px;right:3px;bottom:3px;height:2.5px;border-radius:2px;background:rgba(25,60,87,.12);text-decoration:none}
.slab-days s::after{content:"";position:absolute;left:0;top:0;bottom:0;width:var(--r,0%);border-radius:2px;background:var(--teal)}
.slab-days li.f{background:none;border:1px dashed rgba(25,60,87,.30)}
.slab-days li.f i{color:var(--ink-2)}
.slab-days li.t{background:var(--navy);box-shadow:0 0 0 2px var(--yellow)}
.slab-days li.t b{color:var(--yellow)}
.slab-days li.t i{color:var(--on-navy)}
.slab-days li.bill::before{content:"";position:absolute;right:3px;top:3px;width:5px;height:5px;border-radius:50%;background:var(--purple)}
.card-f{position:absolute;padding:8px 11px 9px;border-radius:14px;background:#FFFFFF;color:var(--ink);box-shadow:0 18px 34px rgba(6,20,32,.40),0 4px 10px rgba(6,20,32,.18);font-size:.6875rem;line-height:1.3;white-space:nowrap}
.card-f b{display:block;margin-top:2px;font:700 1rem/1.1 var(--mono);letter-spacing:-.02em}
.card-f .k{display:flex;align-items:center;gap:5px;font-weight:700;color:var(--ink-2)}
.card-f .k .i{width:13px;height:13px}
.card-f small{display:block;margin-top:1px;font-size:.625rem;color:var(--ink-2)}
.f-safe{right:0;top:45%;background:var(--yellow);border:1px solid rgba(25,60,87,.08)}
.f-safe b{font-size:1.375rem}
.f-safe .k,.f-safe small{color:var(--navy)}
.f-save{left:4px;top:10px}
.f-save .k .i{color:#0B6E64}
.f-bill{right:6px;bottom:0}
.f-bill .k .i{color:var(--purple)}
.f-cat{display:none;left:4px;top:118px}
.meter{display:block;width:112px;height:5px;margin-top:5px;border-radius:3px;background:rgba(25,60,87,.12);overflow:hidden}
.meter span{display:block;height:100%;background:#008300}
.demo figcaption{margin-top:12px;font-size:.75rem;line-height:1.45;color:var(--on-navy-2)}
.diff{margin-top:14px;display:flex;gap:9px;align-items:flex-start;font-size:.875rem;line-height:1.45;font-weight:600;color:var(--on-navy)}
.diff .i{width:18px;height:18px;margin-top:1px;color:var(--yellow)}
.cta{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.btn-cta{flex:1 1 auto;background:var(--yellow);color:var(--navy);box-shadow:0 10px 24px rgba(6,20,32,.32)}
.btn-cta:hover{background:#FFDD86}
.hero .btn-ghost{flex:1 1 auto;background:transparent;color:var(--on-navy);border-color:rgba(255,249,240,.46)}
.hero .btn-ghost:hover{background:rgba(255,249,240,.08)}

/* motion: CSS only, decorative, off under reduced motion — the page is complete without it */
@keyframes slab-in{from{opacity:0;transform:rotateX(34deg) rotateY(-24deg) rotate(-7deg) translateY(36px)}}
@keyframes photo-in{from{opacity:0;transform:rotate(5deg) translateY(-14px) scale(.97)}}
@keyframes rise{from{opacity:0;translate:0 12px}}
@keyframes cell-in{from{opacity:0;scale:.6}}
@keyframes bob{50%{translate:0 -5px}}
@keyframes ping{0%{box-shadow:0 0 0 2px var(--yellow),0 0 0 2px rgba(255,210,95,.75)}100%{box-shadow:0 0 0 2px var(--yellow),0 0 0 12px rgba(255,210,95,0)}}
@keyframes fly{0%{opacity:0;translate:-36px 18px;scale:1}14%{opacity:1}70%{opacity:1;translate:var(--tx) var(--ty);scale:.62}100%{opacity:0;translate:var(--tx) var(--ty);scale:.5}}
.photo{animation:photo-in .9s cubic-bezier(.2,.8,.2,1) both}
.slab{animation:slab-in 1.1s cubic-bezier(.16,.84,.24,1) .18s both}
.slab-days li{animation:cell-in .42s cubic-bezier(.2,.9,.3,1.2) both;animation-delay:calc(.55s + var(--i,0) * 22ms)}
.slab-days li.t{animation:cell-in .42s cubic-bezier(.2,.9,.3,1.2) both,ping 1.6s ease-out 2.6s 2;animation-delay:calc(.55s + var(--i,0) * 22ms),2.6s}
.card-f{animation:rise .7s cubic-bezier(.2,.8,.2,1) both,bob 7s ease-in-out infinite}
.f-save{animation-delay:1.25s,2.4s}.f-safe{animation-delay:1.45s,2.9s}.f-bill{animation-delay:1.65s,3.3s}.f-cat{animation-delay:1.85s,3.7s}
.flyer{--tx:-166px;--ty:103px;position:absolute;left:52%;top:55%;padding:5px 9px;border-radius:var(--pill);background:#FFFFFF;color:var(--ink);font:700 .625rem/1 var(--mono);box-shadow:0 10px 22px rgba(6,20,32,.35);opacity:0;pointer-events:none;animation:fly 1.5s cubic-bezier(.3,.7,.2,1) 2.05s both}

/* the sign-in card */
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-l);box-shadow:var(--shadow)}
.auth{scroll-margin-top:12px}
.auth-card{padding:16px 16px 20px}
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
.perm{margin-top:6px}
.perm,.disclose{font-size:.8125rem}
.perm summary,.disclose summary{display:inline-flex;align-items:center;gap:7px;min-height:24px;cursor:pointer;font-weight:700;list-style:none;text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px;text-decoration-color:var(--yellow)}
.perm summary::-webkit-details-marker,.disclose summary::-webkit-details-marker{display:none}
.perm summary::after,.disclose summary::after{content:"";width:6px;height:6px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:translateY(-2px) rotate(45deg)}
.perm[open] summary::after,.disclose[open] summary::after{transform:translateY(1px) rotate(-135deg)}
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
.btn-primary:active,.btn-cta:active{transform:translateY(1px)}
.btn-quiet{min-height:44px;background:transparent;color:var(--ink);border-color:var(--line-2)}
.btn-quiet:hover{background:rgba(25,60,87,.05)}
.btn:focus-visible,.tabs a:focus-visible,a:focus-visible,.check input:focus-visible,.perm summary:focus-visible,.disclose summary:focus-visible{outline:3px solid var(--purple);outline-offset:2px}
.hero .btn:focus-visible,.hero a:focus-visible{outline-color:var(--yellow)}
.return{display:flex;justify-content:center;gap:8px;margin-top:12px;font-size:.8125rem;line-height:1.5;color:var(--ink-2);text-align:center}
.return .i{width:16px;height:16px;margin-top:2px}
.notice{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;margin-top:14px;padding:12px 14px;border-radius:14px;background:var(--notice);font-size:.8125rem;line-height:1.5}
.switch{margin-top:16px;text-align:center;font-size:.9375rem;color:var(--ink-2)}
.switch a,.help a{font-weight:700;text-decoration-thickness:2px;text-underline-offset:3px;text-decoration-color:var(--yellow)}
.help{margin-top:8px;text-align:center;font-size:.8125rem;color:var(--ink-2)}

/* what MITA adds; details */
.section-title{font:700 1.25rem/1.25 var(--display);letter-spacing:-.015em}
.adds-list{list-style:none;padding:0;margin-top:12px;display:grid;gap:10px}
.adds-list li{display:grid;grid-template-columns:42px minmax(0,1fr);gap:12px;align-items:start;padding:14px;border-radius:var(--r-m);background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow-s)}
.adds-list .n{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:var(--navy);color:var(--yellow);font:700 .8125rem/1 var(--mono)}
.adds-list h3{font:700 .9375rem/1.3 var(--ui)}
.adds-list p{margin-top:3px;font-size:.84375rem;line-height:1.5;color:var(--ink-2)}
.more{display:grid;gap:8px}
.more .disclose{padding:10px 14px;border-radius:var(--r-m);background:rgba(255,255,255,.7);border:1px solid var(--line)}
.more summary{min-height:28px}
.more ul{display:grid;gap:6px;margin-top:8px;padding-left:18px;line-height:1.5;color:var(--ink-2)}
.more q{quotes:"\\201C" "\\201D";color:var(--ink);font-weight:600}
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
@media (max-width:359px){.scene{height:360px}.f-bill{display:none}.tag-inv{display:none}}
@media (min-width:430px){.scene{height:430px}.f-cat{display:block}.slab-days li{height:34px}.flyer{--tx:-196px;--ty:116px}}
@media (min-width:560px){
.page{padding:0 24px 36px}.layout{gap:28px}.hero{margin:0 -24px;padding:18px 24px 26px}.consent{padding:12px 14px}
.lede{font-size:1.25rem}.lede-2{font-size:1.0625rem}.scene{height:500px}
.slab{width:68%;padding:13px 12px}.slab-m{font-size:1.0625rem}.tag-ex{font-size:.5625rem}.slab-wd span{font-size:.5625rem}
.slab-days li{height:42px;border-radius:8px;padding:4px 4px 0}.slab-days b{font-size:.6875rem}.slab-days i{font-size:.5625rem;margin-top:4px}
.card-f{font-size:.75rem}.card-f b{font-size:1.125rem}.f-safe b{font-size:1.5rem}.f-cat{top:150px}.flyer{--tx:-236px;--ty:146px}
.auth-card{padding:24px 24px 22px}.auth-card h2{font-size:1.375rem}
.adds-list li{padding:16px}
.problem-card{padding:40px 40px 32px}}
@media (min-width:1040px){
.page{padding:24px 40px 40px}.topbar{max-width:none}
.layout{max-width:none;grid-template-columns:minmax(0,1fr) minmax(400px,440px);grid-template-areas:"hero auth" "adds auth" "more auth";grid-template-rows:auto auto 1fr;column-gap:36px;row-gap:28px}
.hero{margin:0;padding:26px 36px 32px;border-radius:34px;box-shadow:0 30px 60px rgba(25,60,87,.20)}
.hero h1{margin-top:30px}
.scene{height:440px;margin-top:6px}
.photo{width:64%;right:0;top:0}
.slab{width:60%;left:2%;bottom:10px}
.f-safe{right:4%;top:auto;bottom:122px}.f-save{left:auto;right:56%;top:8px}.f-cat{left:auto;right:3%;top:auto;bottom:-4px}.f-bill{left:auto;right:2%;top:-10px;bottom:auto}
.cta{display:none}
.pill-cta{display:none}
.flyer{--tx:-300px;--ty:124px}
.auth{align-self:start}
.adds-list{grid-template-columns:repeat(3,minmax(0,1fr))}
.adds-list li{grid-template-columns:minmax(0,1fr);gap:10px}
.more{max-width:none}.foot{max-width:none}
.auth-card{padding:24px 28px 22px}}
@media (min-width:1040px) and (min-height:1020px){.auth{position:sticky;top:24px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*::before,*::after{animation:none!important;transition:none!important}.flyer{display:none}}
@media (forced-colors:active){.btn-primary,.btn-cta,.tabs a[aria-current=page]{border:1px solid ButtonText}.rules li::before{background:CanvasText}.slab-days s::after{background:CanvasText}}
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
        '<meta name="theme-color" content="#193C57">'
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
    # Unticked until the person ticks it: ticking is the consent.
    usage_stats: bool = False
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
        first_prompt = BUDGET_PROMPT
        switch = (
            "Already have a MITA account? "
            f'<a href="{e(_login_href(view.req, False))}#auth">Sign in</a>'
        )
    else:
        title = f"Connect MITA to {client}"
        sub = "Use your MITA account — not your ChatGPT login."
        submit_value, submit_label = "allow", "Sign in and connect"
        first_prompt = CALENDAR_PROMPT
        switch = (
            "New to MITA? "
            f'<a href="{e(_login_href(view.req, True))}#auth">Create an account</a>'
        )

    tabs = ""
    for is_register, label in ((False, "Sign in"), (True, "Create account")):
        current = ' aria-current="page"' if is_register == view.register else ""
        tabs += f'<a href="{e(_login_href(view.req, is_register))}#auth"{current}>{label}</a>'

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
    usage_label = (
        USAGE_STATS_LABEL
        if view.register
        else f"{USAGE_STATS_LABEL} {USAGE_STATS_KEEP}"
    )
    help_html = (
        f'<p class="help">Need help? <a href="{e(view.support_url)}" target="_blank" '
        'rel="noopener noreferrer">Contact MITA support</a></p>'
        if view.support_url
        else ""
    )

    return f"""<section class="auth" id="auth" aria-labelledby="auth-title"><div class="card auth-card">
<h2 id="auth-title">{title}</h2>
<p class="sub">{sub}</p>
<nav class="tabs" aria-label="MITA account">{tabs}</nav>
{error_html}
<form method="post" action="{LOGIN_PATH}" autocomplete="on">
<input type="hidden" name="req" value="{e(view.req)}">
<input type="hidden" name="csrf" value="{e(view.csrf)}">
{mode_field}{email}{password}
{_consent(view)}
<label class="check"><input type="checkbox" name="usage_stats" value="1"{checked}><span>{e(usage_label)}</span></label>
<div class="actions">
<button class="btn btn-primary" type="submit" name="action" value="{submit_value}">{submit_label}</button>
<button class="btn btn-quiet" type="submit" name="action" value="deny" formnovalidate>Cancel</button>
</div>
<p class="return">{icon("return")}<span>After you continue, you’ll return to <strong>{e(view.redirect_host)}</strong>. Then try: “{e(first_prompt)}”</span></p>
<div class="notice">{icon("shield")}<p><strong>{e(FORGERY_WARNING_LEAD)}</strong> {e(FORGERY_WARNING)}</p></div>
</form>
<p class="switch">{switch}</p>{help_html}
</div></section>"""


def _slab() -> str:
    """The example month as a calendar: spending on the days begun, the plan
    on the days ahead, today, the bill due — all from ``demo.DEMO``."""
    first = DEMO.days[0].day
    bills = {b.occurrence.day for b in DEMO.bills}
    cells = ['<li class="b"></li>'] * first.weekday()
    for index, day in enumerate(DEMO.days):
        classes = ["d"]
        if day.kind == "future":
            classes.append("f")
            amount = _cell_amount(day.planned) if day.planned > 0 else ""
            meter = ""
        else:
            if day.kind == "today":
                classes.append("t")
            amount = _cell_amount(day.spent) if day.spent > 0 else ""
            ratio = (
                min(Decimal(1), day.spent_everyday / day.planned_everyday)
                if day.planned_everyday > 0
                else Decimal(0)
            )
            meter = (
                f'<s style="--r:{ratio * 100:.0f}%"></s>'
                if day.planned_everyday > 0
                else ""
            )
        if day.day in bills:
            classes.append("bill")
        cells.append(
            f'<li class="{" ".join(classes)}" style="--i:{index}"><b>{day.day.day}</b>'
            f"<i>{amount}</i>{meter}</li>"
        )
    weekdays = "".join(f"<span>{d}</span>" for d in "MTWTFSS")
    return (
        '<div class="slab" aria-hidden="true">'
        f'<div class="slab-top"><span class="slab-m">{e(FIGURES.month)}</span>'
        '<span class="tag-ex">Fictional example</span></div>'
        f'<div class="slab-wd">{weekdays}</div><ol class="slab-days">{"".join(cells)}</ol></div>'
    )


def _demo(assets: AssetCatalog) -> str:
    """The example: the photograph, the month, MITA's figures for it."""
    f = FIGURES
    groceries_ratio = Decimal(f.groceries_spent.replace(",", "")) / Decimal(
        f.groceries_planned.replace(",", "")
    )
    small, large = assets.url("hero-family-640.webp"), assets.url(
        "hero-family-1100.webp"
    )
    today_spent = next(d.spent for d in DEMO.days if d.kind == "today")
    summary = (
        f"Fictional example of MITA's calendar for {f.month}: about €{f.per_day} a day "
        f"is safe to spend for the {f.days_left} days left, with €{f.savings} of savings "
        f"kept out; groceries €{f.groceries_spent} of €{f.groceries_planned}; "
        f"{f.bill_name} €{f.bill_amount} due {f.bill_date}."
    )
    return f"""<figure class="demo" aria-labelledby="demo-cap">
<p class="vh">{e(summary)}</p>
<div class="scene" aria-hidden="true">
<div class="photo"><img src="{small}" srcset="{small} 640w, {large} 1100w" sizes="(min-width: 1040px) 460px, 90vw" width="1100" height="733" alt="{e(PHOTO_ALT)}" fetchpriority="high" decoding="async"></div>
{_slab()}
<div class="card-f f-save"><span class="k">{icon("shield")}Savings kept</span><b>€{f.savings}</b></div>
<div class="card-f f-safe"><span class="k">Safe to spend</span><b>€{f.per_day}</b><small>a day · {f.days_left} days left</small></div>
<div class="card-f f-cat"><span class="k">Groceries</span><b>€{f.groceries_spent}</b><span class="meter"><span style="width:{groceries_ratio * 100:.0f}%"></span></span><small>of €{f.groceries_planned} planned</small></div>
<div class="card-f f-bill"><span class="k">{icon("bill")}{e(f.bill_name)}</span><b>€{f.bill_amount}</b><small>due {e(f.bill_date)}</small></div>
<span class="flyer">Groceries €{_amount(today_spent)}</span>
</div>
<figcaption id="demo-cap">{e(DEMO_CAPTION)}</figcaption>
</figure>"""


def _hero(view: LoginView, assets: AssetCatalog) -> str:
    """The phone's first screen: promise, value, the month, the way in."""
    other = (
        f'<a class="btn btn-ghost" href="{e(_login_href(view.req, False))}#auth">I have an account</a>'
        if view.register
        else f'<a class="btn btn-ghost" href="{e(_login_href(view.req, True))}#auth">Create account</a>'
    )
    return f"""<section class="hero" aria-labelledby="hero-title">
<div class="htop"><span class="brand">{logo_lockup("logo-inv", fill=INVERTED_FILL)}</span><span class="htop-r"><span class="tag-inv">for ChatGPT</span><a class="pill-cta" href="#auth">Connect {icon("arrow-down")}</a></span></div>
<h1 id="hero-title">{e(HEADLINE_LEAD)}<span class="hl">{e(HEADLINE_MARK)}</span>{e(HEADLINE_END)}</h1>
<p class="lede">{e(LEDE)}</p>
<p class="lede-2">{e(LEDE_2)}</p>
{_demo(assets)}
<p class="diff">{icon("check-circle")}<span>{e(DIFFERENCE)}</span></p>
<div class="cta"><a class="btn btn-cta" href="#auth">Connect MITA {icon("arrow-down")}</a>{other}</div>
</section>"""


def _adds() -> str:
    items = "".join(
        f'<li><span class="n">{index:02d}</span><div><h3>{e(title)}</h3><p>{e(text)}</p></div></li>'
        for index, (title, text) in enumerate(ADDS, start=1)
    )
    return (
        '<section class="adds" aria-labelledby="adds-title">'
        '<h2 class="section-title" id="adds-title">What MITA adds to ChatGPT</h2>'
        f'<ol class="adds-list">{items}</ol></section>'
    )


def _more() -> str:
    """Secondary detail for whoever wants it, closed by default."""
    prompts = "".join(f"<li><q>{e(text)}</q></li>" for text in PROMPTS)
    kept = "".join(f"<li>{e(text)}</li>" for text in KEPT)
    return (
        '<section class="more" aria-labelledby="more-title">'
        '<h2 class="vh" id="more-title">More about MITA</h2>'
        '<details class="disclose"><summary>What can I ask ChatGPT?</summary>'
        f"<ul>{prompts}</ul></details>"
        '<details class="disclose"><summary>What MITA keeps, and what it doesn’t</summary>'
        f"<ul>{kept}</ul></details></section>"
    )


def login_page(view: LoginView, assets: AssetCatalog = ASSETS) -> str:
    title = (
        "Create your MITA account"
        if view.register
        else f"Connect MITA to {view.client_name}"
    )
    body = (
        '<main class="layout">'
        f"{_hero(view, assets)}{_auth_card(view)}{_adds()}{_more()}"
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
