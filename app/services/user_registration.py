"""The one way a password account row is built.

Used by the mobile registration route (``app/api/auth/registration.py``) and
the ChatGPT sign-up page (``app/mcp/auth/login.py``), so an account created in
ChatGPT is the same kind of row, with the same defaults, as one created in
the app — one user system, not two. Hashing and policy checks happen before
this is called; this only fixes the column values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.db.models import User

# ISO 3166 user-assigned code for "not stated". Accounts created in ChatGPT
# are never asked for a location; ``users.country`` is NOT NULL in the API's
# profile schema, and writing "US" would state something nobody said. Every
# country-dependent path falls back to the DEFAULT profile for unknown codes.
COUNTRY_NOT_STATED = "ZZ"


def build_password_user(
    *,
    email: str,
    password_hash: str,
    country: str,
    timezone_name: Optional[str] = None,
    name: Optional[str] = None,
    annual_income: Optional[Decimal] = None,
) -> User:
    now = datetime.now(timezone.utc)
    return User(
        email=email,
        password_hash=password_hash,
        country=country,
        annual_income=annual_income or 0,
        timezone=timezone_name or "UTC",
        created_at=now,
        updated_at=now,
        is_premium=False,
        email_verified=False,
        has_onboarded=False,
        notifications_enabled=True,
        dark_mode_enabled=False,
        token_version=1,
        name=name or "",
        monthly_income=0,
        savings_goal=0,
        budget_method="50/30/20 Rule",
        currency="USD",
    )
