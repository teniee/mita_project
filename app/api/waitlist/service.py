"""
Waitlist Service — Level 2 waitlist with referral position boost.

Mechanics:
- Each new signup gets the next sequential position.
- Every successful referral gives the referrer a REFERRAL_BOOST to their effective position.
- Effective position = max(1, raw_position - position_boost)
- A confirmation email is sent on signup.
- Referred user gets a "you jumped the queue" email if they were referred.
"""

import hashlib
import logging
import os
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.waitlist import WaitlistEntry

logger = logging.getLogger(__name__)

REFERRAL_BOOST = 10          # spots moved up per referral
BASE_URL = os.getenv("FRONTEND_URL", "https://mitafinance.app")


def _gen_ref_code(email: str) -> str:
    """Deterministic 8-char alphanumeric code derived from email + random salt."""
    salt = secrets.token_hex(4)
    digest = hashlib.sha256(f"{email}{salt}".encode()).hexdigest()
    alphabet = string.ascii_uppercase + string.digits
    return "".join(alphabet[int(digest[i:i+2], 16) % len(alphabet)] for i in range(0, 16, 2))


def _gen_confirm_token() -> str:
    return secrets.token_urlsafe(48)


async def _get_total(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(WaitlistEntry))
    return result.scalar() or 0


async def join_waitlist(email: str, referred_by_code: Optional[str], db: AsyncSession) -> WaitlistEntry:
    # Check duplicate
    existing = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already on the waitlist."
        )

    # Validate referral code
    referrer: Optional[WaitlistEntry] = None
    if referred_by_code:
        res = await db.execute(
            select(WaitlistEntry).where(WaitlistEntry.ref_code == referred_by_code.upper())
        )
        referrer = res.scalar_one_or_none()
        # silently ignore invalid codes — don't block signup

    total = await _get_total(db)
    position = total + 1

    entry = WaitlistEntry(
        email=email,
        position=position,
        ref_code=_gen_ref_code(email),
        referred_by_code=referrer.ref_code if referrer else None,
        referral_count=0,
        position_boost=0,
        confirmed=False,
        confirm_token=_gen_confirm_token(),
    )
    db.add(entry)

    # Boost referrer
    if referrer:
        referrer.referral_count += 1
        referrer.position_boost += REFERRAL_BOOST
        referrer.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(entry)
    return entry


async def get_by_ref_code(ref_code: str, db: AsyncSession) -> WaitlistEntry:
    res = await db.execute(
        select(WaitlistEntry).where(WaitlistEntry.ref_code == ref_code.upper())
    )
    entry = res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found.")
    return entry


async def confirm_email(token: str, db: AsyncSession) -> WaitlistEntry:
    res = await db.execute(
        select(WaitlistEntry).where(WaitlistEntry.confirm_token == token)
    )
    entry = res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Invalid or expired confirmation token.")
    if entry.confirmed:
        return entry
    entry.confirmed = True
    entry.confirm_token = None
    entry.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(entry)
    return entry


def build_referral_link(ref_code: str) -> str:
    return f"{BASE_URL}/?ref={ref_code}"


def effective_position(entry: WaitlistEntry) -> int:
    return max(1, entry.position - entry.position_boost)
