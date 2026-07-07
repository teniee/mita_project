"""Regression tests for the standardized response wrapper.

GET /api/calendar/day/{y}/{m}/{d} (and any route returning DB-derived
values) 500'd with "Object of type Decimal is not JSON serializable"
because JSONResponse uses stdlib json. The wrapper must encode
Decimal/date/datetime/UUID payloads before serialization.
"""

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.utils.response_wrapper import StandardizedResponse, success_response


def _body(response) -> dict:
    return json.loads(response.body)


def test_success_response_serializes_decimal():
    resp = success_response({"planned_amount": Decimal("42.50")})
    assert resp.status_code == 200
    assert _body(resp)["data"]["planned_amount"] == 42.5


def test_success_response_serializes_date_datetime_uuid():
    uid = uuid4()
    resp = success_response(
        {
            "day": date(2026, 7, 5),
            "created_at": datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
            "id": uid,
        }
    )
    data = _body(resp)["data"]
    assert data["day"] == "2026-07-05"
    assert data["created_at"].startswith("2026-07-05T12:00:00")
    assert data["id"] == str(uid)


def test_success_response_serializes_nested_decimals():
    resp = success_response(
        {
            "days": [
                {"total": Decimal("100.10"), "categories": {"food": Decimal("25.25")}}
            ]
        }
    )
    data = _body(resp)["data"]
    assert data["days"][0]["total"] == 100.1
    assert data["days"][0]["categories"]["food"] == 25.25


def test_success_meta_serializes_decimal():
    resp = StandardizedResponse.success(
        data={"ok": True}, meta={"balance_impact": Decimal("9.99")}
    )
    assert _body(resp)["meta"]["balance_impact"] == 9.99


def test_created_response_serializes_decimal():
    resp = StandardizedResponse.created(data={"amount": Decimal("15.75")})
    assert resp.status_code == 201
    assert _body(resp)["data"]["amount"] == 15.75
