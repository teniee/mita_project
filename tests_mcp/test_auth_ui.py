"""The ChatGPT sign-in / sign-up / consent page and its error pages.

What the redesign must keep: no script and nothing third-party, every value
escaped, the same protocol (codes, redirects, statuses), generic failures.
What it adds and must keep true: labelled fields wired to their errors,
password hints that are the policy, every granted scope in plain language,
a page instead of JSON for a person on a refused /authorize, a page instead
of a 500 when the database is down, only real, supported example prompts —
on the page, never behind a tap — and one labelled example whose figures are
what MITA's forecast engine returns: the hero, the sentences to type and the
sign-in form first, everything secondary after them, details closed.
"""

import json
import logging
import re
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.password_policy import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    password_policy_violation,
)
from app.mcp.auth import pages
from app.mcp.auth.scopes import SCOPE_DESCRIPTIONS, SCOPE_TITLES, SUPPORTED_SCOPES
from app.mcp.tools import PUBLISHED_TOOLS
from app.services.core.engine.budget_forecast_engine import (
    DailyPlanData,
    commitment_expectations,
    compute_forecast,
)
from app.services.monthly_obligations import due_in_month
from tests_mcp.conftest import PASSWORD, Harness, make_settings
from tests_mcp.test_oauth_flow import REDIRECT, authorize, csrf_from, pkce, register

ALL_SCOPES = " ".join(SUPPORTED_SCOPES)
BROWSER = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
SUPPORT = "https://support.example.test"


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def parse(html: str) -> _Tags:
    parsed = _Tags()
    parsed.feed(html)
    return parsed


def element(page: _Tags, id_: str) -> dict:
    return next(attrs for _, attrs in page.tags if attrs.get("id") == id_)


def visible_text(html: str) -> str:
    without_style = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    return " ".join(" ".join(parse(without_style).text).split())


async def _login_url(http, scope=ALL_SCOPES, **register_extra):
    client_id = (await register(http, **register_extra)).json()["client_id"]
    _, challenge = pkce()
    redirect = await authorize(http, client_id, challenge, scope=scope)
    assert redirect.status_code == 302, redirect.text
    return redirect.headers["location"]


async def _post(http, login_url, page, **data):
    req = parse_qs(urlparse(login_url).query)["req"][0]
    return await http.post(
        "/oauth/login", data={"req": req, "csrf": csrf_from(page.text), **data}
    )


# --- no script, nothing third-party ----------------------------------------------


@pytest.mark.parametrize("mode", ["", "&mode=register"])
async def test_page_runs_no_script_and_loads_nothing_third_party(mcp, mode):
    async with mcp.http() as http:
        page = await http.get(await _login_url(http) + mode)
    assert page.status_code == 200
    html = page.text
    assert "<script" not in html.lower()
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", html, re.I)  # no inline handlers

    csp = page.headers["content-security-policy"]
    assert "script-src" not in csp
    for directive in (
        "default-src 'none'",
        "img-src 'self'",
        "font-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self' https://chatgpt.com",
    ):
        assert directive in csp, directive

    parsed = parse(html)
    for tag, attrs in parsed.tags:
        for name in ("href", "src", "action", "srcset", "poster", "data"):
            value = attrs.get(name)
            if value is None:
                continue
            # Same-page anchors (the hero's jump to the form) stay on the page.
            assert value.startswith(("/", "#")) or value == SUPPORT, (tag, name, value)
    for url in re.findall(r"url\(([^)]*)\)", html):
        assert url.startswith(pages.ASSET_PREFIX), url


