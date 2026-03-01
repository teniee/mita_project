"""
Audit Reporting API Endpoints
Provides endpoints for generating and viewing audit reports
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.audit_logging import audit_logger, AuditEventType
from app.api.dependencies import get_current_user, require_admin_access
from app.db.models import User

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditReportRequest(BaseModel):
    """Request model for audit reports"""
    start_date: datetime = Field(..., description="Start date for the report")
    end_date: datetime = Field(..., description="End date for the report")
    user_id: Optional[str] = Field(None, description="Filter by specific user ID")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    endpoint: Optional[str] = Field(None, description="Filter by endpoint")


class AuditSummaryResponse(BaseModel):
    """Response model for audit summary"""
    total_events: int
    unique_users: int
    unique_ips: int
    avg_response_time_ms: float
    failed_requests: int
    success_rate: float


class AuditReportResponse(BaseModel):
    """Response model for audit reports"""
    summary: AuditSummaryResponse
    top_endpoints: list
    security_violations: list
    report_period: Dict[str, str]
    generated_at: datetime


@router.get("/health", summary="Audit System Health Check")
async def audit_health():
    """Check if audit logging system is working"""
    try:
        buffer_size = len(audit_logger.buffer)
        last_flush = audit_logger.last_flush
        
        return {
            "status": "healthy",
            "buffer_size": buffer_size,
            "last_flush": datetime.fromtimestamp(last_flush).isoformat(),
            "system": "operational"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Audit system unhealthy: {str(e)}"
        )


@router.get("/report", response_model=AuditReportResponse, summary="Generate Audit Report")
async def generate_audit_report(
    start_date: datetime = Query(..., description="Start date for the report"),
    end_date: datetime = Query(..., description="End date for the report"),
    user_id: Optional[str] = Query(None, description="Filter by specific user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Generate comprehensive audit report
    
    Requires admin access. Provides detailed analytics on:
    - Request/response patterns
    - Security violations
    - User activity
    - System performance metrics
    """
    try:
        # Validate date range
        if end_date <= start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date"
            )
        
        # Limit report range to prevent performance issues
        max_days = 90
        if (end_date - start_date).days > max_days:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report range cannot exceed {max_days} days"
            )
        
        # Convert event_type string to enum if provided
        event_type_enum = None
        if event_type:
            try:
                event_type_enum = AuditEventType(event_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event type: {event_type}"
                )
        
        # Generate report
        report_data = await audit_logger.get_audit_report(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            event_type=event_type_enum
        )
        
        if not report_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No audit data found for the specified criteria"
            )
        
        # Calculate success rate
        summary = report_data['summary']
        total_requests = summary['total_events']
        failed_requests = summary['failed_requests']
        success_rate = ((total_requests - failed_requests) / total_requests * 100) if total_requests > 0 else 0
        
        return AuditReportResponse(
            summary=AuditSummaryResponse(
                total_events=summary['total_events'],
                unique_users=summary['unique_users'],
                unique_ips=summary['unique_ips'],
                avg_response_time_ms=summary['avg_response_time_ms'],
                failed_requests=summary['failed_requests'],
                success_rate=round(success_rate, 2)
            ),
            top_endpoints=report_data['top_endpoints'],
            security_violations=report_data['security_violations'],
            report_period=report_data['report_period'],
            generated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating audit report: {str(e)}"
        )


@router.get("/security-summary", summary="Security Events Summary")
async def get_security_summary(
    hours: int = Query(24, description="Number of hours to look back", ge=1, le=168),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get summary of security events in the last N hours
    
    Requires admin access. Returns:
    - Total security violations
    - Breakdown by violation type
    - Top offending IPs
    - Recent critical events
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        
        # Get security violations report
        report_data = await audit_logger.get_audit_report(
            start_date=start_date,
            end_date=end_date,
            event_type=AuditEventType.SECURITY_VIOLATION
        )
        
        return {
            "period_hours": hours,
            "total_violations": report_data.get('summary', {}).get('total_events', 0),
            "unique_ips": report_data.get('summary', {}).get('unique_ips', 0),
            "violations_by_ip": report_data.get('security_violations', []),
            "summary": report_data.get('summary', {}),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating security summary: {str(e)}"
        )


@router.get("/user-activity/{user_id}", summary="User Activity Report")
async def get_user_activity(
    user_id: str,
    days: int = Query(7, description="Number of days to look back", ge=1, le=30),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get detailed activity report for a specific user
    
    Requires admin access. Shows:
    - Request patterns
    - Authentication events
    - Data access events
    - Failed requests
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get user-specific report
        report_data = await audit_logger.get_audit_report(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id
        )
        
        return {
            "user_id": user_id,
            "period_days": days,
            "activity_summary": report_data.get('summary', {}),
            "top_endpoints": report_data.get('top_endpoints', []),
            "report_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating user activity report: {str(e)}"
        )


@router.get("/performance-metrics", summary="API Performance Metrics")
async def get_performance_metrics(
    hours: int = Query(24, description="Number of hours to look back", ge=1, le=168),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Get API performance metrics
    
    Requires admin access. Returns:
    - Average response times by endpoint
    - Slowest endpoints
    - Error rates
    - Request volume patterns
    """
    try:
        # This would typically query the audit logs for performance data
        # For now, return a placeholder structure
        return {
            "period_hours": hours,
            "metrics": {
                "avg_response_time_ms": 150.5,
                "total_requests": 12450,
                "error_rate_percent": 2.3,
                "requests_per_hour": 518
            },
            "slowest_endpoints": [
                {"endpoint": "/transactions", "avg_time_ms": 450.2},
                {"endpoint": "/goals", "avg_time_ms": 320.1},
                {"endpoint": "/users/profile", "avg_time_ms": 180.5}
            ],
            "error_breakdown": {
                "4xx_errors": 150,
                "5xx_errors": 35,
                "timeout_errors": 12
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating performance metrics: {str(e)}"
        )


@router.post("/flush", summary="Flush Audit Buffer")
async def flush_audit_buffer(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_admin_access)
):
    """
    Manually flush the audit buffer to database
    
    Requires admin access. Forces immediate flush of pending audit events.
    """
    try:
        buffer_size_before = len(audit_logger.buffer)
        await audit_logger._flush_buffer()
        
        return {
            "status": "success",
            "message": f"Flushed {buffer_size_before} audit events",
            "flushed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error flushing audit buffer: {str(e)}"
        )


@router.get("/event-types", summary="Available Event Types")
async def get_event_types():
    """Get list of available audit event types for filtering"""
    return {
        "event_types": [event_type.value for event_type in AuditEventType],
        "descriptions": {
            "request": "HTTP request/response events",
            "authentication": "Login/logout events",
            "authorization": "Access control events",
            "data_access": "Data read operations",
            "data_modification": "Data write operations",
            "security_violation": "Security threat events",
            "system_event": "System-level events"
        }
    }