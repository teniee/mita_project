"""
Installment Payment Module - Database Models
MITA Finance - Smart Installment Payment Management

Based on BNPL (Buy Now Pay Later) research and US financial best practices.
Safe thresholds: payment <5% of income, balance >$2500, DTI <35%
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class InstallmentCategory(str, PyEnum):
    """Purchase categories for installment risk assessment"""
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    FURNITURE = "furniture"
    TRAVEL = "travel"
    EDUCATION = "education"
    HEALTH = "health"
    GROCERIES = "groceries"  # RED FLAG - high risk
    UTILITIES = "utilities"  # RED FLAG - high risk
    OTHER = "other"


class AgeGroup(str, PyEnum):
    """User age groups for risk assessment"""
    AGE_18_24 = "18-24"  # Highest risk: 51% late payment rate
    AGE_25_34 = "25-34"  # Moderate risk
    AGE_35_44 = "35-44"  # Lower risk
    AGE_45_PLUS = "45+"  # Lowest risk


class RiskLevel(str, PyEnum):
    """Risk assessment levels based on financial analysis"""
    GREEN = "green"      # Safe to proceed
    YELLOW = "yellow"    # Consider carefully
    ORANGE = "orange"    # Risky
    RED = "red"          # Not recommended


class InstallmentStatus(str, PyEnum):
    """Status of installment payments"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class Installment(Base):
    """
    User's active installment payment tracking
    Stores real installments for payment tracking and calendar integration
    """
    __tablename__ = "installments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Installment details
    item_name = Column(String(200), nullable=False)
    category = Column(
        Enum(InstallmentCategory, native_enum=False),
        default=InstallmentCategory.OTHER,
        nullable=False
    )

    # Financial details (all amounts in USD)
    total_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    payment_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    interest_rate = Column(Numeric(precision=5, scale=2), default=0, nullable=False)

    # Payment schedule
    total_payments = Column(Integer, nullable=False)  # Total number of payments
    payments_made = Column(Integer, default=0, nullable=False)  # Payments completed
    payment_frequency = Column(String(20), default="monthly", nullable=False)  # monthly, biweekly

    # Dates
    first_payment_date = Column(DateTime(timezone=True), nullable=False)
    next_payment_date = Column(DateTime(timezone=True), nullable=False)
    final_payment_date = Column(DateTime(timezone=True), nullable=False)

    # Status and tracking
    status = Column(
        Enum(InstallmentStatus, native_enum=False),
        default=InstallmentStatus.ACTIVE,
        nullable=False
    )

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None, index=True)  # Soft delete support

    # Relationships
    user = relationship("User", backref="installments")
    calculations = relationship("InstallmentCalculation", back_populates="installment")


class UserFinancialProfile(Base):
    """
    User's financial profile for installment risk assessment
    Updated periodically to reflect current financial situation
    """
    __tablename__ = "user_financial_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Income (after taxes in USD)
    monthly_income = Column(Numeric(precision=12, scale=2), nullable=False)

    # Current financial state (in USD)
    current_balance = Column(Numeric(precision=12, scale=2), nullable=False)

    # Demographics
    age_group = Column(
        Enum(AgeGroup, native_enum=False),
        default=AgeGroup.AGE_25_34,
        nullable=False
    )

    # Existing financial obligations (monthly amounts in USD)
    credit_card_debt = Column(Boolean, default=False, nullable=False)
    credit_card_payment = Column(Numeric(precision=12, scale=2), default=0, nullable=False)

    other_loans_payment = Column(Numeric(precision=12, scale=2), default=0, nullable=False)
    rent_payment = Column(Numeric(precision=12, scale=2), default=0, nullable=False)
    subscriptions_payment = Column(Numeric(precision=12, scale=2), default=0, nullable=False)

    # Future plans
    planning_mortgage = Column(Boolean, default=False, nullable=False)

    # Metadata
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="financial_profile")


class InstallmentCalculation(Base):
    """
    History of installment calculations for analytics and user insights
    Tracks what users consider vs what they actually take
    """
    __tablename__ = "installment_calculations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    installment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("installments.id"),
        nullable=True,
        index=True
    )  # NULL if calculation didn't result in actual installment

    # Purchase details
    purchase_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    category = Column(
        Enum(InstallmentCategory, native_enum=False),
        nullable=False
    )

    # Payment structure
    num_payments = Column(Integer, nullable=False)
    interest_rate = Column(Numeric(precision=5, scale=2), nullable=False)
    monthly_payment = Column(Numeric(precision=12, scale=2), nullable=False)
    total_interest = Column(Numeric(precision=12, scale=2), nullable=False)

    # Risk assessment results
    risk_level = Column(
        Enum(RiskLevel, native_enum=False),
        nullable=False
    )

    # Financial metrics at time of calculation
    dti_ratio = Column(Numeric(precision=5, scale=2), nullable=False)  # Debt-to-Income %
    payment_to_income_ratio = Column(Numeric(precision=5, scale=2), nullable=False)  # Payment as % of income
    remaining_balance = Column(Numeric(precision=12, scale=2), nullable=False)

    # Risk factors that triggered (JSON stored as text)
    risk_factors = Column(Text, nullable=True)  # JSON string of triggered risk factors

    # User decision
    user_proceeded = Column(Boolean, default=False, nullable=False)  # Did user create actual installment?

    # Metadata
    calculated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", backref="installment_calculations")
    installment = relationship("Installment", back_populates="calculations")


class InstallmentAchievement(Base):
    """
    User achievements and milestones in installment management
    Gamification for better financial behavior
    """
    __tablename__ = "installment_achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Achievement tracking
    installments_completed = Column(Integer, default=0, nullable=False)
    calculations_performed = Column(Integer, default=0, nullable=False)
    calculations_declined = Column(Integer, default=0, nullable=False)  # User said "no" to risky installments

    # Streak tracking
    days_without_new_installment = Column(Integer, default=0, nullable=False)
    max_days_streak = Column(Integer, default=0, nullable=False)

    # Financial discipline metrics
    interest_saved = Column(Numeric(precision=12, scale=2), default=0, nullable=False)  # By declining high-interest offers

    # Achievement level (Beginner, Cautious, Wise, Master)
    achievement_level = Column(String(20), default="beginner", nullable=False)

    # Metadata
    last_calculation_date = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="installment_achievements")
