"""
Installment Payment Module - Business Logic and Risk Assessment
Professional Financial Analysis for US Consumers

Research-based thresholds (BNPL studies 2023-2024):
- Payment >5% of income = RED (high default risk)
- Balance <$2,500 = RED (insufficient buffer)
- DTI >43% = RED (debt overload)
- 3+ active installments = ORANGE (66% face problems)
- Age 18-24 = higher risk (51% late payment rate)
- Credit card debt present = RED (71% can't manage both)
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.installment import (
    Installment,
    UserFinancialProfile,
    InstallmentCalculation,
    InstallmentAchievement,
    InstallmentCategory,
    AgeGroup,
    RiskLevel,
    InstallmentStatus
)
from app.api.installments.schemas import (
    InstallmentCalculatorInput,
    InstallmentCalculatorOutput,
    RiskFactor,
    AlternativeRecommendation,
    InstallmentCreate,
    InstallmentUpdate,
    InstallmentOut,
    InstallmentsSummary,
    UserFinancialProfileCreate,
    UserFinancialProfileOut
)


# ===== CONSTANTS BASED ON US FINANCIAL RESEARCH =====

class InstallmentConstants:
    """Research-based financial thresholds for US consumers"""

    # CRITICAL THRESHOLDS (from BNPL research)
    SAFE_PAYMENT_RATIO = Decimal('5.0')  # Max 5% of monthly income
    CRITICAL_PAYMENT_RATIO = Decimal('3.0')  # 3-5% is moderate risk
    IDEAL_PAYMENT_RATIO = Decimal('2.0')  # <2% is ideal

    MIN_SAFE_BALANCE = Decimal('2500.00')  # Minimum $2,500 balance
    COMFORTABLE_BALANCE = Decimal('3500.00')  # $3,500+ is comfortable
    STRONG_BALANCE = Decimal('5000.00')  # $5,000+ is strong

    SAFE_DTI = Decimal('25.0')  # <25% DTI is safe
    MODERATE_DTI = Decimal('35.0')  # 25-35% is moderate
    CRITICAL_DTI = Decimal('43.0')  # >43% is critical (FHA limit)

    # INSTALLMENT LIMITS
    MAX_SAFE_INSTALLMENTS = 1  # 0-1 is safe
    MODERATE_INSTALLMENTS = 2  # 2 is risky
    CRITICAL_INSTALLMENTS = 3  # 3+ is very risky (66% problems)

    # AGE-BASED RISK (research shows 51% of 18-24 late on payments)
    YOUNG_AGE_INSTALLMENT_LIMIT = 1  # Young adults should limit to 1

    # INTEREST RATE THRESHOLDS
    ZERO_INTEREST = Decimal('0.0')
    LOW_INTEREST = Decimal('10.0')
    MODERATE_INTEREST = Decimal('15.0')
    HIGH_INTEREST = Decimal('20.0')
    PREDATORY_INTEREST = Decimal('30.0')

    # EMERGENCY FUND
    MIN_EMERGENCY_BUFFER = Decimal('300.00')  # After payment
    SAFE_EMERGENCY_BUFFER = Decimal('500.00')
    STRONG_EMERGENCY_BUFFER = Decimal('1000.00')


class InstallmentRiskEngine:
    """
    Professional risk assessment engine for installment payments
    Based on BNPL research and US consumer financial best practices
    """

    @staticmethod
    def calculate_payment_schedule(
        principal: Decimal,
        num_payments: int,
        annual_interest_rate: Decimal,
        frequency: str = "monthly"
    ) -> Tuple[Decimal, Decimal, List[Dict]]:
        """
        Calculate payment schedule using standard amortization formula
        Returns: (monthly_payment, total_interest, schedule)
        """
        if annual_interest_rate == 0:
            # Simple division for 0% interest
            payment = principal / num_payments
            total_interest = Decimal('0.00')

            schedule = []
            for i in range(1, num_payments + 1):
                schedule.append({
                    "payment_number": i,
                    "payment_amount": float(payment),
                    "principal": float(payment),
                    "interest": 0.0,
                    "remaining_balance": float(principal - (payment * i))
                })

            return payment, total_interest, schedule

        # Calculate with interest
        monthly_rate = annual_interest_rate / 100 / 12

        # Standard amortization formula: M = P * [r(1+r)^n] / [(1+r)^n - 1]
        if monthly_rate > 0:
            monthly_payment = principal * (
                monthly_rate * ((1 + monthly_rate) ** num_payments)
            ) / (
                ((1 + monthly_rate) ** num_payments) - 1
            )
        else:
            monthly_payment = principal / num_payments

        # Round to 2 decimal places
        monthly_payment = round(monthly_payment, 2)

        # Generate amortization schedule
        schedule = []
        remaining_balance = principal
        total_interest_paid = Decimal('0.00')

        for i in range(1, num_payments + 1):
            interest_payment = remaining_balance * monthly_rate
            principal_payment = monthly_payment - interest_payment
            remaining_balance -= principal_payment
            total_interest_paid += interest_payment

            # Adjust last payment for rounding
            if i == num_payments:
                principal_payment += remaining_balance
                remaining_balance = Decimal('0.00')

            schedule.append({
                "payment_number": i,
                "payment_amount": float(monthly_payment),
                "principal": float(round(principal_payment, 2)),
                "interest": float(round(interest_payment, 2)),
                "remaining_balance": float(round(max(remaining_balance, 0), 2))
            })

        return monthly_payment, total_interest_paid, schedule

    @staticmethod
    def assess_risk(
        monthly_payment: Decimal,
        monthly_income: Decimal,
        current_balance: Decimal,
        category: InstallmentCategory,
        age_group: AgeGroup,
        credit_card_debt: bool,
        active_installments_count: int,
        active_installments_monthly: Decimal,
        other_monthly_obligations: Decimal,
        planning_mortgage: bool,
        interest_rate: Decimal,
        num_payments: int
    ) -> Tuple[RiskLevel, int, List[RiskFactor]]:
        """
        Comprehensive risk assessment based on multiple factors
        Returns: (risk_level, risk_score, risk_factors)
        """
        risk_factors = []
        red_flags = 0
        orange_flags = 0
        yellow_flags = 0

        # Calculate key ratios
        payment_ratio = (monthly_payment / monthly_income * 100) if monthly_income > 0 else Decimal('100.0')

        total_monthly_debt = (
            monthly_payment + active_installments_monthly + other_monthly_obligations
        )
        dti_ratio = (total_monthly_debt / monthly_income * 100) if monthly_income > 0 else Decimal('100.0')

        balance_after_payment = current_balance - monthly_payment

        # === RED FLAG CHECKS (Automatic RED if ANY triggered) ===

        # 1. Payment >5% of income
        if payment_ratio > InstallmentConstants.SAFE_PAYMENT_RATIO:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="high_payment_ratio",
                severity="high",
                message=f"This payment is {float(payment_ratio):.1f}% of your income (safe limit: 5%)",
                stat="Research shows payments >5% of income have high default rates"
            ))

        # 2. Balance <$2,500
        if current_balance < InstallmentConstants.MIN_SAFE_BALANCE:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="low_balance",
                severity="high",
                message=f"Your balance (${float(current_balance):.2f}) is below the safe minimum of $2,500",
                stat="77% of BNPL users with balances <$2,500 struggle with payments"
            ))

        # 3. DTI >43% (FHA limit)
        if dti_ratio > InstallmentConstants.CRITICAL_DTI:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="critical_dti",
                severity="high",
                message=f"Your debt-to-income ratio ({float(dti_ratio):.1f}%) exceeds 43% (FHA limit)",
                stat="DTI >43% indicates severe debt overload - lenders won't approve new credit"
            ))

        # 4. Credit card debt present
        if credit_card_debt:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="credit_card_debt",
                severity="high",
                message="You have existing credit card debt",
                stat="71% of people with credit card debt can't manage additional installments"
            ))

        # 5. Dangerous categories (groceries, utilities)
        if category in [InstallmentCategory.GROCERIES, InstallmentCategory.UTILITIES]:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="dangerous_category",
                severity="high",
                message=f"Taking installments for {category.value} indicates financial distress",
                stat="Installment payments for essentials like food/utilities signal critical cash flow problems"
            ))

        # 6. 3+ active installments
        if active_installments_count >= InstallmentConstants.CRITICAL_INSTALLMENTS:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="too_many_installments",
                severity="high",
                message=f"You already have {active_installments_count} active installments",
                stat="66% of people with 3+ installments face financial difficulties"
            ))

        # 7. Planning mortgage + any installment
        if planning_mortgage:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="mortgage_planning",
                severity="high",
                message="You're planning to apply for a mortgage within 6 months",
                stat="Mortgage lenders scrutinize ALL installments - even paid ones stay on your report for 2 years"
            ))

        # 8. Balance after payment <$300
        if balance_after_payment < InstallmentConstants.MIN_EMERGENCY_BUFFER:
            red_flags += 1
            risk_factors.append(RiskFactor(
                factor="no_emergency_buffer",
                severity="high",
                message=f"After first payment, you'd have only ${float(balance_after_payment):.2f} left",
                stat="No emergency buffer means one unexpected expense could trigger overdrafts and late fees"
            ))

        # === ORANGE FLAG CHECKS (2+ triggers = ORANGE) ===

        # Payment 3-5% of income
        if InstallmentConstants.CRITICAL_PAYMENT_RATIO < payment_ratio <= InstallmentConstants.SAFE_PAYMENT_RATIO:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="moderate_payment_ratio",
                severity="medium",
                message=f"Payment is {float(payment_ratio):.1f}% of your income (moderate risk zone)",
                stat="Payments 3-5% of income are manageable but leave little room for error"
            ))

        # Balance $2,500-$3,500
        if InstallmentConstants.MIN_SAFE_BALANCE <= current_balance < InstallmentConstants.COMFORTABLE_BALANCE:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="moderate_balance",
                severity="medium",
                message=f"Your balance (${float(current_balance):.2f}) provides minimal cushion",
                stat="Balance between $2,500-$3,500 offers limited protection against emergencies"
            ))

        # DTI 36-43%
        if InstallmentConstants.MODERATE_DTI < dti_ratio <= InstallmentConstants.CRITICAL_DTI:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="high_dti",
                severity="medium",
                message=f"Your DTI ratio ({float(dti_ratio):.1f}%) is in the risky zone (36-43%)",
                stat="DTI 36-43% limits your ability to handle unexpected expenses"
            ))

        # 2 active installments
        if active_installments_count == InstallmentConstants.MODERATE_INSTALLMENTS:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="multiple_installments",
                severity="medium",
                message=f"You already have {active_installments_count} active installments",
                stat="Having 2 installments doubles your risk of missing payments"
            ))

        # Age 18-24 + any installment
        if age_group == AgeGroup.AGE_18_24 and active_installments_count >= 1:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="young_age_risk",
                severity="medium",
                message="You're in the 18-24 age group with existing installments",
                stat="51% of 18-24 year-olds with multiple installments experience late payments"
            ))

        # Balance after payment $300-$500
        if InstallmentConstants.MIN_EMERGENCY_BUFFER <= balance_after_payment < InstallmentConstants.SAFE_EMERGENCY_BUFFER:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="tight_emergency_buffer",
                severity="medium",
                message=f"After first payment, you'd have ${float(balance_after_payment):.2f} left",
                stat="Minimal emergency buffer increases risk of overdrafts if unexpected expenses arise"
            ))

        # Long term with interest >0%
        if num_payments > 12 and interest_rate > InstallmentConstants.ZERO_INTEREST:
            orange_flags += 1
            risk_factors.append(RiskFactor(
                factor="long_term_interest",
                severity="medium",
                message=f"12+ month term with {float(interest_rate)}% interest compounds costs",
                stat="Longer terms with interest significantly increase total cost"
            ))

        # === YELLOW FLAG CHECKS (2+ triggers = YELLOW) ===

        # Payment 2-3% of income
        if InstallmentConstants.IDEAL_PAYMENT_RATIO < payment_ratio <= InstallmentConstants.CRITICAL_PAYMENT_RATIO:
            yellow_flags += 1
            risk_factors.append(RiskFactor(
                factor="noticeable_payment",
                severity="low",
                message=f"Payment is {float(payment_ratio):.1f}% of your income",
                stat="Payments 2-3% of income are manageable but worth considering"
            ))

        # Balance $3,500-$5,000
        if InstallmentConstants.COMFORTABLE_BALANCE <= current_balance < InstallmentConstants.STRONG_BALANCE:
            yellow_flags += 1
            risk_factors.append(RiskFactor(
                factor="adequate_balance",
                severity="low",
                message=f"Your balance (${float(current_balance):.2f}) is adequate but not strong",
                stat="Balance $3,500-$5,000 provides reasonable cushion"
            ))

        # DTI 25-35%
        if InstallmentConstants.SAFE_DTI < dti_ratio <= InstallmentConstants.MODERATE_DTI:
            yellow_flags += 1
            risk_factors.append(RiskFactor(
                factor="moderate_dti",
                severity="low",
                message=f"Your DTI ratio ({float(dti_ratio):.1f}%) is in moderate range",
                stat="DTI 25-35% is manageable but limits financial flexibility"
            ))

        # 1 active installment
        if active_installments_count == InstallmentConstants.MAX_SAFE_INSTALLMENTS:
            yellow_flags += 1
            risk_factors.append(RiskFactor(
                factor="one_installment",
                severity="low",
                message="You already have 1 active installment",
                stat="Managing multiple payment schedules requires discipline"
            ))

        # Balance after payment $500-$1,000
        if InstallmentConstants.SAFE_EMERGENCY_BUFFER <= balance_after_payment < InstallmentConstants.STRONG_EMERGENCY_BUFFER:
            yellow_flags += 1
            risk_factors.append(RiskFactor(
                factor="moderate_emergency_buffer",
                severity="low",
                message=f"After first payment, you'd have ${float(balance_after_payment):.2f} left",
                stat="Having $500-$1,000 buffer provides decent protection"
            ))

        # Interest rate >15%
        if interest_rate > InstallmentConstants.MODERATE_INTEREST:
            yellow_flags += 1
            risk_factors.append(RiskFactor(
                factor="high_interest_rate",
                severity="low",
                message=f"Interest rate of {float(interest_rate)}% is significant",
                stat=f"Interest rates >15% substantially increase total cost"
            ))

        # === DETERMINE FINAL RISK LEVEL ===

        if red_flags > 0:
            risk_level = RiskLevel.RED
            risk_score = min(90 + red_flags * 5, 100)
        elif orange_flags >= 2:
            risk_level = RiskLevel.ORANGE
            risk_score = 60 + orange_flags * 5
        elif yellow_flags >= 2:
            risk_level = RiskLevel.YELLOW
            risk_score = 30 + yellow_flags * 5
        else:
            risk_level = RiskLevel.GREEN
            risk_score = max(10 - yellow_flags * 3, 0)

        return risk_level, risk_score, risk_factors

    @staticmethod
    def generate_personalized_message(
        risk_level: RiskLevel,
        risk_factors: List[RiskFactor],
        category: InstallmentCategory,
        age_group: AgeGroup
    ) -> str:
        """Generate personalized message based on user's specific situation"""

        if risk_level == RiskLevel.RED:
            # Find the most severe risk factor
            high_severity_factors = [f for f in risk_factors if f.severity == "high"]

            if any(f.factor == "credit_card_debt" for f in high_severity_factors):
                return "You currently have credit card debt. Research shows 71% of people in this situation struggle when adding installment payments. Focus on paying off your credit card first - the interest rates are likely much higher than any installment."

            elif any(f.factor == "dangerous_category" for f in high_severity_factors):
                if category == InstallmentCategory.GROCERIES:
                    return "Taking installments for groceries is a serious red flag. This indicates you don't have enough cash flow for essentials. Instead of an installment, look into food assistance programs, food banks, or budgeting apps to stretch your current income."
                else:
                    return "Taking installments for utilities signals critical cash flow problems. Consider contacting your utility company about payment plans or assistance programs - they're usually more forgiving than installment providers."

            elif any(f.factor == "too_many_installments" for f in high_severity_factors):
                return "You already have 3 or more active installments. Studies show 66% of people in this situation face serious financial difficulties. Adding another installment would push you into very dangerous territory. Focus on completing your existing obligations first."

            elif any(f.factor == "high_payment_ratio" for f in high_severity_factors):
                return "This payment is too large relative to your income. Financial experts recommend keeping any single payment under 5% of your monthly income. This installment would strain your budget significantly and leave you vulnerable to financial emergencies."

            elif any(f.factor == "mortgage_planning" for f in high_severity_factors):
                return "Since you're planning to apply for a mortgage within 6 months, avoid ANY new installments. Mortgage lenders scrutinize your debt-to-income ratio very carefully, and even zero-interest installments count against you. Wait until after your mortgage is approved."

            else:
                return "Based on your current financial situation, this installment carries significant risk. Multiple red flags indicate you may struggle with the payments, potentially triggering late fees, overdrafts, and damage to your credit score. We strongly advise against proceeding."

        elif risk_level == RiskLevel.ORANGE:
            if age_group == AgeGroup.AGE_18_24:
                return "At your age, financial habits you build now will follow you for years. While this installment is technically possible, statistics show 51% of 18-24 year-olds experience late payments. Consider waiting and building stronger financial habits first. Your future self will thank you."

            elif any(f.factor == "multiple_installments" for f in risk_factors):
                return "You already have multiple installments, and adding another increases your risk significantly. Each additional payment schedule makes it harder to track and manage your finances. If you really need this purchase, consider completing one of your current installments first."

            else:
                return "This installment is risky for your current situation. While you might be able to manage the payments, you have very little margin for error. One unexpected expense (car repair, medical bill, job loss) could trigger a cascade of late payments and fees. Proceed with extreme caution."

        elif risk_level == RiskLevel.YELLOW:
            return "This installment is manageable but worth considering carefully. You have enough income and balance to handle it, but it will reduce your financial flexibility. Make sure you have a solid emergency fund and stable income before committing. Consider whether you could save up and buy it outright in a few months instead."

        else:  # GREEN
            return "Based on your strong financial position, you can afford this installment safely. However, remember that paying cash is always better than debt - even at 0% interest. Installments create mental overhead and reduce your financial flexibility. Make sure this purchase aligns with your financial goals."

    @staticmethod
    def generate_alternative_recommendation(
        risk_level: RiskLevel,
        purchase_amount: Decimal,
        monthly_payment: Decimal,
        monthly_income: Decimal,
        num_payments: int,
        total_interest: Decimal
    ) -> Optional[AlternativeRecommendation]:
        """Generate alternative recommendations based on risk level"""

        if risk_level == RiskLevel.RED:
            # Suggest saving up instead
            # Assume they can save 10% of income per month
            saveable_amount = monthly_income * Decimal('0.10')
            months_to_save = int((purchase_amount / saveable_amount).to_integral_value())

            return AlternativeRecommendation(
                recommendation_type="save_instead",
                title="Save up instead",
                description=f"If you save ${float(saveable_amount):.2f} per month (10% of your income), you can afford this in {months_to_save} months. This way you avoid debt, build saving habits, and might even get a better deal waiting for a sale.",
                savings_amount=saveable_amount,
                time_needed_days=months_to_save * 30
            )

        elif risk_level == RiskLevel.ORANGE:
            # Suggest saving half and financing half
            half_amount = purchase_amount / 2
            saveable_amount = monthly_income * Decimal('0.15')
            months_to_save = int((half_amount / saveable_amount).to_integral_value())

            return AlternativeRecommendation(
                recommendation_type="save_half",
                title="Save half, then finance",
                description=f"If you wait {months_to_save} months and save ${float(half_amount):.2f}, you could then finance only half. This would reduce your monthly payment to ${float(monthly_payment/2):.2f}, making it much safer.",
                savings_amount=saveable_amount,
                time_needed_days=months_to_save * 30
            )

        elif risk_level == RiskLevel.YELLOW:
            # Suggest shorter term
            if num_payments > 6:
                shorter_payments = max(num_payments // 2, 4)
                return AlternativeRecommendation(
                    recommendation_type="shorter_term",
                    title="Consider a shorter term",
                    description=f"Instead of {num_payments} payments, consider {shorter_payments} payments. Yes, the monthly payment will be higher, but you'll be debt-free sooner and pay less interest (if any). This also reduces the risk of life changes affecting your ability to pay.",
                    savings_amount=None,
                    time_needed_days=None
                )

        # GREEN level gets positive reinforcement but still suggests cash
        if risk_level == RiskLevel.GREEN:
            return AlternativeRecommendation(
                recommendation_type="pay_cash",
                title="Consider paying cash",
                description=f"While you can afford this installment, paying cash eliminates mental overhead, gives you stronger negotiating power (ask for a cash discount!), and keeps your credit utilization low. Plus, the psychological benefit of owning it outright is real.",
                savings_amount=None,
                time_needed_days=None
            )

        return None

    @staticmethod
    def generate_verdict_message(risk_level: RiskLevel) -> str:
        """Generate short verdict message"""
        verdicts = {
            RiskLevel.RED: "We don't recommend this",
            RiskLevel.ORANGE: "This is risky",
            RiskLevel.YELLOW: "Think it through",
            RiskLevel.GREEN: "You can afford this"
        }
        return verdicts[risk_level]

    @staticmethod
    def generate_statistics(
        risk_level: RiskLevel,
        category: InstallmentCategory,
        age_group: AgeGroup,
        active_installments_count: int
    ) -> List[str]:
        """Generate relevant statistics to display"""
        stats = []

        # Universal stats
        stats.append("41% of BNPL users miss at least one payment")
        stats.append("Average BNPL user has 9.5 installments per year")

        # Risk-specific stats
        if risk_level == RiskLevel.RED:
            stats.append("71% of people with credit card debt can't manage installments")
            stats.append("Only 37% of frequent installment users can cover a $400 emergency")

        if age_group == AgeGroup.AGE_18_24:
            stats.append("51% of 18-24 year-olds with installments experience late payments")

        if active_installments_count >= 2:
            stats.append("66% of people with 3+ active installments face financial difficulties")

        if category in [InstallmentCategory.GROCERIES, InstallmentCategory.UTILITIES]:
            stats.append("Installments for essentials indicate serious cash flow problems")

        return stats[:4]  # Limit to 4 most relevant stats

    @staticmethod
    def generate_warnings(
        risk_level: RiskLevel,
        interest_rate: Decimal,
        category: InstallmentCategory
    ) -> List[str]:
        """Generate important warnings"""
        warnings = []

        if interest_rate > InstallmentConstants.ZERO_INTEREST:
            warnings.append(f"Interest rate of {float(interest_rate)}% will increase total cost significantly")

        if risk_level == RiskLevel.RED:
            warnings.append("This installment could trigger a debt spiral - one missed payment leads to fees, overdrafts, and more financial stress")

        if category == InstallmentCategory.ELECTRONICS:
            warnings.append("Electronics depreciate quickly - you'll still be paying for it when it's worth much less")

        return warnings


async def calculate_installment_risk(
    db: AsyncSession,
    user_id: UUID,
    calculator_input: InstallmentCalculatorInput
) -> InstallmentCalculatorOutput:
    """
    Main entry point for installment risk calculation
    Returns comprehensive risk assessment and recommendations
    """
    engine = InstallmentRiskEngine()

    # Get or use financial profile
    if calculator_input.monthly_income is not None:
        monthly_income = calculator_input.monthly_income
        current_balance = calculator_input.current_balance or Decimal('0')
        age_group = calculator_input.age_group or AgeGroup.AGE_25_34
    else:
        # Fetch from database
        result = await db.execute(
            select(UserFinancialProfile).where(
                UserFinancialProfile.user_id == user_id
            )
        )
        profile = result.scalar_one_or_none()

        if not profile:
            raise ValueError("Financial profile not found. Please provide financial information.")

        monthly_income = profile.monthly_income
        current_balance = profile.current_balance
        age_group = profile.age_group

    # Calculate payment schedule
    monthly_payment, total_interest, payment_schedule = engine.calculate_payment_schedule(
        principal=calculator_input.purchase_amount,
        num_payments=calculator_input.num_payments,
        annual_interest_rate=calculator_input.interest_rate
    )

    # Calculate financial metrics
    total_cost = calculator_input.purchase_amount + total_interest

    total_monthly_obligations = (
        calculator_input.active_installments_monthly +
        calculator_input.other_monthly_obligations
    )

    payment_to_income = (monthly_payment / monthly_income * 100) if monthly_income > 0 else Decimal('100')
    dti_with_installment = ((monthly_payment + total_monthly_obligations) / monthly_income * 100) if monthly_income > 0 else Decimal('100')
    balance_after_payment = current_balance - monthly_payment
    remaining_monthly = monthly_income - monthly_payment - total_monthly_obligations

    # Perform risk assessment
    risk_level, risk_score, risk_factors = engine.assess_risk(
        monthly_payment=monthly_payment,
        monthly_income=monthly_income,
        current_balance=current_balance,
        category=calculator_input.category,
        age_group=age_group,
        credit_card_debt=calculator_input.credit_card_debt,
        active_installments_count=calculator_input.active_installments_count,
        active_installments_monthly=calculator_input.active_installments_monthly,
        other_monthly_obligations=calculator_input.other_monthly_obligations,
        planning_mortgage=calculator_input.planning_mortgage,
        interest_rate=calculator_input.interest_rate,
        num_payments=calculator_input.num_payments
    )

    # Generate personalized content
    verdict = engine.generate_verdict_message(risk_level)
    personalized_message = engine.generate_personalized_message(
        risk_level, risk_factors, calculator_input.category, age_group
    )
    alternative = engine.generate_alternative_recommendation(
        risk_level,
        calculator_input.purchase_amount,
        monthly_payment,
        monthly_income,
        calculator_input.num_payments,
        total_interest
    )
    statistics = engine.generate_statistics(
        risk_level,
        calculator_input.category,
        age_group,
        calculator_input.active_installments_count
    )
    warnings = engine.generate_warnings(
        risk_level,
        calculator_input.interest_rate,
        calculator_input.category
    )

    # Generate tips
    tips = []
    if calculator_input.interest_rate == 0:
        tips.append("Even at 0% interest, track payment dates carefully to avoid late fees")
    if risk_level in [RiskLevel.GREEN, RiskLevel.YELLOW]:
        tips.append("Set up automatic payments to never miss a due date")
        tips.append("Keep a buffer of $500-$1000 in your account for emergencies")

    # Calculate hidden costs
    potential_late_fee = Decimal('35.00')  # Typical late fee
    potential_overdraft = Decimal('35.00')  # Typical overdraft fee
    hidden_cost_message = None

    if risk_level in [RiskLevel.ORANGE, RiskLevel.RED]:
        total_hidden_cost = potential_late_fee + potential_overdraft
        effective_interest_increase = (total_hidden_cost / calculator_input.purchase_amount * 100)
        hidden_cost_message = (
            f"One missed payment could cost ${float(total_hidden_cost):.2f} in fees, "
            f"turning a 0% installment into an effective {float(effective_interest_increase):.1f}% interest rate"
        )

    # Save calculation to database for analytics
    calculation_record = InstallmentCalculation(
        user_id=user_id,
        purchase_amount=calculator_input.purchase_amount,
        category=calculator_input.category,
        num_payments=calculator_input.num_payments,
        interest_rate=calculator_input.interest_rate,
        monthly_payment=monthly_payment,
        total_interest=total_interest,
        risk_level=risk_level,
        dti_ratio=dti_with_installment,
        payment_to_income_ratio=payment_to_income,
        remaining_balance=balance_after_payment,
        risk_factors=json.dumps([rf.dict() for rf in risk_factors]),
        user_proceeded=False  # Will be updated if user creates actual installment
    )
    db.add(calculation_record)

    # Update achievement tracking
    await update_achievement_calculations(db, user_id, risk_level)

    await db.commit()

    return InstallmentCalculatorOutput(
        risk_level=risk_level,
        risk_score=risk_score,
        verdict=verdict,
        monthly_payment=monthly_payment,
        total_interest=total_interest,
        total_cost=total_cost,
        first_payment_amount=monthly_payment,
        payment_schedule=payment_schedule,
        dti_ratio=dti_with_installment,
        payment_to_income_ratio=payment_to_income,
        remaining_monthly_funds=remaining_monthly,
        balance_after_first_payment=balance_after_payment,
        risk_factors=risk_factors,
        personalized_message=personalized_message,
        alternative_recommendation=alternative,
        warnings=warnings,
        tips=tips,
        statistics=statistics,
        potential_late_fee=potential_late_fee,
        potential_overdraft=potential_overdraft,
        hidden_cost_message=hidden_cost_message
    )


async def update_achievement_calculations(
    db: AsyncSession,
    user_id: UUID,
    risk_level: RiskLevel
):
    """Update user's achievement tracking for calculations"""
    result = await db.execute(
        select(InstallmentAchievement).where(
            InstallmentAchievement.user_id == user_id
        )
    )
    achievement = result.scalar_one_or_none()

    if not achievement:
        achievement = InstallmentAchievement(user_id=user_id)
        db.add(achievement)

    achievement.calculations_performed += 1
    achievement.last_calculation_date = datetime.utcnow()

    # Track declined calculations (user saw red/orange and hopefully won't proceed)
    if risk_level in [RiskLevel.RED, RiskLevel.ORANGE]:
        # We'll update calculations_declined when they don't create installment
        pass

    await db.commit()


# Additional service functions for installment management will go here
# (create_installment, get_user_installments, update_installment, etc.)
# These will be implemented in the next section along with routes
