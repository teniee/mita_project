"""What a person sees during the ChatGPT connection: MITA's sign-in /
sign-up / consent page and its error pages.

Presentation only. ``login.py`` owns the flow (CSRF, lockout, rate limits,
sign-up rules, code issuance) and hands this module values it has already
validated; ``browser_errors.py`` uses ``problem_page`` for the authorization
endpoint. Rules:

* **No JavaScript.** No ``<script>``, no inline handlers; the CSP has no
  ``script-src`` (docs/chatgpt-app/oauth-security-audit.md, XSS row). Motion
  is CSS and stops under ``prefers-reduced-motion``.
* **Nothing third-party.** Fonts and the favicon come from this service
  (``/oauth/assets/``); the logo is the master vector from the MITA Brand
  Guidelines (Figma), inlined. Brand values: docs/brand/AUTH-UI-DESIGN.md.
* **Every dynamic value is escaped** with ``html.escape`` at the point of use.
* **Copy states facts only** (docs/chatgpt-app/data-inventory.md): MITA keeps
  structured financial records, never conversations or receipt images, and
  cannot move money. Demo figures are fictional and labelled as such.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass
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
    "Help improve MITA: record which MITA features I use. MITA never records "
    "my conversations, amounts or merchant names. I can turn this off at any time."
)
CANNOT_MOVE_MONEY = (
    "MITA cannot move money, make payments or connect to your bank, and it "
    "cannot buy investments or crypto."
)
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
    "link": '<path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1"/>',
    "chat": '<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H8l-4 3v-10.5A7.5 7.5 0 0 1 11.5 4h1A7.5 7.5 0 0 1 20 11.5z"/>',
    "ban": '<circle cx="12" cy="12" r="9"/><path d="M5.7 5.7l12.6 12.6"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "chart": '<path d="M5 20V11M12 20V5M19 20v-6"/>',
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

PROMPTS: Tuple[Tuple[str, str, str], ...] = (
    ("Budget", "yellow", "Help me build my monthly budget."),
    ("Budget", "yellow", "How am I doing against my budget this month?"),
    ("Expenses", "red", "I spent €36.80 on groceries today."),
    ("Expenses", "red", "Add the expenses from this receipt to MITA."),
    ("Plans", "teal", "What recurring expenses do I have?"),
    ("Plans", "teal", "Create an Emergency Fund goal for €3,000."),
    ("Insights", "purple", "How has my spending changed over the last six months?"),
    ("Insights", "purple", "Where did most of my money go this month?"),
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
        "Expenses, budgets, recurring costs and goals are saved as structured data in your MITA account.",
    ),
    (
        "yellow",
        "Ask anytime",
        "Start a new conversation tomorrow: ChatGPT can still check your budget through MITA.",
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

_CSS = """
:root{--navy:#193C57;--navy-2:#2B5876;--yellow:#FFD25F;--red:#F44336;--teal:#14B8A6;--purple:#6B73FF;--cream:#FFF9F0;
--ink:#193C57;--ink-2:#4C6679;--surface:#FFFFFF;--line:rgba(25,60,87,.14);--line-2:rgba(25,60,87,.24);--field:#7A8E9E;
--error:#BA1A1A;--error-bg:#FEECEB;--notice:rgba(255,210,95,.31);
--t-red:#FDE1DF;--t-purple:#E4E6FF;--t-teal:#D5F2EF;--t-yellow:#FFF1CD;
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
.page{max-width:1200px;margin:0 auto;padding:20px 16px 32px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;max-width:580px;margin:0 auto 28px}
.brand{display:flex;align-items:center;gap:12px}
.logo{display:block;height:30px;width:auto}
.tag{font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);padding:7px 10px;border:1px solid var(--line-2);border-radius:var(--pill);background:rgba(255,255,255,.6);white-space:nowrap}
.layout{display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"hero" "auth" "demo" "ask" "how" "trust";gap:36px;max-width:580px;margin:0 auto}
.hero{grid-area:hero}.auth{grid-area:auth}.demo{grid-area:demo}.ask{grid-area:ask}.how{grid-area:how}.trust{grid-area:trust}
.eyebrow{margin-bottom:14px;font:700 .75rem/1.2 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2)}
.hero h1{font:700 clamp(2.1rem,1.5rem + 2.7vw,3.35rem)/1.07 var(--display);letter-spacing:-.025em;text-wrap:balance}
.hl{background:linear-gradient(transparent 62%,rgba(255,210,95,.9) 62%,rgba(255,210,95,.9) 92%,transparent 92%);padding:0 .05em;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.lede{margin-top:16px;max-width:36rem;font-size:1.0625rem;line-height:1.6;color:var(--ink-2);text-wrap:pretty}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-l);box-shadow:var(--shadow)}
.auth-card{padding:24px 20px}
.pair{display:flex;align-items:center;gap:8px;margin-bottom:16px}
.app{width:40px;height:40px;border-radius:13px;display:grid;place-items:center;border:1px solid var(--line);background:var(--cream)}
.app .mark{width:24px;height:24px}
.app-gpt{background:var(--navy);border-color:var(--navy);color:#fff}
.pair-link{display:flex;color:var(--ink-2)}
.auth-card h2{font:700 1.5rem/1.2 var(--display);letter-spacing:-.015em}
.sub{margin-top:8px;color:var(--ink-2);font-size:.9375rem}
.tabs{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:20px 0 4px;padding:4px;border-radius:var(--pill);background:rgba(25,60,87,.06)}
.tabs a{display:flex;align-items:center;justify-content:center;min-height:40px;border-radius:var(--pill);font-weight:700;font-size:.9375rem;color:var(--ink-2);text-decoration:none}
.tabs a:hover{color:var(--ink)}
.tabs a[aria-current=page]{background:var(--surface);color:var(--ink);box-shadow:0 1px 3px rgba(25,60,87,.14),0 0 0 1px var(--line)}
.alert{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:12px 14px;border-radius:14px;background:var(--error-bg);border:1px solid rgba(244,67,54,.4);color:var(--error);font-weight:600;font-size:.9375rem;line-height:1.45}
.alert .i{margin-top:1px}
.field{margin-top:16px}
.field label{display:block;margin-bottom:6px;font-weight:700;font-size:.9375rem}
.input{display:block;width:100%;min-height:50px;padding:12px 14px;border:1px solid var(--field);border-radius:14px;background:var(--surface);color:var(--ink);font:500 1rem/1.4 var(--ui)}
.input:hover{border-color:var(--navy-2)}
.input:focus{outline:3px solid var(--purple);outline-offset:1px;border-color:var(--navy)}
.input[aria-invalid=true]{border:2px solid var(--error);padding:11px 13px}
.rules{list-style:none;padding:0;margin-top:10px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 12px;font-size:.8125rem;color:var(--ink-2)}
.rules li{display:flex;align-items:center;gap:7px}
.rules li::before{content:"";width:6px;height:6px;border-radius:2px;background:var(--teal);flex:none}
.consent{margin-top:18px;padding:14px 14px 12px;border-radius:var(--r-m);background:var(--cream);border:1px solid var(--line)}
.consent h3{margin-bottom:10px;font:700 .9375rem/1.3 var(--ui)}
.scopes{list-style:none;padding:0;display:grid;gap:8px}
.scopes li{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;align-items:start}
.scopes .i{color:var(--teal);margin-top:1px}
.scope-title{display:block;font-weight:700;font-size:.875rem;line-height:1.3}
.scope-detail{display:block;margin-top:1px;font-size:.78125rem;line-height:1.4;color:var(--ink-2)}
.limits{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;margin-top:12px;padding-top:12px;border-top:1px dashed var(--line-2);font-size:.8125rem;line-height:1.45;font-weight:600}
.check{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;align-items:start;margin-top:16px;font-size:.8125rem;line-height:1.5;color:var(--ink-2);cursor:pointer}
.check input{width:18px;height:18px;margin:2px 0 0;accent-color:var(--navy)}
.actions{display:grid;gap:10px;margin-top:20px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:12px 22px;border-radius:var(--pill);border:1px solid transparent;font:700 1rem/1.2 var(--ui);text-decoration:none;cursor:pointer;transition:background-color .15s ease,box-shadow .15s ease,transform .15s ease}
.btn-primary{min-height:54px;background:var(--navy);color:var(--yellow);box-shadow:0 6px 18px rgba(25,60,87,.24)}
.btn-primary:hover{background:var(--navy-2)}
.btn-primary:active{transform:translateY(1px);box-shadow:0 2px 8px rgba(25,60,87,.24)}
.btn-quiet{background:transparent;color:var(--ink);border-color:var(--line-2)}
.btn-quiet:hover{background:rgba(25,60,87,.05)}
.btn:focus-visible,.tabs a:focus-visible,a:focus-visible,.check input:focus-visible{outline:3px solid var(--purple);outline-offset:2px}
.return{display:flex;justify-content:center;gap:8px;margin-top:14px;font-size:.8125rem;line-height:1.5;color:var(--ink-2);text-align:center}
.return .i{width:16px;height:16px;margin-top:2px}
.notice{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;margin-top:16px;padding:12px 14px;border-radius:14px;background:var(--notice);font-size:.8125rem;line-height:1.5}
.switch{margin-top:18px;text-align:center;font-size:.9375rem;color:var(--ink-2)}
.switch a,.help a{font-weight:700;text-decoration-thickness:2px;text-underline-offset:3px;text-decoration-color:var(--yellow)}
.help{margin-top:8px;text-align:center;font-size:.8125rem;color:var(--ink-2)}
.section-title{font:600 1.5rem/1.25 var(--display);letter-spacing:-.012em}
.section-lede{margin-top:6px;color:var(--ink-2)}
.convo{padding:16px;border-radius:22px;background:rgba(255,255,255,.82);border:1px solid var(--line);box-shadow:var(--shadow)}
.convo-label{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.example{padding:4px 8px;border-radius:var(--pill);border:1px solid var(--line-2);font-size:.625rem}
.bubble{margin:0 0 10px auto;max-width:86%;width:fit-content;padding:10px 14px;border-radius:18px 18px 6px 18px;background:var(--navy);color:#fff;font-weight:500;line-height:1.45}
.reply{display:grid;grid-template-columns:30px minmax(0,1fr);gap:10px;align-items:start}
.avatar{width:30px;height:30px;border-radius:10px;display:grid;place-items:center;background:var(--surface);border:1px solid var(--line)}
.avatar .mark{width:18px;height:18px}
.result{padding:12px 14px;border-radius:16px;background:var(--surface);border:1px solid var(--line)}
.result-head{display:flex;align-items:center;gap:8px;font-weight:700;font-size:.9375rem}
.result-head .i{color:var(--teal)}
.result-src{margin-left:auto;font:700 .625rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:10px}
.chip{padding:4px 10px;border-radius:var(--pill);background:var(--cream);border:1px solid var(--line);font-size:.8125rem;font-weight:600}
.amount{margin-left:auto;font:700 1.0625rem/1.2 var(--mono)}
.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
.figures dt{font-size:.75rem;color:var(--ink-2)}
.figures dd{margin-top:2px;font:700 .9375rem/1.2 var(--mono);white-space:nowrap}
.meter{height:8px;margin-top:12px;border-radius:var(--pill);background:rgba(25,60,87,.08);overflow:hidden}
.meter span{display:block;height:100%;width:5.4%;border-radius:inherit;background:var(--teal);transform-origin:left center}
.meter-note{margin-top:6px;font-size:.75rem;color:var(--ink-2)}
.memory{display:flex;align-items:center;gap:10px;margin:2px 0 2px 26px;padding:10px 0;font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.memory::before{content:"";align-self:stretch;width:2px;min-height:26px;background:repeating-linear-gradient(var(--line-2) 0 4px,transparent 4px 8px)}
.memory .i{width:16px;height:16px;color:var(--teal)}
.demo figcaption{margin-top:10px;font-size:.75rem;color:var(--ink-2)}
.prompts{list-style:none;padding:0;margin-top:16px;display:grid;grid-template-columns:minmax(0,1fr);gap:10px}
.prompt{padding:12px 14px;border-radius:16px;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow-s)}
.kicker{display:flex;align-items:center;gap:7px;font:700 .6875rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2)}
.kicker::before{content:"";width:8px;height:8px;border-radius:2px;background:var(--k)}
.prompt q{display:block;margin-top:7px;font-weight:600;font-size:.9375rem;line-height:1.45;quotes:"\\201C" "\\201D"}
.k-yellow{--k:var(--yellow);--kt:var(--t-yellow)}.k-red{--k:var(--red);--kt:var(--t-red)}.k-teal{--k:var(--teal);--kt:var(--t-teal)}.k-purple{--k:var(--purple);--kt:var(--t-purple)}
.steps{list-style:none;padding:0;margin-top:16px;display:grid;grid-template-columns:minmax(0,1fr);gap:10px;counter-reset:step}
.step{display:grid;grid-template-columns:40px minmax(0,1fr);gap:12px;align-items:start;padding:14px;border-radius:16px;background:rgba(255,255,255,.66);border:1px solid var(--line)}
.num{display:grid;place-items:center;width:40px;height:40px;border-radius:12px;background:var(--kt);font:700 .875rem/1 var(--mono)}
.step h3,.trust-item h3{font:700 1rem/1.3 var(--ui)}
.step p{margin-top:3px;font-size:.875rem;line-height:1.5;color:var(--ink-2)}
.privacy{display:grid;grid-template-columns:20px minmax(0,1fr);gap:10px;margin-top:14px;padding:12px 14px;border-radius:14px;background:var(--t-teal);font-size:.875rem;line-height:1.5;font-weight:600}
.trust-list{list-style:none;padding:0;margin-top:16px;display:grid;grid-template-columns:minmax(0,1fr);gap:16px}
.trust-item{display:grid;grid-template-columns:38px minmax(0,1fr);gap:12px;align-items:start}
.trust-icon{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:var(--surface);border:1px solid var(--line)}
.trust-item p{margin-top:3px;font-size:.8125rem;line-height:1.5;color:var(--ink-2)}
.foot{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;max-width:580px;margin:48px auto 0;padding-top:18px;border-top:1px solid var(--line);font-size:.8125rem;color:var(--ink-2)}
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
@media (max-width:479px){.figures dd{font-size:.8125rem}}
@media (max-width:359px){.figures{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (min-width:560px){.prompts,.steps,.trust-list{grid-template-columns:repeat(2,minmax(0,1fr))}.auth-card{padding:32px 32px 28px}.problem-card{padding:40px 40px 32px}}
@media (min-width:640px){.page{padding:28px 32px 40px}.logo{height:34px}}
@media (min-width:1040px){
.layout{max-width:none;grid-template-columns:minmax(0,1fr) minmax(420px,484px);grid-template-areas:"hero auth" "demo auth" "ask auth" "how auth" "trust auth";grid-template-rows:auto auto auto auto 1fr;column-gap:64px;row-gap:48px}
.auth{align-self:start}.hero{padding-top:12px}.lede{font-size:1.1875rem}.foot,.topbar{max-width:none}
.demo{max-width:600px}}
@media (min-width:1040px) and (min-height:1020px){.auth{position:sticky;top:24px}}
@media (prefers-reduced-motion:no-preference) and (min-width:1040px){
.rise{animation:rise .6s cubic-bezier(.2,.7,.2,1) both;animation-delay:var(--d,0s)}
.meter span{animation:grow 1.1s cubic-bezier(.2,.7,.2,1) both;animation-delay:2.3s}}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media (forced-colors:active){.meter span{background:Highlight}.btn-primary,.tabs a[aria-current=page]{border:1px solid ButtonText}.kicker::before,.rules li::before{background:CanvasText}}
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


def _auth_card(view: LoginView) -> str:
    client = e(view.client_name)
    if view.register:
        title = "Create your MITA account"
        sub = f"Your budget, expenses and goals will live in this account, and {client} will connect to it."
        submit_value, submit_label = REGISTER, "Create account and connect"
        switch = (
            "Already have a MITA account? "
            f'<a href="{e(_login_href(view.req, False))}">Sign in</a>'
        )
    else:
        title = f"Connect MITA to {client}"
        sub = "Sign in with your MITA email and password — not your ChatGPT login."
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

    scope_items = "".join(
        f'<li>{icon("check-circle")}<span>'
        f'<span class="scope-title">{e(SCOPE_TITLES.get(s, s))}</span>'
        f'<span class="scope-detail">{e(SCOPE_DESCRIPTIONS.get(s, ""))}</span></span></li>'
        for s in view.scopes
    )
    checked = " checked" if view.usage_stats else ""
    help_html = (
        f'<p class="help">Need help? <a href="{e(view.support_url)}" target="_blank" '
        'rel="noopener noreferrer">Contact MITA support</a></p>'
        if view.support_url
        else ""
    )

    return f"""<section class="auth" aria-labelledby="auth-title"><div class="card auth-card">
<div class="pair" aria-hidden="true"><span class="app">{logo_mark()}</span><span class="pair-link">{icon("link")}</span><span class="app app-gpt">{icon("chat")}</span></div>
<h2 id="auth-title">{title}</h2>
<p class="sub">{sub}</p>
<nav class="tabs" aria-label="MITA account">{tabs}</nav>
{error_html}
<form method="post" action="{LOGIN_PATH}" autocomplete="on">
<input type="hidden" name="req" value="{e(view.req)}">
<input type="hidden" name="csrf" value="{e(view.csrf)}">
{mode_field}{email}{password}
<div class="consent" role="group" aria-labelledby="consent-title">
<h3 id="consent-title">{client} will be able to</h3>
<ul class="scopes">{scope_items}</ul>
<p class="limits">{icon("ban")}<span>{e(CANNOT_MOVE_MONEY)}</span></p>
</div>
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


def _hero() -> str:
    return (
        '<section class="hero" aria-labelledby="hero-title">'
        '<p class="eyebrow">Budgets · expenses · goals</p>'
        '<h1 id="hero-title">Your finances, <span class="hl">remembered</span> in ChatGPT.</h1>'
        '<p class="lede">MITA keeps your budget, expenses, recurring costs and savings goals '
        "in your MITA account, so ChatGPT can use them in any conversation — "
        "no starting from scratch.</p></section>"
    )


def _demo() -> str:
    mita = f'<span class="avatar">{logo_mark()}</span>'
    return f"""<section class="demo" aria-labelledby="demo-title">
<h2 class="vh" id="demo-title">Example: MITA in two ChatGPT conversations</h2>
<figure>
<div class="convo rise" style="--d:.15s">
<p class="convo-label"><span>Conversation · Monday</span><span class="example">Example</span></p>
<p class="bubble rise" style="--d:.45s">I spent €36.80 at Lidl today.</p>
<div class="reply rise" style="--d:.9s">{mita}<div class="result">
<p class="result-head">{icon("check-circle")}Expense recorded<span class="result-src">MITA</span></p>
<p class="chips"><span class="chip">Groceries</span><span class="chip">Lidl</span><span class="amount">€36.80</span></p>
</div></div></div>
<p class="memory rise" style="--d:1.35s">{icon("database")}Saved in your MITA account</p>
<div class="convo rise" style="--d:1.6s">
<p class="convo-label"><span>New conversation · Friday</span><span class="example">Example</span></p>
<p class="bubble rise" style="--d:1.85s">How am I doing against my budget?</p>
<div class="reply rise" style="--d:2.2s">{mita}<div class="result">
<p class="result-head">{icon("chart")}This month’s budget<span class="result-src">MITA</span></p>
<dl class="figures"><div><dt>Budget</dt><dd>€2,325.00</dd></div><div><dt>Spent</dt><dd>€126.50</dd></div><div><dt>Left</dt><dd>€2,198.50</dd></div></dl>
<div class="meter" aria-hidden="true"><span></span></div>
<p class="meter-note">5% of this month’s budget used</p>
</div></div></div>
<figcaption>An example of how it looks. All figures are fictional.</figcaption>
</figure></section>"""


def _ask() -> str:
    items = "".join(
        f'<li class="prompt k-{color}"><span class="kicker">{e(kind)}</span><q>{e(text)}</q></li>'
        for kind, color, text in PROMPTS
    )
    return (
        '<section class="ask" aria-labelledby="ask-title">'
        '<h2 class="section-title" id="ask-title">What can I ask MITA?</h2>'
        '<p class="section-lede">Once MITA is connected, just talk to ChatGPT. For example:</p>'
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
        f"{_hero()}{_auth_card(view)}{_demo()}{_ask()}{_how()}{_trust()}"
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
