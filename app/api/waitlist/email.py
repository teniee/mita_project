"""
Waitlist email helpers.
Uses the existing EmailService — falls back to logging if not configured.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def send_waitlist_confirmation(entry, referral_link: str, position: int, total: int):
    """Send confirmation + referral email to new waitlist member."""
    try:
        from app.services.email_service import get_email_service, EmailType

        svc = get_email_service()
        subject = f"You're #{position} on the Mita waitlist 🎉"
        html = f"""
        <div style="font-family:'Manrope',sans-serif;max-width:560px;margin:0 auto;background:#FFF8F0;padding:40px;border-radius:24px;">
          <div style="margin-bottom:32px">
            <span style="font-size:28px;font-weight:800;color:#1A3347;">Mita Finance</span>
          </div>
          <h1 style="font-size:32px;font-weight:800;color:#1A3347;line-height:1.1;margin-bottom:16px;">
            You're on the list.<br>You're <span style="color:#F5C842;">#{position}</span>.
          </h1>
          <p style="color:#4A6275;font-size:16px;line-height:1.6;margin-bottom:28px;">
            Out of <strong>{total:,} people</strong> who want to control their money — you're near the front.<br>
            <strong>Share your link and move up the queue.</strong> Each friend you invite bumps you 10 spots.
          </p>
          <div style="background:#1A3347;border-radius:16px;padding:24px;margin-bottom:28px;">
            <p style="color:rgba(255,255,255,0.5);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Your referral link</p>
            <p style="color:#F5C842;font-size:15px;font-weight:700;word-break:break-all;">{referral_link}</p>
          </div>
          <a href="{referral_link}" style="display:inline-block;background:#F5C842;color:#1A3347;font-weight:800;font-size:16px;padding:14px 32px;border-radius:100px;text-decoration:none;">
            Share &amp; Move Up →
          </a>
          <p style="color:#8AA0B0;font-size:13px;margin-top:32px;">
            Mita Finance · Control your money. Daily.<br>
            Not a financial advisor.
          </p>
        </div>
        """
        await svc.send_email(
            to_email=entry.email,
            subject=subject,
            html_content=html,
        )
    except Exception as e:
        logger.warning(f"Waitlist confirmation email failed for {entry.email}: {e}")


async def send_referrer_notification(ref_code: str, db: AsyncSession):
    """Tell the referrer someone used their link."""
    try:
        from app.db.models.waitlist import WaitlistEntry
        from app.services.email_service import get_email_service
        from app.api.waitlist.service import effective_position, build_referral_link

        res = await db.execute(select(WaitlistEntry).where(WaitlistEntry.ref_code == ref_code.upper()))
        referrer = res.scalar_one_or_none()
        if not referrer:
            return

        eff = effective_position(referrer)
        svc = get_email_service()
        subject = "Someone joined Mita with your link 🚀"
        html = f"""
        <div style="font-family:'Manrope',sans-serif;max-width:560px;margin:0 auto;background:#FFF8F0;padding:40px;border-radius:24px;">
          <h2 style="font-size:24px;font-weight:800;color:#1A3347;">Your friend just joined!</h2>
          <p style="color:#4A6275;font-size:16px;">You moved up 10 spots. You're now <strong style="color:#1DB9A0;">#{eff}</strong> on the waitlist.</p>
          <p style="color:#4A6275;font-size:16px;">Keep sharing — each referral = 10 more spots up.</p>
          <a href="{build_referral_link(referrer.ref_code)}" style="display:inline-block;background:#F5C842;color:#1A3347;font-weight:800;font-size:15px;padding:12px 28px;border-radius:100px;text-decoration:none;margin-top:16px;">
            Share Again →
          </a>
        </div>
        """
        await svc.send_email(
            to_email=referrer.email,
            subject=subject,
            html_content=html,
        )
    except Exception as e:
        logger.warning(f"Referrer notification failed for {ref_code}: {e}")
