"""Server-side In-App Purchase verification (Apple App Store, Google Play).

Design rules:
- Subscription state comes only from cryptographically verified store
  notifications or authenticated store API calls — never from the client.
- Missing credentials/configuration fail CLOSED: no premium is granted.
- Every processed notification is recorded for idempotency/replay defense.
"""

from app.services.iap.errors import (  # noqa: F401
    IAPNotConfiguredError,
    IAPVerificationError,
)
