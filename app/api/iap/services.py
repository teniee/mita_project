"""Very naive receipt validation helpers with simulated expiration."""

from datetime import datetime, timedelta
from typing import Any, Dict


def validate_receipt(
    user_id: str,
    receipt: str,
    platform: str,
) -> Dict[str, Any]:
    """Validate receipt contents.

    This stub now returns an expiration timestamp. Real integration with
    App Store or Google Play should be implemented separately.
    """

    if platform not in {"ios", "android"}:
        return {"status": "invalid", "reason": "unsupported platform"}
    if not receipt:
        return {"status": "invalid", "reason": "empty receipt"}

    days = 365 if "year" in receipt else 30
    expiration = datetime.utcnow() + timedelta(days=days)
    return {
        "status": "valid",
        "platform": platform,
        "plan": "annual" if days > 30 else "monthly",
        "starts_at": datetime.utcnow(),
        "expires_at": expiration,
    }
