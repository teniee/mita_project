"""Creating a MITA account from the ChatGPT OAuth flow (``/oauth/login?mode=register``).

The real sign-up page, the real OAuth endpoints and the real database: a new
person registers, the pending authorization continues to their new account,
and the token works for tools — and nothing about anyone else leaks.
"""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import text

from app.core.password_security import verify_password_sync
from app.mcp.auth.login import REGISTRATION_FAILED
from app.mcp.auth.scopes import SUPPORTED_SCOPES
from tests_mcp.conftest import PASSWORD, Harness, make_settings, structured
from tests_mcp.test_oauth_flow import (
    REDIRECT,
    authorize,
    csrf_from,
    exchange,
    pkce,
    register,
)

NEW_PASSWORD = "Fresh-Start-2026!"
ALL_SCOPES = " ".join(SUPPORTED_SCOPES)


async def _login_url(http, *, state="st-reg"):
    client_id = (await register(http)).json()["client_id"]
    verifier, challenge = pkce()
    redirect = await authorize(
        http, client_id, challenge, state=state, scope=ALL_SCOPES
    )
    assert redirect.status_code == 302, redirect.text
    return client_id, verifier, redirect.headers["location"]


async def _sign_up(
    http, login_url, email, password=NEW_PASSWORD, *, confirm=None, usage="1"
):
    page = await http.get(login_url + "&mode=register")
    assert page.status_code == 200, page.text
    req = parse_qs(urlparse(login_url).query)["req"][0]
    data = {
        "req": req,
        "csrf": csrf_from(page.text),
        "email": email,
        "password": password,
        "password_confirm": password if confirm is None else confirm,
        "action": "register",
    }
    if usage:
        data["usage_stats"] = usage
    return page, await http.post("/oauth/login", data=data)


async def _user_row(connection, email):
    return (
        await connection.execute(
            text(
                "SELECT id, email, password_hash, country, currency, timezone, "
                "has_onboarded, monthly_income FROM users WHERE email = :e"
            ),
            {"e": email},
        )
    ).first()


async def test_sign_up_page_offers_both_paths(mcp):
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        sign_in = await http.get(login_url)
        sign_up = await http.get(login_url + "&mode=register")
    assert "Create an account" in sign_in.text and "Sign in and connect" in sign_in.text
    assert "Already have a MITA account?" in sign_up.text
    assert 'name="password_confirm"' in sign_up.text
    assert 'value="register"' in sign_up.text
    # The page says what MITA can never do, and asks about usage statistics.
    for page in (sign_in, sign_up):
        assert "cannot move money, make payments or connect to your bank" in page.text
        assert 'name="usage_stats"' in page.text
        assert "never records my conversations, amounts or merchant names" in page.text


