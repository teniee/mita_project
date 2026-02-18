"""
Authentication routes main aggregator.

This module aggregates all authentication-related sub-routers into a single main router
with the /auth prefix. All sub-routers are mounted without their own prefix since the
main router already has /auth.

Architecture:
- routes.py (this file): Main aggregator with /auth prefix
- registration.py: User registration endpoints
- login.py: User login endpoints
- token_management.py: Token refresh and logout
- password_reset.py: Password reset flow
- google_auth.py: Google OAuth integration
- admin_endpoints.py: Admin token management
- account_management.py: Password change, account deletion
- security_monitoring.py: Security status and token validation
- test_endpoints.py: Test and emergency endpoints
- utils.py: Shared utility functions
"""

from fastapi import APIRouter

# Import all sub-routers
from app.api.auth import (
    account_management,
    admin_endpoints,
    google_auth,
    login,
    password_reset,
    registration,
    security_monitoring,
    token_management,
)

# Main router with /auth prefix
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Include all sub-routers (they don't have /auth prefix)
router.include_router(registration.router)
router.include_router(login.router)
router.include_router(token_management.router)
router.include_router(password_reset.router)
router.include_router(google_auth.router)
router.include_router(admin_endpoints.router)
router.include_router(account_management.router)
router.include_router(security_monitoring.router)
# test_endpoints.router intentionally NOT included — bypass registration
# endpoints (/emergency-register, /register-fast) must not be reachable in production.
