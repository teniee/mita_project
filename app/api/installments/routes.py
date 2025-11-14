"""
Installment Payment Module - API Routes
Professional Buy Now Pay Later (BNPL) risk assessment and management

Endpoints for installment risk calculation, financial profile management,
installment tracking, calendar integration, and achievement tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from calendar import monthrange

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.core.async_session import get_async_db
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.models.installment import (
    Installment,
    UserFinancialProfile,
    InstallmentAchievement,
    InstallmentStatus,
    RiskLevel,
)
from app.api.installments.schemas import (
    InstallmentCalculatorInput,
    InstallmentCalculatorOutput,
    UserFinancialProfileCreate,
    UserFinancialProfileOut,
    InstallmentCreate,
    InstallmentUpdate,
    InstallmentOut,
    InstallmentsSummary,
    InstallmentAchievementOut,
    MonthlyInstallmentsCalendar,
    InstallmentCalendarEvent,
)
from app.api.installments.services import calculate_installment_risk
from app.utils.response_wrapper import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/installments", tags=["installments"])


# ===== INSTALLMENT CALCULATOR ENDPOINT =====

@router.post("/calculator", response_model=InstallmentCalculatorOutput)
async def calculate_installment(
    calculator_input: InstallmentCalculatorInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Calculate installment risk and get comprehensive financial assessment

    This endpoint provides:
    - Risk level assessment (RED, ORANGE, YELLOW, GREEN)
    - Payment schedule with amortization
    - Financial impact analysis (DTI, payment-to-income ratio)
    - Personalized recommendations based on user's financial situation
    - Alternative approaches for risky installments
    - Educational content and statistics

    Based on BNPL research and US financial best practices.
    """
    try:
        result = await calculate_installment_risk(
            db=db,
            user_id=user.id,
            calculator_input=calculator_input
        )
        return result
    except ValueError as e:
        logger.warning(f"Validation error in installment calculation for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error calculating installment risk for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate installment risk"
        )


# ===== FINANCIAL PROFILE ENDPOINTS =====