async def test_every_asset_the_page_uses_is_served_immutable(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
        urls = set(re.findall(r'(/oauth/assets/[^"\')\s]+)', html))
        assert {urlparse(u).path.rsplit("/", 1)[1] for u in urls} == set(
            pages.ASSETS.names()
        )
        for url in urls:
            response = await http.get(url)
            assert response.status_code == 200, url
            assert response.headers["content-type"] in (
                "font/woff2",
                "image/svg+xml",
                "image/webp",
            )
            assert "immutable" in response.headers["cache-control"]
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["cross-origin-resource-policy"] == "same-origin"
            if response.headers["content-type"] == "image/svg+xml":
                assert (
                    response.headers["content-security-policy"] == "default-src 'none'"
                )
                assert b"<script" not in response.content


@pytest.mark.parametrize(
    "name",
    [
        "login.py",
        "..%2Flogin.py",
        "..%2F..%2Fserver.py",
        "fonts",
        "Manrope-OFL.license",
        "manrope.woff2%00.py",
        "MANROPE.WOFF2",
    ],
)
async def test_only_known_asset_names_are_served(mcp, name):
    async with mcp.http() as http:
        response = await http.get(f"/oauth/assets/{name}")
    assert response.status_code == 404
    assert response.content in (b"", b"Not Found")  # ours, or the router's


# --- fields, labels, password managers --------------------------------------------


async def test_sign_in_fields_are_labelled_for_people_and_password_managers(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    page = parse(html)
    labels = {attrs.get("for") for tag, attrs in page.tags if tag == "label"}
    email, password = element(page, "email"), element(page, "password")
    assert {"email", "password"} <= labels
    assert email["type"] == "email" and email["autocomplete"] == "username"
    assert "required" in email
    assert password["type"] == "password"
    assert password["autocomplete"] == "current-password"
    assert "autofocus" not in email and "autofocus" not in password
    assert 'name="password_confirm"' not in html
    assert '<label class="check"><input type="checkbox" name="usage_stats"' in html


async def test_sign_up_fields_carry_the_password_policy(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http) + "&mode=register")).text
    page = parse(html)
    labels = {attrs.get("for") for tag, attrs in page.tags if tag == "label"}
    assert {"email", "password", "password_confirm"} <= labels
    for field in ("password", "password_confirm"):
        attrs = element(page, field)
        assert attrs["autocomplete"] == "new-password"
        assert attrs["minlength"] == str(MIN_PASSWORD_LENGTH)
        assert attrs["maxlength"] == str(MAX_PASSWORD_LENGTH)
    assert element(page, "password")["passwordrules"] == pages.PASSWORD_RULES_ATTR
    assert "password-rules" in element(page, "password")["aria-describedby"]
    rules = visible_text(html)
    for rule in pages.PASSWORD_RULES:
        assert rule in rules


def test_the_password_hints_are_the_policy():
    """Each shown rule is one check of password_policy_violation, no more."""
    assert len(pages.PASSWORD_RULES) == 4
    assert str(MIN_PASSWORD_LENGTH) in pages.PASSWORD_RULES[0]
    assert f"minlength: {MIN_PASSWORD_LENGTH};" in pages.PASSWORD_RULES_ATTR
    assert f"maxlength: {MAX_PASSWORD_LENGTH};" in pages.PASSWORD_RULES_ATTR
    meets_all = "Abcdef1!"
    assert len(meets_all) == MIN_PASSWORD_LENGTH
    assert password_policy_violation(meets_all) is None
    for breaks_one in (
        "Abcde1!",  # too short
        "abcdef1!",  # no upper case
        "ABCDEF1!",  # no lower case
        "Abcdefg!",  # no number
        "Abcdefg1",  # no symbol
        "Ab1!" + "x" * MAX_PASSWORD_LENGTH,  # too long
    ):
        assert password_policy_violation(breaks_one) is not None, breaks_one


# --- consent ---------------------------------------------------------------------------


def test_every_scope_has_plain_language_and_the_five_scopes_are_unchanged():
    assert SUPPORTED_SCOPES == (
        "profile:read",
        "finance:read",
        "finance:write",
        "feedback:write",
        "profile:write",
    )
    assert set(SCOPE_TITLES) == set(SUPPORTED_SCOPES) == set(SCOPE_DESCRIPTIONS)


async def test_consent_shows_exactly_the_scopes_being_granted(mcp):
    async with mcp.http() as http:
        everything = visible_text((await http.get(await _login_url(http))).text)
        reads_only = visible_text(
            (
                await http.get(
                    await _login_url(http, scope="profile:read finance:read")
                )
            ).text
        )
    assert "ChatGPT will be able to" in everything
    for scope in SUPPORTED_SCOPES:
        assert SCOPE_TITLES[scope] in everything
        assert SCOPE_DESCRIPTIONS[scope] in everything
    for scope in ("profile:read", "finance:read"):
        assert SCOPE_TITLES[scope] in reads_only
    for scope in ("finance:write", "feedback:write", "profile:write"):
        assert SCOPE_TITLES[scope] not in reads_only
    for page in (everything, reads_only):
        assert pages.CANNOT_MOVE_MONEY in page
        assert pages.FORGERY_WARNING_LEAD in page and pages.FORGERY_WARNING in page


