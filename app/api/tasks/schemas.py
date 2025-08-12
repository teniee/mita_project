"""
Task API schemas for MITA financial platform.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class TaskResponse(BaseModel):
    """Task status response schema."""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatusEnum = Field(..., description="Current task status")
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result data")
    error: Optional[str] = Field(None, description="Error message if task failed")
    created_at: Optional[datetime] = Field(None, description="Task creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Task start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TaskSubmissionResponse(BaseModel):
    """Task submission response schema."""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatusEnum = Field(..., description="Initial task status")
    estimated_completion: Optional[str] = Field(None, description="Estimated completion time")
    message: str = Field(..., description="Human-readable status message")


class NotificationRequest(BaseModel):
    """Notification task request schema."""
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    notification_type: str = Field("push", description="Notification type (push or email)")
    title: Optional[str] = Field(None, max_length=200, description="Notification title")
    email: Optional[str] = Field(None, description="Email address for email notifications")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data for push notifications")


class DataExportRequest(BaseModel):
    """Data export task request schema."""
    export_format: str = Field("json", description="Export format (json or csv)")
    include_transactions: bool = Field(True, description="Include transaction data")
    include_analytics: bool = Field(True, description="Include analytics data")


class AIAnalysisRequest(BaseModel):
    """AI analysis task request schema."""
    year: int = Field(..., ge=2020, le=2030, description="Analysis year")
    month: int = Field(..., ge=1, le=12, description="Analysis month")


class BudgetRedistributionRequest(BaseModel):
    """Budget redistribution task request schema."""
    year: int = Field(..., ge=2020, le=2030, description="Redistribution year")
    month: int = Field(..., ge=1, le=12, description="Redistribution month")


class SystemStatsResponse(BaseModel):
    """System statistics response schema."""
    queue_statistics: Dict[str, Any] = Field(..., description="Queue statistics")
    timestamp: str = Field(..., description="Statistics timestamp")
    system_health: str = Field(..., description="Overall system health status")


class BatchTaskResponse(BaseModel):
    """Batch task response schema."""
    task_id: str = Field(..., description="Batch task identifier")
    status: TaskStatusEnum = Field(..., description="Batch task status")
    estimated_completion: str = Field(..., description="Estimated completion time")
    description: str = Field(..., description="Batch task description")