"""Receipt validation helpers for App Store and Google Play."""

from datetime import datetime
from typing import Any, Dict
import json
import os
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build


def validate_receipt(
    user_id: str,
    receipt: str,
    platform: str,
) -> Dict[str, Any]:
    """Validate a purchase receipt and return subscription info."""

    if platform not in {"ios", "android"}:
        return {"status": "invalid", "reason": "unsupported platform"}
    if not receipt:
        return {"status": "invalid", "reason": "empty receipt"}

    if platform == "ios":
        secret = os.getenv("APPLE_SHARED_SECRET")
        if not secret:
            return {"status": "invalid", "reason": "missing secret"}
        try:
            resp = requests.post(
                "https://buy.itunes.apple.com/verifyReceipt",
                json={"receipt-data": receipt, "password": secret},
                timeout=10,
            )
            data = resp.json()
        except Exception as exc:  # pragma: no cover - network failure
            return {"status": "invalid", "reason": str(exc)}
        if resp.status_code != 200 or data.get("status") != 0:
            return {"status": "invalid", "reason": "apple verification failed"}
        latest = data.get("latest_receipt_info", [{}])[-1]
        expires_at = datetime.utcfromtimestamp(
            int(latest.get("expires_date_ms", 0)) / 1000
        )
        starts_at = datetime.utcfromtimestamp(
            int(latest.get("purchase_date_ms", 0)) / 1000
        )
        prod = latest.get("product_id", "").lower()
        plan = "annual" if any(x in prod for x in ["1y", "annual", "year"]) else "monthly"
        return {
            "status": "valid",
            "platform": "ios",
            "plan": plan,
            "starts_at": starts_at,
            "expires_at": expires_at,
        }

    if platform == "android":
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if not creds_path:
            return {"status": "invalid", "reason": "missing credentials"}
        try:
            credentials = service_account.Credentials.from_service_account_file(
                creds_path
            )
            service = build(
                "androidpublisher", "v3", credentials=credentials, cache_discovery=False
            )
            payload = json.loads(receipt)
            result = (
                service.purchases()
                .subscriptions()
                .get(
                    packageName=payload["packageName"],
                    subscriptionId=payload["subscriptionId"],
                    token=payload["purchaseToken"],
                )
                .execute()
            )
        except Exception as exc:  # pragma: no cover - network failure
            return {"status": "invalid", "reason": str(exc)}

        expires_at = datetime.utcfromtimestamp(
            int(result.get("expiryTimeMillis", 0)) / 1000
        )
        starts_at = datetime.utcfromtimestamp(
            int(result.get("startTimeMillis", result.get("expiryTimeMillis", 0)))
            / 1000
        )
        plan = "annual" if "P1Y" in result.get("subscriptionPeriod", "") else "monthly"
        return {
            "status": "valid",
            "platform": "android",
            "plan": plan,
            "starts_at": starts_at,
            "expires_at": expires_at,
        }

    # Should never reach here
    return {"status": "invalid", "reason": "unhandled"}
