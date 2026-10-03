"""Email/password verification with account lockout for the ChatGPT consent page.

Used by the ChatGPT OAuth consent page (``app/mcp/auth/login.py``). It
mirrors the mobile login's rules in ``app/api/auth/login.py`` exactly and
updates the SAME columns, so both paths share one lockout counter: five
consecutive failures lock the account for 30 minutes, a success resets it
(migration 0017_add_account_security_fields). The mobile route is left
untouched on purpose (ADR §7); keep the two in step if either changes.

Callers own security-event logging (they hold the request context) and the
user-facing message, which must not distinguish "no such user" from "wrong
password".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.password_security import verify_password_async
from app.db.models import User

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=30)


class CredentialOutcome(str, Enum):
    OK = "ok"
    UNKNOWN_USER = "unknown_user"
    LOCKED = "locked"
    INVALID_PASSWORD = "invalid_password"
    INACTIVE = "inactive"


@dataclass
class CredentialCheck:
    outcome: CredentialOutcome
    user: Optional[User] = None
    just_locked: bool = False

    @property
    def ok(self) -> bool:
        return self.outcome is CredentialOutcome.OK


async def verify_login_credentials(
    db: AsyncSession,
    email: str,
    password: str,
    *,
    now: Optional[datetime] = None,
) -> CredentialCheck:
    """Check credentials and update the lockout counters.

    ``email`` must already be validated/normalized by the caller. Commits the
    session when it changes the counters, exactly as the login route did.
    """
    now = now or datetime.now(timezone.utc)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return CredentialCheck(CredentialOutcome.UNKNOWN_USER)

    if user.account_locked_until and user.account_locked_until > now:
        return CredentialCheck(CredentialOutcome.LOCKED, user)

    if not await verify_password_async(password, user.password_hash):
        user.failed_login_attempts += 1
        just_locked = False
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.account_locked_until = now + LOCKOUT_DURATION
            just_locked = True
        await db.commit()
        return CredentialCheck(CredentialOutcome.INVALID_PASSWORD, user, just_locked)

    if hasattr(user, "is_active") and not user.is_active:
        return CredentialCheck(CredentialOutcome.INACTIVE, user)

    if user.failed_login_attempts > 0:
        user.failed_login_attempts = 0
        user.account_locked_until = None
        await db.commit()

    return CredentialCheck(CredentialOutcome.OK, user)
