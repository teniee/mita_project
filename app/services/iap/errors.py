class IAPVerificationError(Exception):
    """Raised when a store notification fails cryptographic or claim checks."""


class IAPNotConfiguredError(Exception):
    """Raised when verification cannot run because credentials/config are
    missing. Callers must fail closed (no entitlement change, 503)."""