@router.post("/profile", response_model=UserFinancialProfileOut, status_code=status.HTTP_201_CREATED)
async def create_or_update_financial_profile(
    profile_data: UserFinancialProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create or update user's financial profile

    Financial profile is used for installment risk assessment.
    Stores income, balance, age group, and existing financial obligations.
    """
    try:
        # Check if profile already exists
        result = await db.execute(
            select(UserFinancialProfile).where(
                UserFinancialProfile.user_id == user.id
            )
        )
        profile = result.scalar_one_or_none()

        if profile:
            # Update existing profile
            profile.monthly_income = profile_data.monthly_income
            profile.current_balance = profile_data.current_balance
            profile.age_group = profile_data.age_group
            profile.credit_card_debt = profile_data.credit_card_debt
            profile.credit_card_payment = profile_data.credit_card_payment
            profile.other_loans_payment = profile_data.other_loans_payment
            profile.rent_payment = profile_data.rent_payment
            profile.subscriptions_payment = profile_data.subscriptions_payment
            profile.planning_mortgage = profile_data.planning_mortgage
            profile.updated_at = datetime.utcnow()

            logger.info(f"Updated financial profile for user {user.id}")
        else:
            # Create new profile
            profile = UserFinancialProfile(
                user_id=user.id,
                monthly_income=profile_data.monthly_income,
                current_balance=profile_data.current_balance,
                age_group=profile_data.age_group,
                credit_card_debt=profile_data.credit_card_debt,
                credit_card_payment=profile_data.credit_card_payment,
                other_loans_payment=profile_data.other_loans_payment,
                rent_payment=profile_data.rent_payment,
                subscriptions_payment=profile_data.subscriptions_payment,
                planning_mortgage=profile_data.planning_mortgage,
            )
            db.add(profile)
            logger.info(f"Created financial profile for user {user.id}")

        await db.commit()
        await db.refresh(profile)

        return profile

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating/updating financial profile for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create/update financial profile"
        )


@router.get("/profile", response_model=UserFinancialProfileOut)
async def get_financial_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get user's financial profile

    Returns the stored financial profile used for risk assessment.
    If no profile exists, returns 404.
    """
    result = await db.execute(
        select(UserFinancialProfile).where(
            UserFinancialProfile.user_id == user.id
        )
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial profile not found. Please create one first."
        )

    return profile


# ===== INSTALLMENT CRUD ENDPOINTS =====

@router.post("/", response_model=InstallmentOut, status_code=status.HTTP_201_CREATED)
async def create_installment(
    installment_data: InstallmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new installment for tracking

    Stores an actual installment payment plan that the user has committed to.
    This enables calendar integration, payment tracking, and progress monitoring.
    """
    try:
        # Calculate final payment date based on frequency and total payments
        payments_remaining = installment_data.total_payments - installment_data.payments_made

        if installment_data.payment_frequency == "monthly":
            final_date = installment_data.next_payment_date + timedelta(days=30 * payments_remaining)
        elif installment_data.payment_frequency == "biweekly":
            final_date = installment_data.next_payment_date + timedelta(days=14 * payments_remaining)
        else:
            # Default to monthly
            final_date = installment_data.next_payment_date + timedelta(days=30 * payments_remaining)

        # Create installment
        installment = Installment(
            user_id=user.id,
            item_name=installment_data.item_name,
            category=installment_data.category,
            total_amount=installment_data.total_amount,
            payment_amount=installment_data.payment_amount,
            interest_rate=installment_data.interest_rate,
            total_payments=installment_data.total_payments,
            payments_made=installment_data.payments_made,
            payment_frequency=installment_data.payment_frequency,
            first_payment_date=installment_data.first_payment_date,
            next_payment_date=installment_data.next_payment_date,
            final_payment_date=final_date,
            status=InstallmentStatus.ACTIVE,
            notes=installment_data.notes,
        )

        db.add(installment)
        await db.commit()
        await db.refresh(installment)

        logger.info(f"Created installment {installment.id} for user {user.id}")

        # Add calculated fields
        installment_out = InstallmentOut.from_orm(installment)
        installment_out.progress_percentage = (
            (installment_data.payments_made / installment_data.total_payments * 100)
            if installment_data.total_payments > 0 else 0
        )
        installment_out.remaining_payments = payments_remaining
        installment_out.total_paid = installment_data.payment_amount * installment_data.payments_made
        installment_out.remaining_balance = installment_data.total_amount - installment_out.total_paid

        return installment_out

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating installment for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create installment"
        )


@router.get("/", response_model=InstallmentsSummary)
async def get_all_installments(
    status_filter: Optional[InstallmentStatus] = Query(None, description="Filter by status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get all user's installments with summary

    Returns comprehensive overview including:
    - All installments (with optional status filter)
    - Total active and completed counts
    - Total monthly payment obligation
    - Next upcoming payment information
    - Risk assessment of current installment load
    """
    try:
        # Build query
        query = select(Installment).where(Installment.user_id == user.id)

        if status_filter:
            query = query.where(Installment.status == status_filter)

        query = query.order_by(Installment.next_payment_date.asc())

        result = await db.execute(query)
        installments = result.scalars().all()

        # Calculate summary statistics
        active_installments = [i for i in installments if i.status == InstallmentStatus.ACTIVE]
        completed_installments = [i for i in installments if i.status == InstallmentStatus.COMPLETED]

        total_active = len(active_installments)
        total_completed = len(completed_installments)

        # Calculate total monthly payment
        total_monthly_payment = Decimal('0.00')
        for installment in active_installments:
            if installment.payment_frequency == "monthly":
                total_monthly_payment += installment.payment_amount
            elif installment.payment_frequency == "biweekly":
                # Convert biweekly to monthly (multiply by 26/12)
                total_monthly_payment += installment.payment_amount * Decimal('2.17')

        # Find next payment
        next_payment_date = None
        next_payment_amount = None

        if active_installments:
            next_installment = min(active_installments, key=lambda x: x.next_payment_date)
            next_payment_date = next_installment.next_payment_date
            next_payment_amount = next_installment.payment_amount

        # Assess current installment load
        load_level = "safe"
        load_message = "Your installment load is healthy"

        if total_active == 0:
            load_level = "safe"
            load_message = "No active installments - excellent financial discipline!"
        elif total_active == 1:
            load_level = "safe"
            load_message = "1 active installment is manageable"
        elif total_active == 2:
            load_level = "moderate"
            load_message = "2 installments require careful tracking"
        elif total_active >= 3:
            load_level = "high"
            load_message = "3+ installments significantly increase financial risk"

        # Check monthly payment burden
        # Get user's financial profile if available
        profile_result = await db.execute(
            select(UserFinancialProfile).where(
                UserFinancialProfile.user_id == user.id
            )
        )
        profile = profile_result.scalar_one_or_none()

        if profile and total_monthly_payment > 0:
            payment_ratio = (total_monthly_payment / profile.monthly_income * 100)
            if payment_ratio > 10:
                load_level = "critical"
                load_message = f"Your installments are {float(payment_ratio):.1f}% of income - this is dangerously high"
            elif payment_ratio > 5:
                load_level = "high"
                load_message = f"Your installments are {float(payment_ratio):.1f}% of income - reduce if possible"

        # Convert installments to output schema with calculated fields
        installment_outs = []
        for inst in installments:
            inst_out = InstallmentOut.from_orm(inst)
            inst_out.progress_percentage = (
                (inst.payments_made / inst.total_payments * 100)
                if inst.total_payments > 0 else 0
            )
            inst_out.remaining_payments = inst.total_payments - inst.payments_made
            inst_out.total_paid = inst.payment_amount * inst.payments_made
            inst_out.remaining_balance = inst.total_amount - inst_out.total_paid
            installment_outs.append(inst_out)

        return InstallmentsSummary(
            total_active=total_active,
            total_completed=total_completed,
            total_monthly_payment=total_monthly_payment,
            next_payment_date=next_payment_date,
            next_payment_amount=next_payment_amount,
            installments=installment_outs,
            current_installment_load=load_level,
            load_message=load_message,
        )

    except Exception as e:
        logger.error(f"Error fetching installments for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch installments"
        )


@router.get("/{installment_id}", response_model=InstallmentOut)
async def get_installment(
    installment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get specific installment by ID

    Returns detailed information about a single installment including progress.
    """
    result = await db.execute(
        select(Installment).where(
            and_(
                Installment.id == installment_id,
                Installment.user_id == user.id
            )
        )
    )
    installment = result.scalar_one_or_none()

    if not installment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installment not found"
        )

    # Add calculated fields
    installment_out = InstallmentOut.from_orm(installment)
    installment_out.progress_percentage = (
        (installment.payments_made / installment.total_payments * 100)
        if installment.total_payments > 0 else 0
    )
    installment_out.remaining_payments = installment.total_payments - installment.payments_made
    installment_out.total_paid = installment.payment_amount * installment.payments_made
    installment_out.remaining_balance = installment.total_amount - installment_out.total_paid

    return installment_out


@router.patch("/{installment_id}", response_model=InstallmentOut)
async def update_installment(
    installment_id: UUID,
    update_data: InstallmentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update installment details

    Allows updating:
    - Payments made count
    - Next payment date
    - Status
    - Notes

    Automatically marks as completed if payments_made equals total_payments.
    """
    try:
        result = await db.execute(
            select(Installment).where(
                and_(
                    Installment.id == installment_id,
                    Installment.user_id == user.id
                )
            )
        )
        installment = result.scalar_one_or_none()

        if not installment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Installment not found"
            )

        # Update fields if provided
        if update_data.payments_made is not None:
            installment.payments_made = update_data.payments_made

            # Auto-complete if all payments made
            if installment.payments_made >= installment.total_payments:
                installment.status = InstallmentStatus.COMPLETED
                logger.info(f"Auto-completed installment {installment_id}")

        if update_data.next_payment_date is not None:
            installment.next_payment_date = update_data.next_payment_date

        if update_data.status is not None:
            installment.status = update_data.status

        if update_data.notes is not None:
            installment.notes = update_data.notes

        installment.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(installment)

        logger.info(f"Updated installment {installment_id} for user {user.id}")

        # Add calculated fields
        installment_out = InstallmentOut.from_orm(installment)
        installment_out.progress_percentage = (
            (installment.payments_made / installment.total_payments * 100)
            if installment.total_payments > 0 else 0
        )
        installment_out.remaining_payments = installment.total_payments - installment.payments_made
        installment_out.total_paid = installment.payment_amount * installment.payments_made
        installment_out.remaining_balance = installment.total_amount - installment_out.total_paid

        return installment_out

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating installment {installment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update installment"
        )


@router.delete("/{installment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_installment(
    installment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete installment

    Permanently removes an installment from tracking.
    Use status update to CANCELLED instead if you want to keep history.
    """
    try:
        result = await db.execute(
            select(Installment).where(
                and_(
                    Installment.id == installment_id,
                    Installment.user_id == user.id
                )
            )
        )
        installment = result.scalar_one_or_none()

        if not installment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Installment not found"
            )

        await db.delete(installment)
        await db.commit()

        logger.info(f"Deleted installment {installment_id} for user {user.id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting installment {installment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete installment"
        )


# ===== CALENDAR INTEGRATION ENDPOINT =====

@router.get("/calendar/{year}/{month}", response_model=MonthlyInstallmentsCalendar)
async def get_monthly_calendar(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get monthly calendar view of installment payments

    Returns all payment dates in the specified month with:
    - Payment amounts and installment details
    - Status (upcoming, today, overdue)
    - Days until payment
    - Total payments for the month
    - Available balance after installments
    """
    try:
        # Validate month/year
        if month < 1 or month > 12:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Month must be between 1 and 12"
            )

        if year < 2000 or year > 2100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Year must be between 2000 and 2100"
            )

        # Get month boundaries
        first_day = datetime(year, month, 1)
        last_day_num = monthrange(year, month)[1]
        last_day = datetime(year, month, last_day_num, 23, 59, 59)

        # Get active installments
        result = await db.execute(
            select(Installment).where(
                and_(
                    Installment.user_id == user.id,
                    Installment.status == InstallmentStatus.ACTIVE
                )
            )
        )
        installments = result.scalars().all()

        # Build calendar events
        payment_events = []
        total_payments = Decimal('0.00')
        today = datetime.utcnow()

        for installment in installments:
            # Check if payment falls in this month
            next_payment = installment.next_payment_date

            # Generate all payment dates for this installment in the month
            current_date = next_payment
            while current_date <= last_day:
                if current_date >= first_day:
                    # This payment is in the requested month
                    days_until = (current_date.date() - today.date()).days

                    # Determine status
                    if days_until < 0:
                        event_status = "overdue"
                    elif days_until == 0:
                        event_status = "today"
                    else:
                        event_status = "upcoming"

                    payment_events.append(
                        InstallmentCalendarEvent(
                            installment_id=installment.id,
                            item_name=installment.item_name,
                            payment_amount=installment.payment_amount,
                            payment_date=current_date,
                            is_upcoming=days_until >= 0,
                            days_until_payment=days_until,
                            status=event_status,
                        )
                    )

                    total_payments += installment.payment_amount

                # Move to next payment date based on frequency
                if installment.payment_frequency == "monthly":
                    # Add roughly 30 days
                    current_date = current_date + timedelta(days=30)
                elif installment.payment_frequency == "biweekly":
                    current_date = current_date + timedelta(days=14)
                else:
                    break

        # Sort by payment date
        payment_events.sort(key=lambda x: x.payment_date)

        # Calculate available funds after installments
        # Get user's financial profile
        profile_result = await db.execute(
            select(UserFinancialProfile).where(
                UserFinancialProfile.user_id == user.id
            )
        )
        profile = profile_result.scalar_one_or_none()

        if profile:
            available_after = profile.current_balance - total_payments
        else:
            available_after = Decimal('0.00')

        return MonthlyInstallmentsCalendar(
            year=year,
            month=month,
            total_payments_this_month=total_payments,
            payment_dates=payment_events,
            available_after_installments=available_after,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating calendar for user {user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate calendar"
        )


# ===== ACHIEVEMENTS ENDPOINT =====

@router.get("/achievements", response_model=InstallmentAchievementOut)
async def get_achievements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get user's installment management achievements

    Returns gamification data including:
    - Installments completed
    - Calculations performed
    - Smart decisions (declined risky installments)
    - Streak tracking (days without new installments)
    - Interest saved by declining high-interest offers
    - Achievement level (Beginner, Cautious, Wise, Master)
    """
    result = await db.execute(
        select(InstallmentAchievement).where(
            InstallmentAchievement.user_id == user.id
        )
    )
    achievement = result.scalar_one_or_none()

    if not achievement:
        # Create initial achievement record
        achievement = InstallmentAchievement(
            user_id=user.id,
            installments_completed=0,
            calculations_performed=0,
            calculations_declined=0,
            days_without_new_installment=0,
            max_days_streak=0,
            interest_saved=Decimal('0.00'),
            achievement_level="beginner",
        )
        db.add(achievement)
        await db.commit()
        await db.refresh(achievement)

        logger.info(f"Created initial achievement record for user {user.id}")

    return achievement