async def test_consent_titles_are_on_screen_and_the_details_one_tap_away(mcp):
    """Every scope title is listed outside the disclosure; the longer
    explanation of each is in a native, closed <details> (no script)."""
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    listed = re.search(r'<ul class="scopes">(.*?)</ul>', html, re.S).group(1)
    disclosure = re.search(r'<details class="perm">(.*?)</details>', html, re.S)
    assert disclosure and '<details class="perm" open' not in html
    assert "<summary>View permission details</summary>" in disclosure.group(1)
    for scope in SUPPORTED_SCOPES:
        assert pages.e(SCOPE_TITLES[scope]) in listed
        assert pages.e(SCOPE_DESCRIPTIONS[scope]) not in listed
        assert pages.e(SCOPE_DESCRIPTIONS[scope]) in disclosure.group(1)
    assert pages.e(pages.CANNOT_MOVE_MONEY) in disclosure.group(1)
    # The short line on screen restates the full sentence, nothing more.
    on_screen = re.search(
        r'<div class="consent"(.*?)<details class="perm">', html, re.S
    )
    assert pages.e(pages.CANNOT_MOVE_MONEY_SHORT) in on_screen.group(1)
    assert "move money" in pages.CANNOT_MOVE_MONEY_SHORT


async def test_enter_signs_in_and_cancel_skips_validation(mcp):
    """The first submit button is the default for Enter: it must be the
    primary action, not Cancel."""
    async with mcp.http() as http:
        url = await _login_url(http)
        for mode, primary in (("", "allow"), ("&mode=register", "register")):
            page = parse((await http.get(url + mode)).text)
            buttons = [attrs for tag, attrs in page.tags if tag == "button"]
            assert [b["value"] for b in buttons] == [primary, "deny"]
            assert all(b["type"] == "submit" for b in buttons)
            assert "formnovalidate" in buttons[1] and "formnovalidate" not in buttons[0]


async def test_a_hostile_client_name_is_text_everywhere(mcp):
    hostile = "<img src=x onerror=alert(1)>\"&'</title>"
    async with mcp.http() as http:
        url = await _login_url(http, client_name=hostile)
        for mode in ("", "&mode=register"):
            html = (await http.get(url + mode)).text
            assert "<img src=x" not in html and '</title>"' not in html
            assert "&lt;img src=x onerror=alert(1)&gt;" in html
            assert html.count("<title>") == 1 and html.count("</title>") == 1


# --- errors tied to their fields ---------------------------------------------------------


async def test_a_sign_in_failure_marks_both_fields_identically_for_any_cause(mcp, seed):
    user = await seed.user()
    pages_by_cause = []
    async with mcp.http() as http:
        url = await _login_url(http)
        for email in (user.email, "nobody-at-all@example.test"):
            page = await http.get(url)
            response = await _post(
                http, url, page, email=email, password="Wrong-Pass-1!", action="allow"
            )
            assert response.status_code == 400
            pages_by_cause.append(parse(response.text))
    marks = []
    for page in pages_by_cause:
        alert = element(page, "form-error")
        assert alert["role"] == "alert"
        email, password = element(page, "email"), element(page, "password")
        for field in (email, password):
            assert field["aria-invalid"] == "true"
            assert "form-error" in field["aria-describedby"].split()
        assert "autofocus" in password and "autofocus" not in email
        marks.append(
            [
                {k: v for k, v in attrs.items() if k != "value"}
                for tag, attrs in page.tags
                if tag == "input" and attrs.get("name") in ("email", "password")
            ]
        )
    assert marks[0] == marks[1]


