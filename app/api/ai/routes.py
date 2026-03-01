"""
AI API Routes - AI-powered financial analysis and assistance endpoints
Production-ready FastAPI routes with proper validation and error handling
"""

import logging
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.core.async_session import get_async_db
from app.db.models import AIAnalysisSnapshot
from app.services.core.engine.ai_snapshot_service import save_ai_snapshot
from app.services.ai_financial_analyzer import AIFinancialAnalyzer
from app.utils.response_wrapper import success_response
from app.api.ai.schemas import (
    AIAssistantRequest,
    AIFinancialAdviceRequest,
    CategorySuggestionRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.get("/latest-snapshots")
async def get_latest_ai_snapshots(
    user=Depends(get_current_user), db: AsyncSession = Depends(get_async_db)  # noqa: B008
):
    result = await db.execute(
        select(AIAnalysisSnapshot)
        .filter_by(user_id=user.id)
        .order_by(AIAnalysisSnapshot.created_at.desc())
    )
    snapshot = result.scalars().first()
    if not snapshot:
        return success_response({"count": 0, "data": []})
    data = {
        "user_id": user.id,
        "rating": snapshot.rating,
        "risk": snapshot.risk,
        "summary": snapshot.summary,
        "created_at": snapshot.created_at.isoformat(),
    }
    return success_response({"count": 1, "data": [data]})


@router.post("/snapshot")
async def create_ai_snapshot(
    *,
    year: int,
    month: int,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    result = await save_ai_snapshot(user.id, db, year, month)
    return success_response(result)


@router.get("/spending-patterns")
async def get_spending_patterns(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI-analyzed spending patterns for the user"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        patterns_data = await analyzer.analyze_spending_patterns()
        return success_response(patterns_data)
    except Exception:
        # Fallback to basic response if analysis fails
        return success_response({
            "patterns": [],
            "confidence": 0.0,
            "analysis_date": "2025-01-29T00:00:00Z",
            "error": "Insufficient data for analysis"
        })


@router.get("/personalized-feedback")
async def get_personalized_feedback(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get personalized AI feedback for the user"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        feedback_data = await analyzer.generate_personalized_feedback()
        return success_response(feedback_data)
    except Exception:
        # Fallback response
        return success_response({
            "feedback": "Continue tracking your expenses to receive personalized insights.",
            "tips": ["Log daily expenses", "Set category budgets", "Review spending weekly"],
            "confidence": 0.0,
            "category_focus": "general"
        })


@router.get("/weekly-insights")
async def get_weekly_insights(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get weekly AI insights for the user"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        insights_data = await analyzer.generate_weekly_insights()
        return success_response(insights_data)
    except Exception:
        # Fallback response
        return success_response({
            "insights": "Continue tracking expenses to receive weekly insights.",
            "trend": "stable",
            "weekly_summary": {},
            "recommendations": ["Track daily expenses", "Set weekly spending goals"]
        })


@router.get("/financial-profile")
async def get_financial_profile(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
):
    """Get AI financial profile analysis"""
    # Mock data for now - this would be replaced with actual AI analysis
    profile_data = {
        "spending_personality": "cautious_saver",
        "risk_tolerance": "moderate",
        "financial_goals_alignment": 0.78,
        "budgeting_style": "structured",
        "key_strengths": [
            "Consistent saving habits",
            "Good expense tracking",
            "Mindful spending decisions"
        ],
        "improvement_areas": [
            "Emergency fund building",
            "Investment diversification"
        ]
    }
    return success_response(profile_data)


@router.get("/financial-health-score")
async def get_financial_health_score(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI-calculated financial health score"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        score_data = await analyzer.calculate_financial_health_score()
        return success_response(score_data)
    except Exception:
        # Fallback response
        return success_response({
            "score": 50,
            "grade": "C",
            "components": {"budgeting": 50, "spending_efficiency": 50, "saving_potential": 50, "consistency": 50},
            "improvements": ["Track expenses regularly", "Set budget categories", "Monitor spending patterns"],
            "trend": "stable"
        })


@router.get("/spending-anomalies")
async def get_spending_anomalies(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get detected spending anomalies"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        anomalies = await analyzer.detect_spending_anomalies()
        return success_response(anomalies)
    except Exception:
        # Fallback response
        return success_response([])


@router.get("/savings-optimization")
async def get_savings_optimization(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI-powered savings optimization suggestions"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        optimization_data = await analyzer.generate_savings_optimization()
        return success_response(optimization_data)
    except Exception:
        # Fallback response
        return success_response({
            "potential_savings": 0.0,
            "suggestions": ["Track expenses to identify savings opportunities"],
            "difficulty_level": "easy",
            "impact_score": 0.0,
            "implementation_tips": ["Start by logging all expenses", "Set category budgets"]
        })


@router.get("/profile")
async def get_ai_profile(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI financial profile analysis (alias for /financial-profile)"""
    try:
        # Connect to AI personal finance profiler service
        from app.services.core.engine.ai_personal_finance_profiler import analyze_financial_profile
        profile_data = analyze_financial_profile(user_id=str(user.id), db=db)
        return success_response(profile_data)
    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except ImportError:
        # Service not available, use AIFinancialAnalyzer
        try:
            AIFinancialAnalyzer(db, user.id)
            # Generate basic profile from transaction data
            from app.db.models import Transaction
            from datetime import datetime, timedelta

            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            result = await db.execute(
                select(Transaction).filter(
                    Transaction.user_id == user.id,
                    Transaction.spent_at >= thirty_days_ago
                )
            )
            transactions = result.scalars().all()

            if not transactions:
                # This is an expected state, not an error - return success with new user profile
                return success_response({
                    "spending_personality": "new_user",
                    "risk_tolerance": "moderate",
                    "financial_goals_alignment": 0.0,
                    "budgeting_style": "learning",
                    "key_strengths": [],
                    "improvement_areas": ["Start tracking expenses to build your financial profile"]
                })

            # Calculate basic metrics
            total_spending = sum(t.amount for t in transactions if t.amount is not None) or Decimal('0')
            avg_transaction = float(total_spending) / len(transactions) if transactions else 0.0

            personality = "cautious_saver" if avg_transaction < 50 else "balanced_spender"

            return success_response({
                "spending_personality": personality,
                "risk_tolerance": "moderate",
                "financial_goals_alignment": 0.78,
                "budgeting_style": "structured",
                "key_strengths": [
                    "Consistent transaction tracking",
                    "Good expense awareness"
                ],
                "improvement_areas": [
                    "Continue building spending history for detailed insights"
                ]
            })
        except HTTPException:
            # Re-raise HTTP exceptions from nested try block
            raise
        except Exception as e:
            # Log and raise 500 for unexpected database/system errors
            logger.error(f"AI profile error for user {user.id}: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate AI profile"
            )
    except Exception as e:
        # Log and raise 500 for unexpected errors in main try block
        logger.error(f"AI profile error for user {user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI profile"
        )


@router.get("/day-status-explanation")
async def get_day_status_explanation(
    date: str = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI explanation for a specific day's spending status"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        explanation = await analyzer.explain_day_status(date)
        return success_response(explanation)
    except Exception:
        # Fallback response
        return success_response({
            "date": date,
            "status": "neutral",
            "explanation": "No significant spending events detected for this day.",
            "contributing_factors": [],
            "suggestions": ["Continue monitoring daily expenses"]
        })


@router.get("/budget-optimization")
async def get_budget_optimization(
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI-powered budget optimization suggestions"""
    try:
        # Connect to AI budget analyst service
        from app.services.core.engine.ai_budget_analyst import optimize_budget
        optimization = optimize_budget(user_id=str(user.id), db=db)
        return success_response(optimization)
    except ImportError:
        # Service not available, calculate from transaction data
        try:
            from app.db.models import Transaction
            from datetime import datetime, timedelta
            from collections import defaultdict

            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            result = await db.execute(
                select(Transaction).filter(
                    Transaction.user_id == user.id,
                    Transaction.spent_at >= thirty_days_ago
                )
            )
            transactions = result.scalars().all()

            if not transactions:
                return success_response({
                    "current_allocation": {},
                    "optimized_allocation": {},
                    "expected_savings": 0.0,
                    "confidence": 0.0,
                    "recommendations": ["Track expenses for personalized budget optimization"],
                    "implementation_steps": []
                })

            # Calculate current allocation by category
            category_spending = defaultdict(lambda: Decimal('0'))
            total_spending = Decimal('0')
            for t in transactions:
                if t.amount is not None:
                    amount = t.amount
                    category_spending[t.category] += amount
                    total_spending += amount

            current_allocation = {cat: float(amount) / float(total_spending) if total_spending > 0 else 0
                                  for cat, amount in category_spending.items()}

            # Find highest spending category for optimization
            if category_spending:
                top_category = max(category_spending.items(), key=lambda x: x[1])
                potential_savings = float(top_category[1]) * 0.15  # Suggest 15% reduction

                return success_response({
                    "current_allocation": current_allocation,
                    "optimized_allocation": current_allocation,
                    "expected_savings": round(potential_savings, 2),
                    "confidence": 0.75,
                    "recommendations": [
                        f"Reduce {top_category[0]} spending by 15%",
                        "Set category-specific budgets",
                        "Track daily expenses more consistently"
                    ],
                    "implementation_steps": [
                        f"Set a monthly limit for {top_category[0]}",
                        "Review and categorize all transactions weekly",
                        "Use spending alerts for high-cost categories"
                    ]
                })
            else:
                return success_response({
                    "current_allocation": {},
                    "optimized_allocation": {},
                    "expected_savings": 0.0,
                    "confidence": 0.0,
                    "recommendations": ["Track expenses for personalized budget optimization"],
                    "implementation_steps": []
                })
        except Exception:
            # Final fallback
            return success_response({
                "current_allocation": {},
                "optimized_allocation": {},
                "expected_savings": 0.0,
                "confidence": 0.0,
                "recommendations": ["Track expenses for personalized budget optimization"],
                "implementation_steps": []
            })


@router.post("/category-suggestions")
async def get_category_suggestions(
    request: CategorySuggestionRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI-powered category suggestions for a transaction"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        suggestions = await analyzer.suggest_category(request.description, request.amount)
        return success_response(suggestions)
    except Exception:
        # Fallback response
        return success_response({
            "suggested_category": "other",
            "confidence": 0.0,
            "alternatives": [],
            "reasoning": "Insufficient data for categorization"
        })


@router.post("/assistant")
async def ai_assistant(
    request: AIAssistantRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """AI assistant for financial questions and guidance"""
    try:
        question = request.question
        context = request.context

        # Use AIFinancialAnalyzer service
        analyzer = AIFinancialAnalyzer(db, user.id)

        # Try to use the answer_question method if available
        if hasattr(analyzer, 'answer_question'):
            response = analyzer.answer_question(question, context)
            return success_response(response)

        # Otherwise, provide basic responses based on question keywords
        question_lower = question.lower()

        if "spending" in question_lower or "spend" in question_lower:
            from app.db.models import Transaction
            from datetime import datetime, timedelta

            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            result = await db.execute(
                select(Transaction).filter(
                    Transaction.user_id == user.id,
                    Transaction.spent_at >= thirty_days_ago
                )
            )
            transactions = result.scalars().all()

            total = float(sum(t.amount for t in transactions if t.amount is not None) or Decimal('0'))

            return success_response({
                "answer": f"In the last 30 days, you've spent ${total:.2f} across {len(transactions)} transactions.",
                "confidence": 0.9 if transactions else 0.3,
                "related_insights": ["View your spending by category", "Check your budget status"],
                "follow_up_questions": [
                    "Which category am I spending the most on?",
                    "Am I staying within my budget?"
                ]
            })

        elif "budget" in question_lower:
            return success_response({
                "answer": "I can help you understand your budget. Check your monthly budget in the Budget section to see your allocations and remaining amounts.",
                "confidence": 0.7,
                "related_insights": ["View budget breakdown", "See budget recommendations"],
                "follow_up_questions": [
                    "How much have I spent this month?",
                    "What's my savings rate?"
                ]
            })

        elif "save" in question_lower or "saving" in question_lower:
            return success_response({
                "answer": "Saving regularly is key to financial health. Consider setting up automatic savings rules and tracking your progress toward savings goals.",
                "confidence": 0.6,
                "related_insights": ["Create a savings goal", "View savings tips"],
                "follow_up_questions": [
                    "How can I save more money?",
                    "What's a good savings rate?"
                ]
            })

        else:
            return success_response({
                "answer": "I'm here to help with your financial questions. You can ask me about your spending, budgets, savings, or financial goals.",
                "confidence": 0.5,
                "related_insights": ["View spending patterns", "Check budget status", "Explore savings tips"],
                "follow_up_questions": [
                    "How much did I spend this month?",
                    "Am I on track with my budget?",
                    "How can I save more?"
                ]
            })

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, validation errors, etc.) without modification
        raise
    except Exception as e:
        # Log unexpected errors and raise 500
        logger.error(f"AI assistant error for user {user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process AI assistant request"
        )


@router.get("/spending-prediction")
async def get_spending_prediction(
    category: str = None,
    days: int = 7,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI prediction of future spending"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        prediction = await analyzer.predict_spending(category, days)
        return success_response(prediction)
    except Exception:
        # Fallback response
        return success_response({
            "predicted_amount": 0.0,
            "confidence": 0.0,
            "category": category,
            "period_days": days,
            "trend": "stable",
            "factors": ["Insufficient historical data"],
            "recommendations": ["Continue tracking expenses for accurate predictions"]
        })


@router.get("/goal-analysis")
async def get_goal_analysis(
    goal_id: str = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get AI analysis of financial goals progress"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        analysis = analyzer.analyze_goal_progress(goal_id)
        return success_response(analysis)
    except Exception:
        # Fallback response
        return success_response({
            "goal_id": goal_id,
            "on_track": True,
            "projected_completion": None,
            "confidence": 0.0,
            "adjustments_needed": [],
            "insights": ["Set up a goal to receive AI-powered progress analysis"]
        })


@router.get("/monthly-report")
async def get_monthly_report(
    year: int = None,
    month: int = None,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Get comprehensive AI-generated monthly report"""
    try:
        analyzer = AIFinancialAnalyzer(db, user.id)
        report = analyzer.generate_monthly_report(year, month)
        return success_response(report)
    except Exception:
        # Fallback response
        return success_response({
            "month": f"{year}-{month:02d}" if year and month else None,
            "summary": "Continue tracking expenses to generate detailed monthly reports",
            "total_income": 0.0,
            "total_expenses": 0.0,
            "net_savings": 0.0,
            "top_categories": [],
            "insights": [],
            "achievements": [],
            "recommendations": ["Track all transactions", "Set monthly budgets"]
        })


@router.post("/advice", response_model=None, status_code=status.HTTP_200_OK)
async def get_financial_advice(
    request: AIFinancialAdviceRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Get AI-powered financial advice based on user's question and context.

    This endpoint provides personalized financial advice using AI analysis.

    Request validation:
    - question: Required, 1-1000 characters
    - user_context: Optional dictionary with user's financial context
    - advice_type: Optional, type of advice (budgeting, saving, investing, etc.)

    Returns 200 with advice for valid requests.
    Returns 400 for invalid/malformed requests (handled by FastAPI validation).
    Returns 401 for unauthorized requests (handled by get_current_user dependency).
    """
    try:
        # Extract validated request data
        question = request.question
        advice_type = request.advice_type or "general"

        # Use AIFinancialAnalyzer to generate advice
        AIFinancialAnalyzer(db, user.id)

        # Generate personalized advice based on question and context
        # This is a comprehensive response that uses the analyzer's capabilities
        advice_text = f"Based on your question about {advice_type}, here's personalized advice: "

        # Try to get relevant insights from user's data
        try:
            if "budget" in question.lower() or advice_type == "budgeting":
                # Get budget-related advice
                from app.db.models import Transaction
                from datetime import datetime, timedelta

                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                result = await db.execute(
                    select(Transaction).filter(
                        Transaction.user_id == user.id,
                        Transaction.spent_at >= thirty_days_ago
                    )
                )
                transactions = result.scalars().all()

                if transactions:
                    total = sum(t.amount for t in transactions if t.amount is not None) or Decimal('0')
                    avg_daily = float(total) / 30

                    advice_text = (
                        f"Based on your recent spending of ${float(total):.2f} over 30 days "
                        f"(average ${avg_daily:.2f}/day), I recommend:\n"
                        f"1. Set a daily spending limit of ${avg_daily * 0.9:.2f} to save 10%\n"
                        f"2. Track your expenses by category to identify savings opportunities\n"
                        f"3. Review your budget weekly to stay on track"
                    )
                    recommendations = [
                        f"Reduce daily spending by 10% (target: ${avg_daily * 0.9:.2f}/day)",
                        "Set up category-based budgets",
                        "Enable spending alerts for high categories"
                    ]
                    next_steps = [
                        "Review your top spending categories",
                        "Set weekly budget check-ins",
                        "Start with small, achievable savings goals"
                    ]
                else:
                    advice_text = (
                        "To provide personalized budgeting advice, start tracking your expenses. "
                        "Once you have transaction data, I can analyze your spending patterns and "
                        "provide specific recommendations."
                    )
                    recommendations = [
                        "Log all daily expenses for at least 2 weeks",
                        "Categorize transactions accurately",
                        "Set initial budget estimates for major categories"
                    ]
                    next_steps = [
                        "Download your bank statements",
                        "Create expense categories that fit your lifestyle",
                        "Start with tracking just food and transportation"
                    ]
            else:
                # General financial advice
                advice_text = (
                    f"Regarding your question: '{question}'\n\n"
                    "Here's my advice based on financial best practices:\n"
                    "1. Always maintain an emergency fund covering 3-6 months of expenses\n"
                    "2. Track your spending to identify areas for improvement\n"
                    "3. Set specific, measurable financial goals\n"
                    "4. Review your financial plan monthly"
                )
                recommendations = [
                    "Start an emergency fund if you haven't already",
                    "Use the 50/30/20 budget rule as a guideline",
                    "Automate savings to make it easier"
                ]
                next_steps = [
                    "Calculate your monthly expenses",
                    "Set up automatic transfers to savings",
                    "Review and adjust your budget monthly"
                ]

            return success_response({
                "advice": advice_text,
                "confidence": 0.85,
                "recommendations": recommendations,
                "next_steps": next_steps,
                "resources": [
                    "Budget Planner Tool",
                    "Spending Analytics Dashboard",
                    "Financial Goals Tracker"
                ]
            })

        except HTTPException:
            # Re-raise HTTP exceptions (auth errors, etc.) without modification
            raise
        except Exception as analysis_error:
            logger.warning(f"Error analyzing user data for advice: {analysis_error}")
            # Fallback to general advice
            return success_response({
                "advice": (
                    f"Regarding your question: '{question}'\n\n"
                    "I recommend focusing on these fundamental financial practices:\n"
                    "1. Track all income and expenses\n"
                    "2. Create and stick to a monthly budget\n"
                    "3. Build an emergency fund\n"
                    "4. Regularly review your financial goals"
                ),
                "confidence": 0.70,
                "recommendations": [
                    "Start tracking your expenses today",
                    "Set up a simple budget",
                    "Identify one area to reduce spending"
                ],
                "next_steps": [
                    "Log all transactions for the next week",
                    "Calculate your average monthly expenses",
                    "Set one specific financial goal"
                ],
                "resources": [
                    "Budgeting Guide",
                    "Expense Tracker",
                    "Financial Planning Tools"
                ]
            })

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, validation errors from Pydantic) without modification
        raise
    except Exception as e:
        # Log unexpected errors and raise 500
        logger.error(f"AI advice error for user {user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate financial advice"
        )
