"""Receipt validation helpers for App Store and Google Play.

Returned dictionaries carry the store-side purchase identity
(`original_transaction_id`: Apple originalTransactionId or Google
purchaseToken), the store `product_id` and the `environment`
("production"/"sandbox") so callers can enforce ownership, product
allowlists and sandbox separation.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi.concurrency import run_in_threadpool
from google.oauth2 import service_account
from googleapiclient.discovery import build

APPLE_PRODUCTION_VERIFY_URL = "https://buy.itunes.apple.com/verifyReceipt"
APPLE_SANDBOX_VERIFY_URL = "https://sandbox.itunes.apple.com/verifyReceipt"
# Apple: "used a sandbox receipt against the production environment".
APPLE_STATUS_SANDBOX_RECEIPT = 21007


def _from_ms(value) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


async def validate_receipt(
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
        secret = os.getenv("APPLE_SHARED_SECRET") or os.getenv("APPSTORE_SHARED_SECRET")
        if not secret:
            return {"status": "invalid", "reason": "missing secret"}
        environment = "production"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    APPLE_PRODUCTION_VERIFY_URL,
                    json={"receipt-data": receipt, "password": secret},
                    timeout=10,
                )
                data = resp.json()
                if (
                    resp.status_code == 200
                    and data.get("status") == APPLE_STATUS_SANDBOX_RECEIPT
                ):
                    environment = "sandbox"
                    resp = await client.post(
                        APPLE_SANDBOX_VERIFY_URL,
                        json={"receipt-data": receipt, "password": secret},
                        timeout=10,
                    )
                    data = resp.json()
        except Exception:  # pragma: no cover - network failure
            return {"status": "invalid", "reason": "store request failed"}
        if resp.status_code != 200 or data.get("status") != 0:
            return {"status": "invalid", "reason": "apple verification failed"}
        latest = data.get("latest_receipt_info", [{}])[-1]
        expires_at = _from_ms(latest.get("expires_date_ms", 0))
        starts_at = _from_ms(latest.get("purchase_date_ms", 0))
        product_id = latest.get("product_id", "")
        prod = product_id.lower()
        plan = (
            "annual" if any(x in prod for x in ["1y", "annual", "year"]) else "monthly"
        )
        return {
            "status": "valid",
            "platform": "ios",
            "plan": plan,
            "starts_at": starts_at,
            "expires_at": expires_at,
            "product_id": product_id,
            "original_transaction_id": latest.get("original_transaction_id"),
            "environment": environment,
        }

    if platform == "android":
        creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if not creds_path:
            return {"status": "invalid", "reason": "missing credentials"}
        try:
            payload = json.loads(receipt)
            purchase_token = payload["purchaseToken"]
            subscription_id = payload["subscriptionId"]
            package_name = payload["packageName"]
        except (ValueError, KeyError, TypeError):
            return {"status": "invalid", "reason": "malformed android receipt"}

        expected_package = os.getenv("GOOGLE_PACKAGE_NAME")
        if expected_package and package_name != expected_package:
            return {"status": "invalid", "reason": "package name mismatch"}

        try:

            def _fetch():
                credentials = service_account.Credentials.from_service_account_file(
                    creds_path
                )
                service = build(
                    "androidpublisher",
                    "v3",
                    credentials=credentials,
                    cache_discovery=False,
                )
                return (
                    service.purchases()
                    .subscriptions()
                    .get(
                        packageName=package_name,
                        subscriptionId=subscription_id,
                        token=purchase_token,
                    )
                    .execute()
                )

            result = await run_in_threadpool(_fetch)
        except Exception:  # pragma: no cover - network failure
            return {"status": "invalid", "reason": "store request failed"}

        expires_at = _from_ms(result.get("expiryTimeMillis", 0))
        starts_at = _from_ms(
            result.get("startTimeMillis", result.get("expiryTimeMillis", 0))
        )
        plan = "annual" if "P1Y" in result.get("subscriptionPeriod", "") else "monthly"
        # purchaseType 0 marks test (license-tester) purchases.
        environment = "sandbox" if result.get("purchaseType") == 0 else "production"
        return {
            "status": "valid",
            "platform": "android",
            "plan": plan,
            "starts_at": starts_at,
            "expires_at": expires_at,
            "product_id": subscription_id,
            "original_transaction_id": purchase_token,
            "environment": environment,
        }

    # Should never reach here
    return {"status": "invalid", "reason": "unhandled"}