async def test_a_sign_up_error_marks_only_the_field_it_is_about(mcp):
    async with mcp.http() as http:
        url = await _login_url(http)
        page = await http.get(url + "&mode=register")
        mismatch = parse(
            (
                await _post(
                    http,
                    url,
                    page,
                    email="mismatch-ui@example.test",
                    password="Fresh-Start-2026!",
                    password_confirm="Other-Start-2026!",
                    action="register",
                )
            ).text
        )
    assert element(mismatch, "password_confirm")["aria-invalid"] == "true"
    assert "autofocus" in element(mismatch, "password_confirm")
    assert "aria-invalid" not in element(mismatch, "email")
    assert "aria-invalid" not in element(mismatch, "password")


# --- error pages ---------------------------------------------------------------------------


async def test_an_expired_link_gets_a_branded_page_that_reveals_nothing(mcp):
    async with mcp.http() as http:
        response = await http.get("/oauth/login", params={"req": "forged.deadbeef"})
    assert response.status_code == 400
    assert "This sign-in link has expired" in response.text
    assert "10 minutes" in response.text
    assert "forged" not in response.text and "<form" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "form-action 'self';" in response.headers["content-security-policy"]


async def test_authorize_refusals_are_a_page_for_a_person_and_json_for_a_client(mcp):
    async with mcp.http() as http:
        _, challenge = pkce()
        params = {
            "response_type": "code",
            "client_id": "no-such-client-7f3a",
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "s",
        }
        machine = await http.get("/authorize", params=params)
        person = await http.get("/authorize", params=params, headers=BROWSER)

        client_id = (await register(http)).json()["client_id"]
        evil = dict(params, client_id=client_id, redirect_uri="https://evil.example/cb")
        evil_person = await http.get("/authorize", params=evil, headers=BROWSER)
        good_person = await http.get(
            "/authorize", params=dict(params, client_id=client_id), headers=BROWSER
        )
        # An error the SDK can send back to ChatGPT still goes back to ChatGPT.
        bad_scope = await http.get(
            "/authorize",
            params=dict(params, client_id=client_id, scope="admin:all"),
            headers=BROWSER,
        )

    assert machine.status_code == 400 and machine.json()["error"] == "invalid_request"
    assert person.status_code == 400 and "location" not in person.headers
    assert person.headers["content-type"].startswith("text/html")
    assert "We couldn’t continue this connection" in person.text
    assert "Error reference: invalid_request" in person.text
    assert "no-such-client-7f3a" not in person.text
    assert person.headers["cache-control"] == "no-store"
    assert person.headers["x-frame-options"] == "DENY"
    assert "script-src" not in person.headers["content-security-policy"]

    assert evil_person.status_code == 400 and "location" not in evil_person.headers
    assert "evil.example" not in evil_person.text

    assert good_person.status_code == 302
    assert good_person.headers["location"].startswith(
        "https://mcp.example.test/oauth/login?req="
    )
    assert bad_scope.status_code == 302
    assert bad_scope.headers["location"].startswith(REDIRECT)


async def test_authorize_rate_limit_is_a_page_for_a_person(make_service):
    harness = Harness(make_service, make_settings(oauth_requests_per_minute=1))
    async with harness.http() as http:
        await http.get("/authorize", params={"client_id": "x"})
        person = await http.get(
            "/authorize", params={"client_id": "x"}, headers=BROWSER
        )
        machine = await http.get("/authorize", params={"client_id": "x"})
    assert person.status_code == 429
    assert person.headers["retry-after"] == "60"
    assert "Too many connection attempts" in person.text
    assert machine.status_code == 429 and machine.json()["error"] == "rate_limited"


def _driver_error(email: str) -> OperationalError:
    return OperationalError(
        "SELECT * FROM users WHERE email = %(email)s",
        {"email": email},
        ConnectionRefusedError("database unreachable"),
    )


async def test_a_database_outage_on_the_form_is_a_page(mcp, monkeypatch):
    async with mcp.http() as http:
        url = await _login_url(http)

        async def down(client_id):
            raise _driver_error("x@example.test")

        monkeypatch.setattr(http.mita_service.provider, "get_client", down)
        response = await http.get(url + "&mode=register")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"
    assert response.headers["cache-control"] == "no-store"
    assert "MITA is temporarily unavailable" in response.text
    retry = parse(response.text)
    href = next(
        a["href"]
        for t, a in retry.tags
        if t == "a" and a.get("class") == "btn btn-primary"
    )
    query = parse_qs(urlparse(href).query)
    assert urlparse(href).path == "/oauth/login"
    assert query["req"] == parse_qs(urlparse(url).query)["req"]
    assert query["mode"] == ["register"]