async def test_new_user_registers_and_continues_the_same_authorization(
    mcp, connection, analytics_sink
):
    email = "New.Person+Mita@Example.test"
    async with mcp.http() as http:
        client_id, verifier, login_url = await _login_url(http, state="pending-42")
        _, done = await _sign_up(http, login_url, email)
        assert done.status_code == 302, done.text
        location = urlparse(done.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
        query = parse_qs(location.query)
        assert query["state"] == ["pending-42"]  # the exact pending request
        token = (await exchange(http, client_id, query["code"][0], verifier)).json()

    assert sorted(token["scope"].split()) == sorted(SUPPORTED_SCOPES)
    row = await _user_row(connection, "new.person+mita@example.test")
    assert row is not None, "e-mail is stored normalized (lower-case)"
    assert row.country == "ZZ"  # not stated — never invented
    assert row.currency == "USD" and row.timezone == "UTC"  # API defaults, unconfirmed
    assert row.has_onboarded is False and row.monthly_income == 0
    assert row.password_hash != NEW_PASSWORD
    assert verify_password_sync(NEW_PASSWORD, row.password_hash)

    status = structured(await mcp.call(token["access_token"], "get_setup_status"))
    assert status["profile_complete"] is False
    assert status["missing_fields"] == [
        "monthly_net_income",
        "currency",
        "timezone",
        "household_size",
        "monthly_savings_target",
    ]
    assert status["known"] == {
        "monthly_net_income": None,
        "currency": None,
        "timezone": None,
        "household_size": None,
        "monthly_savings_target": None,
    }
    assert status["transaction_count"] == 0 and status["monthly_plan_exists"] is False
    assert status["suggested_next_step"] == "complete_profile"

    profile = (
        await connection.execute(
            text(
                "SELECT usage_analytics_enabled FROM mcp_user_profiles WHERE user_id = :u"
            ),
            {"u": row.id},
        )
    ).scalar_one()
    assert profile is True
    names = analytics_sink.names()
    assert "account_created" in names and "oauth_connected" in names
    created = next(
        e for e in analytics_sink.events if e.event_name == "account_created"
    )
    assert created.user_key and created.user_key != str(row.id)


async def test_unchecked_usage_statistics_links_nothing(
    mcp, connection, analytics_sink
):
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        _, done = await _sign_up(http, login_url, "private@example.test", usage=None)
        assert done.status_code == 302
    row = await _user_row(connection, "private@example.test")
    enabled = (
        await connection.execute(
            text(
                "SELECT usage_analytics_enabled FROM mcp_user_profiles WHERE user_id = :u"
            ),
            {"u": row.id},
        )
    ).scalar_one()
    assert enabled is False
    for event in analytics_sink.events:
        assert event.user_key is None and event.session_key is None


# --- the usage-statistics box (owner decision 2026-10-25: unticked by default) ----


async def _sign_in(http, login_url, email, password, *, usage=None):
    page = await http.get(login_url)
    req = parse_qs(urlparse(login_url).query)["req"][0]
    data = {
        "req": req,
        "csrf": csrf_from(page.text),
        "email": email,
        "password": password,
        "action": "allow",
    }
    if usage:
        data["usage_stats"] = usage
    return await http.post("/oauth/login", data=data)


async def _usage_row(connection, user_id):
    return (
        await connection.execute(
            text(
                "SELECT usage_analytics_enabled, usage_analytics_updated_at "
                "FROM mcp_user_profiles WHERE user_id = :u"
            ),
            {"u": user_id},
        )
    ).first()


def _connected(analytics_sink):
    return next(e for e in analytics_sink.events if e.event_name == "oauth_connected")


async def test_the_box_starts_unticked_on_both_tabs(mcp):
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        sign_in = await http.get(login_url)
        sign_up = await http.get(login_url + "&mode=register")
    box = '<input type="checkbox" name="usage_stats" value="1">'
    assert box in sign_in.text and box in sign_up.text
    assert "checked" not in sign_in.text and "checked" not in sign_up.text
    keep = "Leaving it unticked keeps any choice I made before."
    assert keep in sign_in.text and keep not in sign_up.text


async def test_a_failed_attempt_keeps_the_box_as_the_person_left_it(mcp, seed):
    user = await seed.user()
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        ticked = await _sign_in(http, login_url, user.email, "wrong", usage="1")
        _, _, login_url = await _login_url(http)
        unticked = await _sign_in(http, login_url, user.email, "wrong")
    assert ticked.status_code == unticked.status_code == 400
    assert 'name="usage_stats" value="1" checked>' in ticked.text
    assert 'name="usage_stats" value="1">' in unticked.text


async def test_ticking_the_box_on_sign_in_opts_an_existing_account_in(
    mcp, seed, connection, analytics_sink
):
    user = await seed.user()
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        done = await _sign_in(http, login_url, user.email, PASSWORD, usage="1")
    assert done.status_code == 302
    assert (await _usage_row(connection, user.id))[0] is True
    assert _connected(analytics_sink).user_key is not None


async def test_an_unticked_box_on_sign_in_keeps_an_earlier_yes(
    mcp, seed, connection, analytics_sink
):
    """Not a withdrawal: the account stays opted in and nothing is deleted
    (withdrawing is set_usage_analytics(false), which deletes the linked
    statistics)."""
    user = await seed.user()
    when = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
    await seed.profile(
        user, usage_analytics_enabled=True, usage_analytics_updated_at=when
    )
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        done = await _sign_in(http, login_url, user.email, PASSWORD)
    assert done.status_code == 302
    assert tuple(await _usage_row(connection, user.id)) == (True, when)
    assert _connected(analytics_sink).user_key is not None


async def test_an_unticked_box_on_sign_in_keeps_an_earlier_no(
    mcp, seed, connection, analytics_sink
):
    user = await seed.user()
    await seed.profile(user, usage_analytics_enabled=False)
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        done = await _sign_in(http, login_url, user.email, PASSWORD)
    assert done.status_code == 302
    assert (await _usage_row(connection, user.id))[0] is False
    connected = _connected(analytics_sink)
    assert connected.user_key is None and connected.session_key is None


async def test_an_unticked_box_on_sign_in_records_no_choice(
    mcp, seed, connection, analytics_sink
):
    """An account that never answered (e.g. made in the mobile app) is not
    given an answer by the default state of a box."""
    user = await seed.user()
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        done = await _sign_in(http, login_url, user.email, PASSWORD)
    assert done.status_code == 302
    assert await _usage_row(connection, user.id) is None
    assert _connected(analytics_sink).user_key is None


async def test_taken_address_is_refused_generically_and_changes_nothing(
    mcp, seed, connection
):
    existing = await seed.user()
    before = (await _user_row(connection, existing.email)).password_hash
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        _, refused = await _sign_up(http, login_url, existing.email.upper())
    assert refused.status_code == 400
    assert REGISTRATION_FAILED in refused.text
    count = (
        await connection.execute(
            text("SELECT count(*) FROM users WHERE lower(email) = :e"),
            {"e": existing.email.lower()},
        )
    ).scalar_one()
    assert count == 1
    assert (await _user_row(connection, existing.email)).password_hash == before


async def test_taken_and_new_addresses_both_pay_for_a_hash(mcp, seed, monkeypatch):
    """No timing split: the password is hashed before the address is looked up."""
    import app.mcp.auth.login as login_module

    calls = []
    real = login_module.hash_password_async

    async def spy(password):
        calls.append(1)
        return await real(password)

    monkeypatch.setattr(login_module, "hash_password_async", spy)
    existing = await seed.user()
    async with mcp.http() as http:
        _, _, url_a = await _login_url(http)
        await _sign_up(http, url_a, existing.email)
        _, _, url_b = await _login_url(http)
        await _sign_up(http, url_b, "brand-new@example.test")
    assert len(calls) == 2


@pytest.mark.parametrize(
    "email,password,confirm,message",
    [
        ("not-an-email", NEW_PASSWORD, None, "Enter a valid email address."),
        ("short@example.test", "Ab1!", None, "at least 8 characters"),
        ("nosymbol@example.test", "Abcdefgh123", None, "special characters"),
        ("mismatch@example.test", NEW_PASSWORD, "Other-Pass-2026!", "do not match"),
    ],
)
async def test_invalid_sign_up_forms_are_explained_and_create_nothing(
    mcp, connection, email, password, confirm, message
):
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        _, response = await _sign_up(http, login_url, email, password, confirm=confirm)
    assert response.status_code == 400
    assert message in response.text
    assert await _user_row(connection, email.lower()) is None
    assert password not in response.text  # never echoed back


async def test_sign_up_without_csrf_is_refused(mcp, connection):
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        page = await http.get(login_url + "&mode=register")
        req = parse_qs(urlparse(login_url).query)["req"][0]
        http.cookies.clear()
        response = await http.post(
            "/oauth/login",
            data={
                "req": req,
                "csrf": csrf_from(page.text),
                "email": "csrf@example.test",
                "password": NEW_PASSWORD,
                "password_confirm": NEW_PASSWORD,
                "action": "register",
            },
        )
    assert response.status_code == 400
    assert await _user_row(connection, "csrf@example.test") is None


async def test_sign_up_is_rate_limited_per_network(make_service, connection):
    harness = Harness(make_service, make_settings(registrations_per_hour=2))
    async with harness.http() as http:
        statuses = []
        for i in range(3):
            _, _, login_url = await _login_url(http)
            _, response = await _sign_up(http, login_url, f"burst{i}@example.test")
            statuses.append(response.status_code)
    assert statuses == [302, 302, 429]
    assert await _user_row(connection, "burst2@example.test") is None


async def test_sign_up_logs_no_email_or_password(mcp, caplog):
    caplog.set_level("INFO")
    async with mcp.http() as http:
        _, _, login_url = await _login_url(http)
        await _sign_up(http, login_url, "quiet.person@example.test")
    logged = "\n".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
    assert "quiet.person" not in logged
    assert NEW_PASSWORD not in logged


async def test_new_account_cannot_see_anyone_else(mcp, seed):
    other = await seed.user(name="Somebody Else")
    await seed.txn(other, "123.45", "groceries", seed_now())
    async with mcp.http() as http:
        client_id, verifier, login_url = await _login_url(http)
        _, done = await _sign_up(http, login_url, "isolated@example.test")
        code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
        token = (await exchange(http, client_id, code, verifier)).json()["access_token"]
    for tool in ("get_financial_summary", "list_transactions", "get_profile"):
        text_out = (await mcp.call(token, tool)).content[0].text
        assert "123.45" not in text_out and "Somebody Else" not in text_out, tool


def seed_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


async def test_registered_user_reconnects_with_sign_in_and_keeps_their_data(mcp):
    from tests_mcp.test_oauth_flow import consent

    email = "returning@example.test"
    async with mcp.http() as http:
        client_id, verifier, login_url = await _login_url(http)
        _, done = await _sign_up(http, login_url, email)
        code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
        first = (await exchange(http, client_id, code, verifier)).json()["access_token"]
    await mcp.call(first, "update_financial_profile", {"household_size": 4})

    # Later: a new connection (e.g. after the ChatGPT conversation was deleted).
    async with mcp.http() as http:
        client_id, verifier, login_url = await _login_url(http)
        _, done = await consent(http, login_url, email, NEW_PASSWORD)
        assert done.status_code == 302, done.text
        code = parse_qs(urlparse(done.headers["location"]).query)["code"][0]
        second = (await exchange(http, client_id, code, verifier)).json()[
            "access_token"
        ]
    status = structured(await mcp.call(second, "get_setup_status"))
    assert status["known"]["household_size"] == 4
