from datetime import datetime

from app.api.iap.services import validate_receipt


def test_validate_receipt_expiration():
    result = validate_receipt("u1", "sample-year-receipt", "ios")
    assert result["status"] == "valid"
    assert result["platform"] == "ios"
    assert isinstance(result["expires_at"], datetime)
    assert result["plan"] == "annual"
    assert isinstance(result["starts_at"], datetime)