async def test_a_database_outage_at_sign_in_issues_no_code_and_logs_no_data(
    mcp, seed, connection, monkeypatch, caplog
):
    import app.mcp.auth.login as login_module

    user = await seed.user()

    async def down(session, email, password):
        raise _driver_error(email)

    caplog.set_level(logging.INFO)
    async with mcp.http() as http:
        url = await _login_url(http)
        page = await http.get(url)
        monkeypatch.setattr(login_module, "verify_login_credentials", down)
        response = await _post(
            http, url, page, email=user.email, password=PASSWORD, action="allow"
        )
    assert response.status_code == 503 and "location" not in response.headers
    assert "MITA is temporarily unavailable" in response.text
    codes = (
        await connection.execute(
            text(
                "SELECT count(*) FROM mcp_oauth_authorization_codes WHERE user_id = :u"
            ),
            {"u": user.id},
        )
    ).scalar_one()
    assert codes == 0
    records = [
        r
        for r in caplog.records
        if getattr(r, "event", "") == "oauth_login_unavailable"
    ]
    assert records and records[0].error_class == "OperationalError"
    logged = "\n".join(
        f"{r.getMessage()} {json.dumps(r.__dict__, default=str)}"
        for r in caplog.records
    )
    assert user.email not in logged and PASSWORD not in logged


# --- the product story states only what MITA does ---------------------------------------

# Every sentence the page tells a person to type and the published tool that
# answers it (rent, the lunch fix, dinner out and the last 30 days are golden
# prompts en-07, en-09, en-12 and en-20).
PROMPT_TOOLS = {
    "Help me build my monthly budget.": "preview_monthly_budget",
    "I spent €36.80 on groceries today.": "add_transaction",
    # safe_daily_limit: what is left of the month's plan per day after today
    "How much can I safely spend per day?": "get_budget_forecast",
    "Create an Emergency Fund goal for €3,000.": "create_savings_goal",
    "Where did my money go in the last 30 days?": "get_spending_breakdown",
    "Show my financial calendar for this month.": "show_financial_calendar",
    "My rent is €700 every month on the first.": "add_recurring_expense",
    "Oops, that lunch was €12, not €21.": "update_transaction",
    "Can I afford dinner out tonight?": "get_budget_status",
    "How has my spending changed over the last six months?": "get_spending_history",
}

# The page's last word, "With MITA, ChatGPT answers from your real month": the
# tools that read the person's own recorded month.
REAL_MONTH_TOOLS = (
    "get_budget_status",
    "get_budget_forecast",
    "list_transactions",
    "show_financial_calendar",
)

# Words for the people who build MITA, not the people who use it.
JARGON = (
    r"\bMCP\b",
    r"\btools?\b",
    r"\bAPI\b",
    r"forecast engine",
    r"\bOAuth\b",
    r"\bendpoints?\b",
    r"\bscopes?\b",
    r"\btokens?\b",
)


