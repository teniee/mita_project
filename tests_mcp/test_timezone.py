"""Days and months are the user's local ones (Europe/Sofia vs UTC).

Europe/Sofia is UTC+2 until 2026-03-29 03:00 local, then UTC+3.
"""

from datetime import date, datetime, timezone

from tests_mcp.conftest import structured


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


async def test_month_boundary_belongs_to_the_local_month(mcp, seed):
    # 2026-03-31 22:30Z is 2026-04-01 01:30 in Sofia (UTC+3 after the DST switch).
    sofia = await seed.user(tz="Europe/Sofia")
    london = await seed.user(tz="UTC")
    for user in (sofia, london):
        await seed.txn(user, "42.00", "food", utc(2026, 3, 31, 22, 30))
    m = mcp.at(utc(2026, 4, 2, 12))
    s_march = structured(
        await m.call(
            m.token(sofia), "get_financial_summary", {"year": 2026, "month": 3}
        )
    )
    s_april = structured(
        await m.call(
            m.token(sofia), "get_financial_summary", {"year": 2026, "month": 4}
        )
    )
    u_march = structured(
        await m.call(
            m.token(london), "get_financial_summary", {"year": 2026, "month": 3}
        )
    )
    assert (s_march["spent_total"], s_april["spent_total"]) == ("0.00", "42.00")
    assert u_march["spent_total"] == "42.00"
    listed = structured(
        await m.call(
            m.token(sofia),
            "list_transactions",
            {"start_date": "2026-04-01", "end_date": "2026-04-01"},
        )
    )
    assert [t["date"] for t in listed["transactions"]] == ["2026-04-01"]


async def test_today_crosses_midnight_in_local_time(mcp, seed):
    # 23:30Z on Mar 14 is already Mar 15, 01:30 in Sofia (UTC+2).
    sofia = await seed.user(tz="Europe/Sofia")
    await seed.plan(sofia, date(2026, 3, 14), {"food": "11.00"})
    await seed.plan(sofia, date(2026, 3, 15), {"food": "22.00"})
    await seed.txn(
        sofia, "5.00", "food", utc(2026, 3, 14, 23, 0)
    )  # Sofia: Mar 15 01:00
    await seed.txn(
        sofia, "3.00", "food", utc(2026, 3, 14, 21, 0)
    )  # Sofia: Mar 14 23:00
    m = mcp.at(utc(2026, 3, 14, 23, 30))
    data = structured(await m.call(m.token(sofia), "get_budget_status"))
    assert data["today"] == {
        "date": "2026-03-15",
        "planned": "22.00",
        "spent": "5.00",
        "remaining": "17.00",
    }


async def test_same_instant_is_a_different_day_for_a_utc_user(mcp, seed):
    london = await seed.user(tz="UTC")
    await seed.plan(london, date(2026, 3, 14), {"food": "11.00"})
    await seed.txn(london, "5.00", "food", utc(2026, 3, 14, 23, 0))
    m = mcp.at(utc(2026, 3, 14, 23, 30))
    data = structured(await m.call(m.token(london), "get_budget_status"))
    assert data["today"] == {
        "date": "2026-03-14",
        "planned": "11.00",
        "spent": "5.00",
        "remaining": "6.00",
    }


async def test_default_date_range_ends_on_local_today(mcp, seed):
    sofia = await seed.user(tz="Europe/Sofia")
    m = mcp.at(utc(2026, 3, 14, 23, 30))
    data = structured(await m.call(m.token(sofia), "list_transactions"))
    assert (data["start_date"], data["end_date"]) == ("2026-02-14", "2026-03-15")


async def test_forecast_uses_local_today(mcp, seed):
    sofia = await seed.user(tz="Europe/Sofia")
    await seed.plan(sofia, date(2026, 3, 1), {"food": "310.00"})
    m = mcp.at(utc(2026, 3, 31, 22, 30))  # Sofia: 2026-04-01 01:30
    march = structured(
        await m.call(m.token(sofia), "get_budget_forecast", {"year": 2026, "month": 3})
    )
    assert march["month_position"] == "past"
    assert (march["days_elapsed"], march["days_remaining"]) == (31, 0)
    april = structured(await m.call(m.token(sofia), "get_budget_forecast"))
    assert (april["year"], april["month"]) == (2026, 4)


async def test_invalid_timezone_falls_back_to_utc_like_the_ledger(mcp, seed):
    user = await seed.user(tz="Mars/Olympus_Mons")
    await seed.txn(user, "9.00", "food", utc(2026, 3, 14, 23, 0))
    m = mcp.at(utc(2026, 3, 14, 23, 30))
    data = structured(await m.call(m.token(user), "list_transactions"))
    assert data["end_date"] == "2026-03-14"
    assert [t["date"] for t in data["transactions"]] == ["2026-03-14"]
