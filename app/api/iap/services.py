"""Very naive receipt validation helpers."""

from typing import Dict


def validate_receipt(
    user_id: str,
    receipt: str,
    platform: str,
) -> Dict[str, str]:
    """Validate receipt contents.

    This stub just checks that the platform is supported and the receipt is
    not empty. Real integration with App Store or Google Play should be
    implemented separately.
    """

    if platform not in {"ios", "android"}:
        return {"status": "invalid", "reason": "unsupported platform"}
    if not receipt:
        return {"status": "invalid", "reason": "empty receipt"}
    return {"status": "valid", "platform": platform}