async def test_the_page_shows_real_prompts_fictional_figures_and_no_overclaims(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    words = visible_text(html)
    assert set(pages.PROMPTS) == set(PROMPT_TOOLS)
    for prompt, tool in PROMPT_TOOLS.items():
        assert prompt in words
        assert tool in PUBLISHED_TOOLS
    assert "With MITA, ChatGPT answers from your real month" in words
    assert set(REAL_MONTH_TOOLS) <= set(PUBLISHED_TOOLS)
    assert "Fictional example" in words
    assert pages.DEMO_CAPTION in words and pages.MONTH_CAPTION in words
    assert "It does not store your ChatGPT conversations" in words
    # The story is told in a person's words; the consent card names permissions.
    story = visible_text(
        "".join(
            html.split(f'<section class="{name}"', 1)[1].split("</section>", 1)[0]
            for name in ("hero", "ask", "trust", "month", "more", "close")
        )
    )
    for word in JARGON:
        assert not re.search(word, story, re.I), word
    # The forecast's status is not shown: its linear pace counts rent paid on
    # the 1st as daily spending, so it can mislead until that model is fixed.
    assert not re.search(r"\bon[ _]track\b|\bdanger\b", words, re.I)
    # The forecast gives one amount per remaining day — never "today's" safe
    # amount or a budget per date.
    assert not re.search(
        r"safe(ly)? (to )?spend today|budget for (each|every) day", words, re.I
    )
    for claim in (
        r"bank[- ]grade",
        r"military[- ]grade",
        r"zero[- ]knowledge",
        r"end[- ]to[- ]end",
        r"\bencrypt",
        r"\bread[- ]only\b",
        r"\b(free|premium|trial|pricing)\b",
        r"\b(customers?|testimonial|families trust)\b",
    ):
        assert not re.search(claim, words, re.I), claim


async def test_the_sentences_to_type_are_on_the_page_not_behind_a_tap(mcp):
    """Four different abilities right after the hero and before the form,
    the rest lower down, and the hero's own question nowhere else: each
    sentence once. All quoted text on the page: none inside a <details>, none
    a fake control."""
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text

    def section(name: str) -> str:
        return html.split(f'<section class="{name}"', 1)[1].split("</section>", 1)[0]

    ask, more = section("ask"), section("more")
    for part in (ask, more):
        assert "<details" not in part and "<button" not in part and "<a " not in part
    primary = [card.prompt for card in pages.PROMPT_CARDS]
    assert len(primary) == 4 and all(card.result for card in pages.PROMPT_CARDS)
    assert {pages.BUDGET_PROMPT, pages.AFFORD_PROMPT} <= set(primary)
    assert pages.SAFE_PROMPT not in primary
    assert f'<p class="q">{pages.e(pages.SAFE_PROMPT)}</p>' in section("hero")
    assert len(set(pages.PROMPTS)) == len(pages.PROMPTS)
    for prompt in primary:
        assert f"<q>{pages.e(prompt)}</q>" in ask, prompt
    for _, prompt in pages.MORE_PROMPTS:
        assert f"<q>{pages.e(prompt)}</q>" in more, prompt
    assert html.index('<section class="ask"') < html.index("<form ")


async def test_the_photograph_is_self_hosted_and_never_a_customer(mcp):
    """AI-generated for MITA (no real person), served from this service as
    WebP at two widths, described as an illustration, never captioned as a
    user or a testimonial."""
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
        img = next(attrs for tag, attrs in parse(html).tags if tag == "img")
        assert img["alt"].startswith("Illustration:")
        assert img["src"].startswith("/oauth/assets/hero-family-640.webp?v=")
        assert "hero-family-1100.webp" in img["srcset"]
        assert (img["width"], img["height"]) == ("1100", "733")
        for url in (img["src"], img["srcset"].split(", ")[1].split(" ")[0]):
            response = await http.get(url)
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/webp"
            assert len(response.content) < 120_000


async def test_motion_is_decorative_and_stops_under_reduced_motion(mcp):
    """CSS only (no script). Under prefers-reduced-motion every animation and
    transition is off and the decorative flying expense is hidden; nothing
    but that decorative element starts invisible, so the page is complete
    without any motion."""
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    css = pages._CSS
    reduced = css.split("@media (prefers-reduced-motion:reduce){", 1)[1].split("}\n")[0]
    assert "animation:none!important" in reduced
    assert "transition:none!important" in reduced
    assert ".flyer{display:none}" in reduced
    without_keyframes = re.sub(r"@keyframes [a-z-]+\{.*?\}\}", "", css, flags=re.S)
    hidden = re.findall(r"([^{}]+)\{[^{}]*opacity:0[;}]", without_keyframes)
    assert [rule.strip() for rule in hidden] == [".flyer"], hidden
    assert "@media (prefers-reduced-motion:reduce)" in html
    assert re.search(r":focus-visible[^{]*\{outline:3px solid", html)
    assert html.count("@font-face") == 4 and "font-display:swap" in html


# --- the example is MITA's arithmetic -----------------------------------------------


def _money(text_value: str) -> Decimal:
    return Decimal(text_value.replace(",", "").replace("€", ""))


def test_the_example_month_is_what_mitas_code_computes():
    """The fictional month: MITA's layout (month_calendar) of the stated
    allocations, the expenses as recorded, and every figure on the page from
    the forecast engine and the calendar builder — recomputed here."""
    from app.mcp.auth import demo
    from app.services.monthly_plan_service import month_calendar

    layout = month_calendar(
        demo.YEAR, demo.MONTH, {k: Decimal(v) for k, v in demo.ALLOCATIONS.items()}
    )
    planned = {
        (date.fromisoformat(day), category): Decimal(str(amount))
        for day, categories in layout.items()
        for category, amount in categories.items()
    }
    spent_rows = [
        DailyPlanData(
            date(demo.YEAR, demo.MONTH, day), category, Decimal(0), Decimal(amount)
        )
        for day, category, amount in demo.EXPENSES
    ]
    plan_rows = [
        DailyPlanData(day, category, amount, Decimal(0))
        for (day, category), amount in planned.items()
    ]
    # The bills come first (owner decision 2026-10-25): each mandatory line's
    # plan, or its saved payments due in October when more.
    due = {}
    for payment in demo.PAYMENTS:
        amount = due_in_month(
            payment.amount, payment.anchor, payment.recurrence, demo.YEAR, demo.MONTH
        )
        if amount > 0:
            due[payment.category] = due.get(payment.category, Decimal(0)) + amount
    result = compute_forecast(
        daily_plans=plan_rows + spent_rows,
        goals=[],
        year=demo.YEAR,
        month=demo.MONTH,
        today=demo.TODAY,
        commitments=commitment_expectations(
            {k: Decimal(v) for k, v in demo.ALLOCATIONS.items()}, due
        ),
    )
    f = pages.FIGURES
    assert demo.TODAY.strftime("%A") == "Monday"
    assert result.days_remaining == f.days_left == 12
    assert result.savings_set_aside == _money(f.savings) == Decimal("400.00")
    # Rent and utilities are recorded; the internet bill (30.00, 27 Oct) is held.
    assert result.commitments_reserved == Decimal("30.00")
    assert result.safe_daily_limit == _money(f.per_day) == Decimal("59.60")
    assert result.total_planned == Decimal("2340.00")
    assert result.total_spent == Decimal("1194.84")
    groceries = sum(
        (Decimal(a) for _, c, a in demo.EXPENSES if c == "groceries"), Decimal(0)
    )
    assert groceries == _money(f.groceries_spent)
    assert Decimal(demo.ALLOCATIONS["groceries"]) == _money(f.groceries_planned)
    assert (f.bill_name, f.bill_amount, f.bill_date) == (
        "Home internet",
        "30.00",
        "27 Oct",
    )


def test_the_example_would_not_trigger_mitas_rebalancing():
    """MITA's automatic rebalancing acts on a date whose category goes over
    its plan, and an expense category with another name than its plan line
    counts as unplanned (backend finding F-2). The example avoids both, so the
    plan it shows is the plan MITA would hold."""
    from app.mcp.auth import demo
    from app.services.monthly_plan_service import month_calendar

    layout = month_calendar(
        demo.YEAR, demo.MONTH, {k: Decimal(v) for k, v in demo.ALLOCATIONS.items()}
    )
    for day, category, amount in demo.EXPENSES:
        key = date(demo.YEAR, demo.MONTH, day).isoformat()
        assert category in demo.ALLOCATIONS, category
        assert Decimal(amount) <= Decimal(str(layout[key].get(category, 0))), (
            day,
            category,
        )
        assert date(demo.YEAR, demo.MONTH, day) <= demo.TODAY


async def test_the_example_calendar_shows_each_date_as_mita_computes_it(mcp):
    """Past dates: what was spent; today marked; dates ahead: their plan
    (dashed), never a forecast; the bill due; everything labelled fictional."""
    from app.mcp.auth.demo import DEMO

    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    slab = re.search(r'<ol class="slab-days">(.*?)</ol>', html, re.S).group(1)
    cells = re.findall(r'<li class="d([^"]*)"[^>]*><b>(\d+)</b><i>([^<]*)</i>', slab)
    assert len(cells) == len(DEMO.days) == 31
    for (classes, number, amount), day in zip(cells, DEMO.days):
        assert int(number) == day.day.day
        if day.kind == "future":
            assert " f" in classes
            assert amount == (f"{day.planned:.2f}" if day.planned else "")
        else:
            assert " f" not in classes
            assert (" t" in classes) == (day.kind == "today")
            shown = f"{day.spent:,.0f}" if day.spent >= 1000 else f"{day.spent:.2f}"
            assert amount == (shown if day.spent else "")
        assert (" bill" in classes) == (day.day == date(2026, 10, 27))
    hero = html.split('<section class="hero"', 1)[1].split("</section>", 1)[0]
    words = visible_text(hero)
    f = pages.FIGURES
    for figure in (
        f"€{f.per_day}",
        f"€{f.savings}",
        f"€{f.groceries_spent}",
        f"€{f.bill_amount}",
    ):
        assert figure in words, figure
    assert f"a day · {f.days_left} days left" in words
    assert words.count("Fictional example") >= 2  # the label and the caption


async def test_the_logo_is_the_master_vector_in_its_own_colours(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    topbar = html.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    logo = re.search(r'<svg class="logo".*?</svg>', topbar, re.S).group(0)
    master = pages._MARK_PATHS + pages._WORDMARK_PATH
    assert re.findall(r' d="([^"]+)"', logo) == re.findall(r' d="([^"]+)"', master)
    assert re.findall(r'fill="(#[0-9A-F]{6})"', logo) == re.findall(
        r'fill="(#[0-9A-F]{6})"', master
    )


async def test_the_hero_the_sentences_and_sign_in_come_first_details_stay_closed(
    mcp,
):
    """The phone's order is short — the person already chose to connect: the
    hero (headline, value, a question and MITA's answer, the jump to the
    form), four more things to ask, the sign-in form, what MITA keeps, the
    month, the rest of what you can ask, one closing line. From
    1040 px the hero and the questions are the main column, the form and what
    MITA keeps the side."""
    async with mcp.http() as http:
        login_url = await _login_url(http)
        html = (await http.get(login_url)).text
        register = (await http.get(login_url + "&mode=register")).text
    order = [
        html.index('<h1 id="hero-title">'),
        html.index('<p class="lede">'),
        html.index('<figure class="proof"'),
        html.index('<div class="cta">'),
        html.index('<section class="ask"'),
        html.index("<form "),
        html.index('<section class="trust"'),
        html.index('<section class="month"'),
        html.index('<section class="more"'),
        html.index('<section class="close"'),
    ]
    assert order == sorted(order)
    main, side = html.split('<div class="col col-main">', 1)[1].split(
        '<div class="col col-side">', 1
    )
    assert '<section class="ask"' in main and "<form " not in main
    assert "<form " in side.split('<section class="month"', 1)[0]
    headline = visible_text(html.split('<h1 id="hero-title">', 1)[1].split("</h1>")[0])
    assert headline == "Know what you can safely spend each day."
    assert 'href="#auth"' in html and 'id="auth"' in html
    details = re.findall(r"<details[^>]*>", html)
    assert len(details) == 2 and not any(" open" in d for d in details)
    # Removed and staying removed: the v3 example and limits grid, the v5 steps
    # and the "Why connect MITA?" comparison.
    for gone in (
        'class="snap"',
        "How is €",
        "Clear limits",
        'class="steps"',
        "Why connect",
        "Without MITA",
    ):
        assert gone not in html
    # What to ask first: the calendar after signing in, a budget for a new account.
    assert f"Then try: “{pages.CALENDAR_PROMPT}”" in html
    assert f"Then try: “{pages.BUDGET_PROMPT}”" in register


def test_the_layout_is_mobile_first():
    """The phone layout is the base; wider screens only add (min-width)."""
    css = pages._CSS
    base = css.split("@media")[0]
    assert ".layout,.col{display:grid;grid-template-columns:minmax(0,1fr);" in base
    assert "grid-template-areas" not in base  # phones: one column, document order
    widths = re.findall(r"@media \((min|max)-width:(\d+)px\)", css)
    assert ("max", "359") in widths
    assert all(kind == "min" for kind, px in widths if px != "359")
    desktop = css.split("@media (min-width:1040px){", 1)[1]
    assert "minmax(400px,440px)" in desktop and "minmax(400px,440px)" not in base
    assert '"main side" "more side"' in desktop
