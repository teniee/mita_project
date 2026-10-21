"""The ChatGPT sign-in / sign-up / consent page and its error pages.

What the redesign must keep: no script and nothing third-party, every value
escaped, the same protocol (codes, redirects, statuses), generic failures.
What it adds and must keep true: labelled fields wired to their errors,
password hints that are the policy, every granted scope in plain language,
a page instead of JSON for a person on a refused /authorize, a page instead
of a 500 when the database is down, and only real, supported example prompts.
"""

import json
import logging
import re
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
            assert value.startswith("/") or value == SUPPORT, (tag, name, value)
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
            assert response.headers["content-type"] in ("font/woff2", "image/svg+xml")
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

# Every example prompt and the published tool that answers it.
PROMPT_TOOLS = {
    "Help me build my monthly budget.": "preview_monthly_budget",
    "How am I doing against my budget this month?": "get_budget_status",
    "I spent €36.80 on groceries today.": "add_transaction",
    "Add the expenses from this receipt to MITA.": "add_transactions",
    "What recurring expenses do I have?": "get_recurring_expenses",
    "Create an Emergency Fund goal for €3,000.": "create_savings_goal",
    "How has my spending changed over the last six months?": "get_spending_history",
    "Where did most of my money go this month?": "get_spending_breakdown",
}


async def test_the_page_shows_real_prompts_fictional_figures_and_no_overclaims(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    words = visible_text(html)
    assert {text for _, _, text in pages.PROMPTS} == set(PROMPT_TOOLS)
    for prompt, tool in PROMPT_TOOLS.items():
        assert prompt in words
        assert tool in PUBLISHED_TOOLS
    assert "All figures are fictional" in words
    assert "It does not store your ChatGPT conversations" in words
    for claim in (
        r"bank[- ]grade",
        r"military[- ]grade",
        r"zero[- ]knowledge",
        r"end[- ]to[- ]end",
        r"\bencrypt",
        r"\bread[- ]only\b",
        r"\b(free|premium|trial|pricing)\b",
    ):
        assert not re.search(claim, words, re.I), claim


async def test_motion_respects_reduced_motion_and_focus_is_visible(mcp):
    async with mcp.http() as http:
        html = (await http.get(await _login_url(http))).text
    assert "@media (prefers-reduced-motion:reduce)" in html
    assert "@media (prefers-reduced-motion:no-preference)" in html
    assert re.search(r":focus-visible[^{]*\{outline:3px solid", html)
    assert html.count("@font-face") == 4 and "font-display:swap" in html
