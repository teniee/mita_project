"""
Email Service API Routes - Email Management and Monitoring Endpoints
Production-ready email service administration and monitoring
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_session import get_async_db
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.services.email_service import EmailService, EmailType, EmailPriority, get_email_service
from app.services.email_queue_service import EmailQueueService, get_email_queue_service, queue_email
from app.utils.response_wrapper import StandardizedResponse
from app.core.audit_logging import log_security_event_async

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/email",
    tags=["Email Service"]
)


@router.get("/health", summary="Check email service health")
async def check_email_service_health(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Check the health status of the email service including:
    - SendGrid connectivity
    - Template availability
    - Queue status
    - Recent delivery metrics
    """
    try:
        email_service = await get_email_service()
        queue_service = await get_email_queue_service()
        
        # Get email service health
        service_health = await email_service.validate_service_health()
        
        # Get queue status
        queue_status = await queue_service.get_queue_status()
        
        # Get service metrics
        email_metrics = email_service.get_metrics()
        
        # Log health check request
        await log_security_event_async(
            event_type="email_service_health_check",
            user_id=str(current_user.id),
            request=request,
            details={"requested_by": current_user.email}
        )
        
        return StandardizedResponse.success(
            message="Email service health check completed",
            data={
                "service_health": service_health,
                "queue_status": queue_status,
                "metrics": email_metrics,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Email service health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/queue/status", summary="Get email queue status")
async def get_email_queue_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get detailed status of the email queue including metrics and job counts"""
    try:
        queue_service = await get_email_queue_service()
        queue_status = await queue_service.get_queue_status()
        
        return StandardizedResponse.success(
            message="Email queue status retrieved",
            data=queue_status
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Queue status check failed: {str(e)}"
        )


@router.get("/queue/job/{job_id}", summary="Get email job status")
async def get_email_job_status(
    job_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get status of specific email job by ID"""
    try:
        queue_service = await get_email_queue_service()
        job_status = await queue_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email job not found"
            )
        
        return StandardizedResponse.success(
            message="Email job status retrieved",
            data=job_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job status check failed: {str(e)}"
        )


@router.post("/send", summary="Send email directly (admin only)")
async def send_email_direct(
    request: Request,
    to_email: str,
    email_type: EmailType,
    variables: Dict[str, Any],
    priority: EmailPriority = EmailPriority.NORMAL,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Send email directly without queuing (for admin testing and urgent emails)
    
    Note: This bypasses the queue system and should only be used for testing
    or critical urgent emails that cannot wait for queue processing.
    """
    # Check if user has admin privileges (you may want to implement proper admin role checking)
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for direct email sending"
        )
    
    try:
        email_service = await get_email_service()

        # Send email directly
        result = await email_service.send_email(
            to_email=to_email,
            email_type=email_type,
            variables=variables,
            priority=priority,
            user_id=str(current_user.id),
            db=db
        )

        # Log admin email send
        await log_security_event_async(
            event_type="admin_direct_email_send",
            user_id=str(current_user.id),
            request=request,
            details={
                "email_type": email_type.value,
                "to_email": to_email,
                "success": result.success,
                "message_id": result.message_id
            }
        )

        return StandardizedResponse.success(
            message="Email sent directly",
            data={
                "success": result.success,
                "message_id": result.message_id,
                "error_message": result.error_message,
                "provider": result.provider,
                "sent_at": result.sent_at.isoformat() if result.sent_at else None
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, validation errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Direct email send failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email send failed: {str(e)}"
        )


@router.post("/queue", summary="Queue email for processing")
async def queue_email_for_processing(
    request: Request,
    to_email: str,
    email_type: EmailType,
    variables: Dict[str, Any],
    priority: EmailPriority = EmailPriority.NORMAL,
    delay_seconds: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Queue email for background processing"""
    try:
        job_id = await queue_email(
            to_email=to_email,
            email_type=email_type,
            variables=variables,
            priority=priority,
            user_id=str(current_user.id),
            delay_seconds=delay_seconds
        )
        
        # Log email queuing
        await log_security_event_async(
            event_type="email_queued",
            user_id=str(current_user.id),
            request=request,
            details={
                "email_type": email_type.value,
                "to_email": to_email,
                "job_id": job_id,
                "priority": priority.value,
                "delay_seconds": delay_seconds
            }
        )
        
        return StandardizedResponse.success(
            message="Email queued for processing",
            data={
                "job_id": job_id,
                "status": "queued",
                "estimated_send_time": delay_seconds
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Email queuing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email queuing failed: {str(e)}"
        )


@router.post("/test/template", summary="Test email template rendering")
async def test_email_template(
    request: Request,
    email_type: EmailType,
    variables: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Test email template rendering without sending"""
    try:
        email_service = await get_email_service()
        
        # Render template
        subject, html_content = email_service.template_manager.render_template(
            email_type=email_type,
            variables=variables
        )
        
        # Log template test
        await log_security_event_async(
            event_type="email_template_test",
            user_id=str(current_user.id),
            request=request,
            details={
                "email_type": email_type.value,
                "template_rendered": True
            }
        )
        
        return StandardizedResponse.success(
            message="Email template rendered successfully",
            data={
                "email_type": email_type.value,
                "subject": subject,
                "html_preview": html_content[:500] + "..." if len(html_content) > 500 else html_content,
                "html_length": len(html_content),
                "variables_used": list(variables.keys())
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Template test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template test failed: {str(e)}"
        )


@router.get("/templates", summary="List available email templates")
async def list_email_templates(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get list of available email templates with their configuration"""
    try:
        email_service = await get_email_service()
        templates = email_service.template_manager.templates
        
        template_info = {}
        for email_type, template_config in templates.items():
            template_info[email_type.value] = {
                "name": template_config.name,
                "subject": template_config.subject,
                "template_path": template_config.template_path,
                "template_type": template_config.template_type,
                "required_vars": template_config.required_vars or [],
                "optional_vars": template_config.optional_vars or [],
                "sender_name": template_config.sender_name,
                "sender_email": template_config.sender_email
            }
        
        return StandardizedResponse.success(
            message="Email templates retrieved",
            data={
                "templates": template_info,
                "total_templates": len(templates)
            }
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template list failed: {str(e)}"
        )


@router.post("/admin/queue/start", summary="Start email queue worker (admin only)")
async def start_email_queue_worker(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Start the email queue worker process"""
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        queue_service = await get_email_queue_service()
        await queue_service.start_worker()
        
        await log_security_event_async(
            event_type="email_queue_worker_started",
            user_id=str(current_user.id),
            request=request,
            details={"action": "worker_start", "admin": current_user.email}
        )
        
        return StandardizedResponse.success(
            message="Email queue worker started",
            data={"status": "started", "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Failed to start queue worker: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Worker start failed: {str(e)}"
        )


@router.post("/admin/queue/stop", summary="Stop email queue worker (admin only)")
async def stop_email_queue_worker(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Stop the email queue worker process"""
    if not getattr(current_user, 'is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    try:
        queue_service = await get_email_queue_service()
        await queue_service.stop_worker()
        
        await log_security_event_async(
            event_type="email_queue_worker_stopped",
            user_id=str(current_user.id),
            request=request,
            details={"action": "worker_stop", "admin": current_user.email}
        )
        
        return StandardizedResponse.success(
            message="Email queue worker stopped",
            data={"status": "stopped", "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.) without modification
        raise
    except Exception as e:
        logger.error(f"Failed to stop queue worker: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Worker stop failed: {str(e)}"
        )