"""
MODULE 5: Budgeting Goals - Enhanced API Routes
Complete CRUD + Progress Tracking + Statistics
"""
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func, select

from app.api.dependencies import get_current_user, require_premium_user
from app.core.session import get_db
from app.api.base_crud import CRUDHelper
from app.db.models import Goal
from app.utils.response_wrapper import success_response
from app.services.notification_integration import get_notification_integration
from app.services.smart_goal_advisor import get_smart_goal_advisor
from app.services.goal_budget_integration import get_goal_budget_integration

router = APIRouter(prefix="/goals", tags=["goals"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class GoalIn(BaseModel):
    """Schema for creating a new goal"""
    title: str = Field(..., min_length=1, max_length=200, description="Goal title")
    description: Optional[str] = Field(None, description="Detailed description of the goal")
    category: Optional[str] = Field(None, max_length=50, description="Goal category")
    target_amount: float = Field(..., gt=0, description="Target amount to save")
    saved_amount: Optional[float] = Field(0, ge=0, description="Amount already saved")
    monthly_contribution: Optional[float] = Field(None, ge=0, description="Recommended monthly contribution")
    target_date: Optional[date] = Field(None, description="Target completion date")
    priority: Optional[str] = Field("medium", description="Priority level: high, medium, low")

    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in ['high', 'medium', 'low']:
            raise ValueError('Priority must be high, medium, or low')
        return v

    @validator('category')
    def validate_category(cls, v):
        valid_categories = ['Savings', 'Travel', 'Emergency', 'Technology', 'Education',
                           'Health', 'Home', 'Vehicle', 'Investment', 'Other']
        if v and v not in valid_categories:
            return 'Other'  # Default to Other if invalid
        return v


class GoalUpdate(BaseModel):
    """Schema for updating an existing goal"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    target_amount: Optional[float] = Field(None, gt=0)
    saved_amount: Optional[float] = Field(None, ge=0)
    monthly_contribution: Optional[float] = Field(None, ge=0)
    target_date: Optional[date] = None
    priority: Optional[str] = None
    status: Optional[str] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in ['high', 'medium', 'low']:
            raise ValueError('Priority must be high, medium, or low')
        return v

    @validator('status')
    def validate_status(cls, v):
        if v and v not in ['active', 'completed', 'paused', 'cancelled']:
            raise ValueError('Status must be active, completed, paused, or cancelled')
        return v


class GoalOut(BaseModel):
    """Schema for goal output"""
    id: UUID
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    target_amount: float
    saved_amount: float
    current_amount: Optional[float] = None  # Alias for mobile compatibility
    monthly_contribution: Optional[float] = None
    status: str
    progress: float
    target_date: Optional[date] = None
    deadline: Optional[str] = None  # ISO string for mobile compatibility
    created_at: datetime
    last_updated: datetime
    completed_at: Optional[datetime] = None
    priority: Optional[str] = None
    remaining_amount: Optional[float] = None
    is_completed: Optional[bool] = None
    is_overdue: Optional[bool] = None

    class Config:
        from_attributes = True


class GoalStatistics(BaseModel):
    """Statistics about user's goals"""
    total_goals: int
    active_goals: int
    completed_goals: int
    paused_goals: int
    completion_rate: float
    average_progress: float
    total_target_amount: float
    total_saved_amount: float
    overdue_goals: int
    due_soon: int


class AddSavingsRequest(BaseModel):
    """Request to add savings to a goal"""
    amount: float = Field(..., gt=0, description="Amount to add to savings")


class AutoTransferRequest(BaseModel):
    """Request to auto-transfer funds to a goal"""
    amount: float = Field(..., gt=0, description="Amount to transfer")


# ============================================================================
# Helper Functions
# ============================================================================

def goal_to_dict(goal: Goal) -> dict:
    """Convert Goal model to dictionary with computed fields"""
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "category": goal.category,
        "target_amount": float(goal.target_amount),
        "saved_amount": float(goal.saved_amount),
        "current_amount": float(goal.saved_amount),  # Alias for mobile
        "monthly_contribution": float(goal.monthly_contribution) if goal.monthly_contribution else None,
        "status": goal.status,
        "progress": float(goal.progress),
        "target_date": goal.target_date,
        "deadline": goal.target_date.isoformat() if goal.target_date else None,  # For mobile
        "created_at": goal.created_at,
        "last_updated": goal.last_updated,
        "completed_at": goal.completed_at,
        "priority": goal.priority,
        "remaining_amount": float(goal.remaining_amount),
        "is_completed": goal.is_completed,
        "is_overdue": goal.is_overdue,
    }


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.post("/", response_model=GoalOut)
def create_goal(
    data: GoalIn,
    user=Depends(require_premium_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Create a new budgeting goal"""
    goal = Goal(
        user_id=user.id,
        title=data.title,
        description=data.description,
        category=data.category,
        target_amount=data.target_amount,
        saved_amount=data.saved_amount or 0,
        monthly_contribution=data.monthly_contribution,
        target_date=data.target_date,
        priority=data.priority or 'medium',
        status='active',
    )

    # Calculate initial progress
    goal.update_progress()

    db.add(goal)
    db.commit()
    db.refresh(goal)

    # Send notification about goal creation
    try:
        notifier = get_notification_integration(db)
        notifier.notify_goal_created(
            user_id=user.id,
            goal_title=goal.title,
            target_amount=float(goal.target_amount)
        )
    except Exception as e:
        # Don't fail goal creation if notification fails
        import logging
        logging.error(f"Failed to send goal creation notification: {e}")

    return success_response(goal_to_dict(goal))


@router.get("/", response_model=List[GoalOut])
def list_goals(
    status: Optional[str] = Query(None, description="Filter by status: active, completed, paused"),
    category: Optional[str] = Query(None, description="Filter by category"),
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """List all goals for the current user with optional filters"""
    query = db.query(Goal).filter(Goal.user_id == user.id)

    if status:
        query = query.filter(Goal.status == status)
    if category:
        query = query.filter(Goal.category == category)

    goals = query.order_by(desc(Goal.created_at)).all()

    return success_response([goal_to_dict(g) for g in goals])


@router.get("/statistics", response_model=GoalStatistics)
def get_statistics(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get comprehensive goal statistics for the user"""

    # Count goals by status
    total_goals = db.query(func.count(Goal.id)).filter(Goal.user_id == user.id).scalar() or 0
    active_goals = db.query(func.count(Goal.id)).filter(
        and_(Goal.user_id == user.id, Goal.status == 'active')
    ).scalar() or 0
    completed_goals = db.query(func.count(Goal.id)).filter(
        and_(Goal.user_id == user.id, Goal.status == 'completed')
    ).scalar() or 0
    paused_goals = db.query(func.count(Goal.id)).filter(
        and_(Goal.user_id == user.id, Goal.status == 'paused')
    ).scalar() or 0

    # Calculate averages
    avg_progress = db.query(func.avg(Goal.progress)).filter(
        and_(Goal.user_id == user.id, Goal.status == 'active')
    ).scalar() or 0.0

    # Calculate totals
    total_target = db.query(func.sum(Goal.target_amount)).filter(
        and_(Goal.user_id == user.id, Goal.status == 'active')
    ).scalar() or 0.0
    total_saved = db.query(func.sum(Goal.saved_amount)).filter(
        and_(Goal.user_id == user.id, Goal.status == 'active')
    ).scalar() or 0.0

    # Count overdue and due soon
    from datetime import date, timedelta
    today = date.today()
    soon_date = today + timedelta(days=7)

    overdue_count = db.query(func.count(Goal.id)).filter(
        and_(
            Goal.user_id == user.id,
            Goal.status == 'active',
            Goal.target_date < today,
            Goal.target_date.isnot(None)
        )
    ).scalar() or 0

    due_soon_count = db.query(func.count(Goal.id)).filter(
        and_(
            Goal.user_id == user.id,
            Goal.status == 'active',
            Goal.target_date <= soon_date,
            Goal.target_date >= today,
            Goal.target_date.isnot(None)
        )
    ).scalar() or 0

    completion_rate = (completed_goals / total_goals * 100) if total_goals > 0 else 0.0

    return success_response({
        "total_goals": total_goals,
        "active_goals": active_goals,
        "completed_goals": completed_goals,
        "paused_goals": paused_goals,
        "completion_rate": round(completion_rate, 2),
        "average_progress": round(float(avg_progress), 2),
        "total_target_amount": float(total_target),
        "total_saved_amount": float(total_saved),
        "overdue_goals": overdue_count,
        "due_soon": due_soon_count,
    })


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get a specific goal by ID"""
    goal = CRUDHelper.get_user_resource_or_404(db, Goal, goal_id, user.id, "Goal not found")
    return success_response(goal_to_dict(goal))


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: UUID,
    data: GoalUpdate,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Update an existing goal"""
    goal = CRUDHelper.get_user_resource_or_404(db, Goal, goal_id, user.id, "Goal not found")

    # Update fields if provided
    if data.title is not None:
        goal.title = data.title
    if data.description is not None:
        goal.description = data.description
    if data.category is not None:
        goal.category = data.category
    if data.target_amount is not None:
        goal.target_amount = data.target_amount
    if data.saved_amount is not None:
        goal.saved_amount = data.saved_amount
    if data.monthly_contribution is not None:
        goal.monthly_contribution = data.monthly_contribution
    if data.target_date is not None:
        goal.target_date = data.target_date
    if data.priority is not None:
        goal.priority = data.priority
    if data.status is not None:
        goal.status = data.status

    # Recalculate progress
    goal.update_progress()

    db.commit()
    db.refresh(goal)

    return success_response(goal_to_dict(goal))


@router.delete("/{goal_id}")
def delete_goal(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Delete a goal"""
    CRUDHelper.delete_user_resource(db, Goal, goal_id, user.id, "Goal not found")
    return success_response({"status": "deleted", "id": str(goal_id)})


# ============================================================================
# Progress Tracking Endpoints
# ============================================================================

@router.post("/{goal_id}/add_savings", response_model=GoalOut)
def add_savings_to_goal(
    goal_id: UUID,
    data: AddSavingsRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Add savings to a goal and update progress"""
    goal = CRUDHelper.get_user_resource_or_404(db, Goal, goal_id, user.id, "Goal not found")

    # Store old progress to check for milestones
    old_progress = float(goal.progress)

    # Add savings
    goal.add_savings(Decimal(str(data.amount)))

    db.commit()
    db.refresh(goal)

    # Send notifications based on progress
    try:
        notifier = get_notification_integration(db)
        new_progress = float(goal.progress)

        # Check if goal was just completed
        if goal.status == 'completed' and old_progress < 100:
            # Calculate days taken if created_at is available
            days_taken = None
            if goal.created_at and goal.completed_at:
                days_taken = (goal.completed_at - goal.created_at).days

            notifier.notify_goal_completed(
                user_id=user.id,
                goal_title=goal.title,
                final_amount=float(goal.saved_amount),
                days_taken=days_taken
            )
        else:
            # Send progress milestone notification
            notifier.notify_goal_progress(
                user_id=user.id,
                goal_title=goal.title,
                progress=new_progress,
                saved_amount=float(goal.saved_amount),
                target_amount=float(goal.target_amount)
            )
    except Exception as e:
        # Don't fail savings addition if notification fails
        import logging
        logging.error(f"Failed to send goal progress notification: {e}")

    return success_response(goal_to_dict(goal))


@router.post("/{goal_id}/complete", response_model=GoalOut)
def mark_goal_completed(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Mark a goal as completed"""
    goal = CRUDHelper.get_user_resource_or_404(db, Goal, goal_id, user.id, "Goal not found")

    goal.status = 'completed'
    goal.progress = 100
    goal.completed_at = datetime.utcnow()
    goal.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(goal)

    # Send completion notification
    try:
        notifier = get_notification_integration(db)
        days_taken = None
        if goal.created_at and goal.completed_at:
            days_taken = (goal.completed_at - goal.created_at).days

        notifier.notify_goal_completed(
            user_id=user.id,
            goal_title=goal.title,
            final_amount=float(goal.saved_amount),
            days_taken=days_taken
        )
    except Exception as e:
        # Don't fail completion if notification fails
        import logging
        logging.error(f"Failed to send goal completion notification: {e}")

    return success_response(goal_to_dict(goal))


@router.post("/{goal_id}/pause", response_model=GoalOut)
def pause_goal(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Pause an active goal"""
    goal = CRUDHelper.get_user_resource_or_404(db, Goal, goal_id, user.id, "Goal not found")

    goal.status = 'paused'
    goal.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(goal)

    return success_response(goal_to_dict(goal))


@router.post("/{goal_id}/resume", response_model=GoalOut)
def resume_goal(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Resume a paused goal"""
    goal = CRUDHelper.get_user_resource_or_404(db, Goal, goal_id, user.id, "Goal not found")

    if goal.status != 'paused':
        raise HTTPException(status_code=400, detail="Only paused goals can be resumed")

    goal.status = 'active'
    goal.last_updated = datetime.utcnow()

    db.commit()
    db.refresh(goal)

    return success_response(goal_to_dict(goal))


# ============================================================================
# Goal Suggestions
# ============================================================================

@router.get("/income_based_suggestions")
def get_income_based_suggestions(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Get goal suggestions based on user's income level (Legacy - use /smart_recommendations instead)"""
    monthly_income = user.monthly_income or 3000.0

    suggestions = []

    # Emergency fund - 6 months of expenses
    suggestions.append({
        "type": "emergency_fund",
        "title": "Build Emergency Fund",
        "category": "Emergency",
        "target_amount": monthly_income * 6,
        "monthly_contribution": monthly_income * 0.10,
        "priority": "high",
        "description": f"Save ${int(monthly_income * 6)} for 6 months of expenses"
    })

    # Monthly savings - 20% rule
    suggestions.append({
        "type": "savings",
        "title": "Monthly Savings Goal",
        "category": "Savings",
        "target_amount": monthly_income * 0.20,
        "monthly_contribution": monthly_income * 0.20,
        "priority": "high",
        "description": "Save 20% of your monthly income"
    })

    # Vacation fund (for higher income)
    if monthly_income > 2000:
        suggestions.append({
            "type": "vacation",
            "title": "Vacation Fund",
            "category": "Travel",
            "target_amount": monthly_income * 2,
            "monthly_contribution": monthly_income * 0.05,
            "priority": "medium",
            "description": "Save for a well-deserved vacation"
        })

    # Technology upgrade
    if monthly_income > 3000:
        suggestions.append({
            "type": "technology",
            "title": "Technology Upgrade",
            "category": "Technology",
            "target_amount": 1500,
            "monthly_contribution": monthly_income * 0.03,
            "priority": "low",
            "description": "Save for new laptop, phone, or other tech"
        })

    return success_response({
        "suggestions": suggestions,
        "monthly_income": float(monthly_income),
        "recommended_savings_rate": 0.20
    })


# ============================================================================
# AI-Powered Smart Goal Recommendations
# ============================================================================

@router.get("/smart_recommendations")
def get_smart_recommendations(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get AI-powered personalized goal recommendations based on:
    - Income level
    - Spending patterns
    - Existing goals
    - Historical behavior
    """
    try:
        advisor = get_smart_goal_advisor(db)
        recommendations = advisor.generate_personalized_recommendations(user.id)

        return success_response({
            "recommendations": recommendations,
            "count": len(recommendations),
            "generated_at": datetime.utcnow().isoformat()
        })
    except Exception as e:
        import logging
        logging.error(f"Error generating smart recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{goal_id}/health")
def analyze_goal_health(
    goal_id: UUID,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Analyze the health of a goal and provide AI-powered insights:
    - Health score (0-100)
    - On-track status
    - Predicted completion date
    - Actionable recommendations
    """
    try:
        advisor = get_smart_goal_advisor(db)
        health_analysis = advisor.analyze_goal_health(goal_id, user.id)

        if "error" in health_analysis:
            raise HTTPException(status_code=404, detail=health_analysis["error"])

        return success_response(health_analysis)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error analyzing goal health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adjustments/suggestions")
def suggest_goal_adjustments(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get AI-powered suggestions for adjusting existing goals based on:
    - Current goal progress
    - Recent spending patterns
    - Available funds
    """
    try:
        advisor = get_smart_goal_advisor(db)
        suggestions = advisor.suggest_goal_adjustments(user.id)

        return success_response({
            "adjustments": suggestions,
            "count": len(suggestions),
            "generated_at": datetime.utcnow().isoformat()
        })
    except Exception as e:
        import logging
        logging.error(f"Error generating goal adjustment suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities/detect")
def detect_goal_opportunities(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Detect opportunities for new goals based on spending patterns:
    - Recurring large expenses
    - Consistent underspending in categories
    - Surplus funds that could be saved
    """
    try:
        advisor = get_smart_goal_advisor(db)
        opportunities = advisor.detect_goal_opportunities(user.id)

        return success_response({
            "opportunities": opportunities,
            "count": len(opportunities),
            "generated_at": datetime.utcnow().isoformat()
        })
    except Exception as e:
        import logging
        logging.error(f"Error detecting goal opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Budget-Goals Integration
# ============================================================================

@router.get("/budget/allocate")
def allocate_budget_for_goals(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Automatically allocate budget for active goals from monthly income
    """
    try:
        integration = get_goal_budget_integration(db)
        allocation = integration.allocate_budget_for_goals(user.id, month, year)

        return success_response(allocation)
    except Exception as e:
        import logging
        logging.error(f"Error allocating budget for goals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/progress")
def track_goal_progress_from_budget(
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Track goal progress based on budget allocations and actual spending
    """
    try:
        integration = get_goal_budget_integration(db)
        progress = integration.track_goal_progress_from_budget(user.id, month, year)

        return success_response(progress)
    except Exception as e:
        import logging
        logging.error(f"Error tracking goal progress from budget: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/adjustment_suggestions")
def suggest_budget_adjustments(
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Get suggestions for budget adjustments to better support goals
    """
    try:
        integration = get_goal_budget_integration(db)
        suggestions = integration.suggest_budget_adjustments_for_goals(user.id)

        return success_response({
            "suggestions": suggestions,
            "count": len(suggestions)
        })
    except Exception as e:
        import logging
        logging.error(f"Error suggesting budget adjustments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{goal_id}/auto_transfer")
def auto_transfer_to_goal(
    goal_id: UUID,
    data: AutoTransferRequest,
    user=Depends(get_current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """
    Automatically create a savings transaction for a goal
    """
    try:
        from decimal import Decimal
        integration = get_goal_budget_integration(db)
        result = integration.auto_transfer_to_savings_goal(user.id, goal_id, Decimal(str(data.amount)))

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return success_response(result)
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error auto-transferring to goal: {e}")
        raise HTTPException(status_code=500, detail=str(e))
