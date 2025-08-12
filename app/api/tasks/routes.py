"""
Task management API routes for MITA financial platform.
Provides endpoints for task status tracking and management.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.tasks.schemas import (
    TaskResponse,
    TaskSubmissionResponse,
    NotificationRequest,
    DataExportRequest,
    AIAnalysisRequest,
    BudgetRedistributionRequest,
    SystemStatsResponse,
    BatchTaskResponse,
    TaskStatusEnum
)
from app.core.session import get_db
from app.services.task_manager import task_manager
from app.utils.response_wrapper import success_response, error_response
from app.core.logger import get_logger
from app.core.feature_flags import is_feature_enabled

logger = get_logger(__name__)

current_user_dep = Depends(get_current_user)  # noqa: B008
db_dep = Depends(get_db)  # noqa: B008

router = APIRouter(prefix="/tasks", tags=["tasks"])


def require_admin_access(user, feature_flag: str = "admin_endpoints_enabled"):
    """
    Check if user has admin access and feature is enabled.
    
    Args:
        user: Current authenticated user
        feature_flag: Feature flag to check for admin endpoints
    
    Raises:
        HTTPException: If user is not admin or feature is disabled
    """
    # Check if admin endpoints are enabled via feature flag
    if not is_feature_enabled(feature_flag, getattr(user, 'id', None), default=True):
        raise HTTPException(
            status_code=403, 
            detail="Admin endpoints are currently disabled"
        )
    
    # Check if user has admin role
    if not hasattr(user, 'is_admin') or not user.is_admin:
        raise HTTPException(
            status_code=403, 
            detail="Admin access required for this operation"
        )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(
    task_id: str,
    user=current_user_dep
):
    """
    Get the status of a specific task.
    
    Args:
        task_id: The task ID to check status for
        user: Current authenticated user
    
    Returns:
        TaskResponse with current status and results
    """
    try:
        task_info = task_manager.get_task_status(task_id)
        
        if not task_info:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        # Convert TaskInfo to TaskResponse
        return success_response(TaskResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            progress=task_info.progress,
            result=task_info.result,
            error=task_info.error,
            created_at=task_info.created_at,
            started_at=task_info.started_at,
            completed_at=task_info.completed_at,
            estimated_completion=task_info.estimated_completion
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    user=current_user_dep
):
    """
    Cancel a queued or running task.
    
    Args:
        task_id: The task ID to cancel
        user: Current authenticated user
    
    Returns:
        Success response if cancelled
    """
    try:
        success = task_manager.cancel_task(task_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} could not be cancelled (may already be completed or not exist)"
            )
        
        return success_response({
            'task_id': task_id,
            'status': 'cancelled',
            'message': 'Task successfully cancelled'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.post("/{task_id}/retry", response_model=TaskSubmissionResponse)
async def retry_task(
    task_id: str,
    user=current_user_dep
):
    """
    Retry a failed task.
    
    Args:
        task_id: The task ID to retry
        user: Current authenticated user
    
    Returns:
        TaskSubmissionResponse with new task details
    """
    try:
        new_task_info = task_manager.retry_failed_task(task_id)
        
        if not new_task_info:
            raise HTTPException(
                status_code=400,
                detail=f"Task {task_id} could not be retried (may not be in failed state or have no retries left)"
            )
        
        return success_response(TaskSubmissionResponse(
            task_id=new_task_info.task_id,
            status=TaskStatusEnum(new_task_info.status.value),
            estimated_completion=new_task_info.estimated_completion,
            message=f'Task {task_id} retried as {new_task_info.task_id}'
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry task: {str(e)}"
        )


@router.post("/notifications", response_model=TaskSubmissionResponse)
async def submit_notification_task(
    request: NotificationRequest,
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=10, seconds=60))
):
    """
    Submit a notification task (push or email).
    
    Args:
        request: Notification request details
        user: Current authenticated user
    
    Returns:
        TaskSubmissionResponse with task details
    """
    try:
        if request.notification_type == "email" and not request.email:
            raise HTTPException(
                status_code=400,
                detail="Email address is required for email notifications"
            )
        
        task_info = task_manager.submit_notification_task(
            user_id=user.id,
            message=request.message,
            notification_type=request.notification_type,
            title=request.title,
            email=request.email,
            data=request.data
        )
        
        return success_response(TaskSubmissionResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            message=f'{request.notification_type.title()} notification queued for processing'
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting notification task: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit notification task: {str(e)}"
        )


@router.post("/data-export", response_model=TaskSubmissionResponse)
async def submit_data_export_task(
    request: DataExportRequest,
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=2, seconds=300))  # 2 exports per 5 minutes
):
    """
    Submit a data export task for the current user.
    
    Args:
        request: Data export request details
        user: Current authenticated user
    
    Returns:
        TaskSubmissionResponse with task details
    """
    try:
        if request.export_format not in ['json', 'csv']:
            raise HTTPException(
                status_code=400,
                detail="Export format must be 'json' or 'csv'"
            )
        
        task_info = task_manager.submit_data_export_task(
            user_id=user.id,
            export_format=request.export_format,
            include_transactions=request.include_transactions,
            include_analytics=request.include_analytics
        )
        
        return success_response(TaskSubmissionResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            message=f'Data export ({request.export_format}) queued for processing'
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting data export task: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit data export task: {str(e)}"
        )


@router.post("/ai-analysis", response_model=TaskSubmissionResponse)
async def submit_ai_analysis_task(
    request: AIAnalysisRequest,
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=5, seconds=300))  # 5 analyses per 5 minutes
):
    """
    Submit an AI analysis task for the current user.
    
    Args:
        request: AI analysis request details
        user: Current authenticated user
    
    Returns:
        TaskSubmissionResponse with task details
    """
    try:
        task_info = task_manager.submit_ai_analysis_task(
            user_id=user.id,
            year=request.year,
            month=request.month
        )
        
        return success_response(TaskSubmissionResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            message=f'AI analysis for {request.year}-{request.month:02d} queued for processing'
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting AI analysis task: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit AI analysis task: {str(e)}"
        )


@router.post("/budget-redistribution", response_model=TaskSubmissionResponse)
async def submit_budget_redistribution_task(
    request: BudgetRedistributionRequest,
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=3, seconds=300))  # 3 redistributions per 5 minutes
):
    """
    Submit a budget redistribution task for the current user.
    
    Args:
        request: Budget redistribution request details
        user: Current authenticated user
    
    Returns:
        TaskSubmissionResponse with task details
    """
    try:
        task_info = task_manager.submit_budget_redistribution_task(
            user_id=user.id,
            year=request.year,
            month=request.month
        )
        
        return success_response(TaskSubmissionResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            message=f'Budget redistribution for {request.year}-{request.month:02d} queued for processing'
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting budget redistribution task: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit budget redistribution task: {str(e)}"
        )


@router.get("/system/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=10, seconds=60))
):
    """
    Get system statistics and health information.
    Restricted to admin users in production.
    
    Args:
        user: Current authenticated user
    
    Returns:
        SystemStatsResponse with system statistics
    """
    try:
        # In production, you'd want to check if user is admin
        # For now, allowing all authenticated users
        
        stats = task_manager.get_system_stats()
        
        return success_response(SystemStatsResponse(**stats))
        
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system stats: {str(e)}"
        )


# Admin endpoints for batch operations (in production, add admin role check)

@router.post("/admin/daily-advice", response_model=BatchTaskResponse)
async def submit_daily_advice_batch(
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=2, seconds=3600))  # 2 per hour
):
    """
    Submit daily AI advice batch task.
    Admin only endpoint.
    
    Args:
        user: Current authenticated user (must be admin)
    
    Returns:
        BatchTaskResponse with batch task details
    """
    try:
        # Check admin access with feature flag
        require_admin_access(user)
        
        task_info = task_manager.submit_daily_advice_batch()
        
        return success_response(BatchTaskResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            description="Daily AI advice batch processing for all active users"
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting daily advice batch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit daily advice batch: {str(e)}"
        )


@router.post("/admin/monthly-redistribution", response_model=BatchTaskResponse)
async def submit_monthly_redistribution_batch(
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=1, seconds=7200))  # 1 per 2 hours
):
    """
    Submit monthly budget redistribution batch task.
    Admin only endpoint.
    
    Args:
        user: Current authenticated user (must be admin)
    
    Returns:
        BatchTaskResponse with batch task details
    """
    try:
        # Check admin access with feature flag
        require_admin_access(user)
        
        task_info = task_manager.submit_monthly_redistribution_batch()
        
        return success_response(BatchTaskResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            description="Monthly budget redistribution batch processing for all active users"
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting monthly redistribution batch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit monthly redistribution batch: {str(e)}"
        )


@router.post("/admin/cleanup", response_model=BatchTaskResponse)
async def submit_cleanup_batch(
    max_age_hours: int = Query(48, ge=1, le=168, description="Maximum age of tasks to keep (1-168 hours)"),
    user=current_user_dep,
    _: None = Depends(RateLimiter(times=3, seconds=3600))  # 3 per hour
):
    """
    Submit cleanup batch task to remove old completed/failed tasks.
    Admin only endpoint.
    
    Args:
        max_age_hours: Maximum age of tasks to keep (1-168 hours)
        user: Current authenticated user (must be admin)
    
    Returns:
        BatchTaskResponse with batch task details
    """
    try:
        # Check admin access with feature flag
        require_admin_access(user)
        
        task_info = task_manager.submit_cleanup_batch(max_age_hours)
        
        return success_response(BatchTaskResponse(
            task_id=task_info.task_id,
            status=TaskStatusEnum(task_info.status.value),
            estimated_completion=task_info.estimated_completion,
            description=f"Cleanup batch processing for tasks older than {max_age_hours} hours"
        ))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting cleanup batch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit cleanup batch: {str(e)}"
        )