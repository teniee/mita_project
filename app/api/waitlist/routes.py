"""
Waitlist API — public endpoints, no auth required.

POST /waitlist/join          — join the waitlist
GET  /waitlist/status/{code} — check position by ref_code
GET  /waitlist/confirm/{tok} — confirm email
"""

import logging

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_session import get_async_db
from app.api.waitlist import service
from app.api.waitlist.schemas import (
    WaitlistJoinRequest,
    WaitlistJoinResponse,
    WaitlistStatusResponse,
    WaitlistConfirmResponse,
)
from app.api.waitlist.email import send_waitlist_confirmation, send_referrer_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist", tags=["waitlist"])


@router.post("/join", response_model=WaitlistJoinResponse, status_code=201)
async def join(
    body: WaitlistJoinRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
):
    entry = await service.join_waitlist(body.email, body.ref_code, db)
    total = await service._get_total(db)
    ref_link = service.build_referral_link(entry.ref_code)
    eff = service.effective_position(entry)

    # Send confirmation email in background
    background.add_task(send_waitlist_confirmation, entry, ref_link, eff, total)

    # Notify referrer if applicable
    if body.ref_code:
        background.add_task(send_referrer_notification, body.ref_code, db)

    return WaitlistJoinResponse(
        email=entry.email,
        position=entry.position,
        effective_position=eff,
        ref_code=entry.ref_code,
        referral_link=ref_link,
        referral_count=entry.referral_count,
        total_signups=total,
        message=f"You're #{eff} on the waitlist! Share your link to move up.",
    )


@router.get("/status/{ref_code}", response_model=WaitlistStatusResponse)
async def status(ref_code: str, db: AsyncSession = Depends(get_async_db)):
    entry = await service.get_by_ref_code(ref_code, db)
    total = await service._get_total(db)
    ref_link = service.build_referral_link(entry.ref_code)
    eff = service.effective_position(entry)

    return WaitlistStatusResponse(
        email=entry.email,
        position=entry.position,
        effective_position=eff,
        ref_code=entry.ref_code,
        referral_link=ref_link,
        referral_count=entry.referral_count,
        position_boost=entry.position_boost,
        confirmed=entry.confirmed,
        total_signups=total,
        joined_at=entry.created_at,
    )


@router.get("/confirm/{token}", response_model=WaitlistConfirmResponse)
async def confirm(token: str, db: AsyncSession = Depends(get_async_db)):
    entry = await service.confirm_email(token, db)
    return WaitlistConfirmResponse(
        email=entry.email,
        confirmed=entry.confirmed,
        message="Your email is confirmed. We'll notify you when it's your turn!",
    )
