"""
Task Manager Service for MITA Financial Platform.
Provides high-level task management and status tracking for API endpoints.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from app.core.task_queue import task_queue, TaskStatus, TaskResult, enqueue_task
from app.core.logger import get_logger
from app.tasks.async_tasks import (
    process_ocr_task,
    generate_ai_analysis_task,
    budget_redistribution_task,
    send_email_notification_task,
    send_push_notification_task,
    export_user_data_task,
    daily_ai_advice_batch_task,
    monthly_budget_redistribution_batch_task,
    cleanup_old_tasks_batch_task
)

logger = get_logger(__name__)


@dataclass
class TaskInfo:
    """Task information for API responses."""
    task_id: str
    status: TaskStatus
    progress: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[str] = None


class TaskManager:
    """High-level task management service for MITA operations."""
    
    def __init__(self):
        """Initialize the task manager."""
        self.task_queue = task_queue
        logger.info("Task manager initialized")

    def submit_ocr_task(
        self,
        user_id: int,
        image_path: str,
        is_premium_user: bool = False
    ) -> TaskInfo:
        """
        Submit OCR processing task for receipt image.
        
        Args:
            user_id: User ID for the transaction
            image_path: Path to the uploaded image
            is_premium_user: Whether to use premium OCR service
        
        Returns:
            TaskInfo with task details
        """
        try:
            job = enqueue_task(
                process_ocr_task,
                user_id=user_id,
                image_path=image_path,
                is_premium_user=is_premium_user
            )
            
            logger.info(
                f"OCR task submitted for user {user_id}: {job.id}",
                extra={'user_id': user_id, 'task_id': job.id}
            )
            
            return TaskInfo(
                task_id=job.id,
                status=TaskStatus.QUEUED,
                created_at=datetime.utcnow(),
                estimated_completion="2-5 minutes"
            )
            
        except Exception as e:
            logger.error(f"Failed to submit OCR task: {str(e)}", exc_info=True)
            raise

    def submit_ai_analysis_task(
        self,
        user_id: int,
        year: int,
        month: int
    ) -> TaskInfo:
        """
        Submit AI analysis task for user financial profile.
        
        Args:
            user_id: User ID to analyze
            year: Analysis year
            month: Analysis month
        
        Returns:
            TaskInfo with task details
        """
        try:
            job = enqueue_task(
                generate_ai_analysis_task,
                user_id=user_id,
                year=year,
                month=month
            )
            
            logger.info(
                f"AI analysis task submitted for user {user_id}: {job.id}",
                extra={'user_id': user_id, 'task_id': job.id}
            )
            
            return TaskInfo(
                task_id=job.id,
                status=TaskStatus.QUEUED,
                created_at=datetime.utcnow(),
                estimated_completion="5-10 minutes"
            )
            
        except Exception as e:
            logger.error(f"Failed to submit AI analysis task: {str(e)}", exc_info=True)
            raise

    def submit_budget_redistribution_task(
        self,
        user_id: int,
        year: int,
        month: int
    ) -> TaskInfo:
        """
        Submit budget redistribution task for user.
        
        Args:
            user_id: User ID to redistribute budget for
            year: Redistribution year
            month: Redistribution month
        
        Returns:
            TaskInfo with task details
        """
        try:
            job = enqueue_task(
                budget_redistribution_task,
                user_id=user_id,
                year=year,
                month=month
            )
            
            logger.info(
                f"Budget redistribution task submitted for user {user_id}: {job.id}",
                extra={'user_id': user_id, 'task_id': job.id}
            )
            
            return TaskInfo(
                task_id=job.id,
                status=TaskStatus.QUEUED,
                created_at=datetime.utcnow(),
                estimated_completion="1-3 minutes"
            )
            
        except Exception as e:
            logger.error(f"Failed to submit budget redistribution task: {str(e)}", exc_info=True)
            raise

    def submit_notification_task(
        self,
        user_id: int,
        message: str,
        notification_type: str = "push",
        title: Optional[str] = None,
        email: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> TaskInfo:
        """
        Submit notification task (push or email).
        
        Args:
            user_id: User ID to send notification to
            message: Notification message
            notification_type: Type of notification ('push' or 'email')
            title: Optional title for push notifications
            email: Email address for email notifications
            data: Optional additional data for push notifications
        
        Returns:
            TaskInfo with task details
        """
        try:
            if notification_type == "push":
                job = enqueue_task(
                    send_push_notification_task,
                    user_id=user_id,
                    message=message,
                    title=title,
                    data=data
                )
                estimated_time = "30 seconds"
            
            elif notification_type == "email":
                if not email:
                    raise ValueError("Email address is required for email notifications")
                
                job = enqueue_task(
                    send_email_notification_task,
                    user_email=email,
                    subject=title or "MITA Notification",
                    body=message,
                    user_id=user_id
                )
                estimated_time = "1 minute"
            
            else:
                raise ValueError(f"Invalid notification type: {notification_type}")
            
            logger.info(
                f"Notification task submitted for user {user_id}: {job.id}",
                extra={'user_id': user_id, 'task_id': job.id, 'type': notification_type}
            )
            
            return TaskInfo(
                task_id=job.id,
                status=TaskStatus.QUEUED,
                created_at=datetime.utcnow(),
                estimated_completion=estimated_time
            )
            
        except Exception as e:
            logger.error(f"Failed to submit notification task: {str(e)}", exc_info=True)
            raise

    def submit_data_export_task(
        self,
        user_id: int,
        export_format: str = 'json',
        include_transactions: bool = True,
        include_analytics: bool = True
    ) -> TaskInfo:
        """
        Submit user data export task.
        
        Args:
            user_id: User ID to export data for
            export_format: Export format ('json' or 'csv')
            include_transactions: Whether to include transaction data
            include_analytics: Whether to include analytics data
        
        Returns:
            TaskInfo with task details
        """
        try:
            job = enqueue_task(
                export_user_data_task,
                user_id=user_id,
                export_format=export_format,
                include_transactions=include_transactions,
                include_analytics=include_analytics
            )
            
            logger.info(
                f"Data export task submitted for user {user_id}: {job.id}",
                extra={'user_id': user_id, 'task_id': job.id, 'format': export_format}
            )
            
            return TaskInfo(
                task_id=job.id,
                status=TaskStatus.QUEUED,
                created_at=datetime.utcnow(),
                estimated_completion="5-15 minutes"
            )
            
        except Exception as e:
            logger.error(f"Failed to submit data export task: {str(e)}", exc_info=True)
            raise

    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """
        Get comprehensive task status information.
        
        Args:
            task_id: Task ID to check
        
        Returns:
            TaskInfo with current status or None if not found
        """
        try:
            task_result = self.task_queue.get_task_status(task_id)
            
            if not task_result:
                return None
            
            # Calculate progress percentage if available
            progress = None
            if task_result.metadata:
                progress = task_result.metadata.get('progress')
            
            return TaskInfo(
                task_id=task_id,
                status=task_result.status,
                progress=progress,
                result=task_result.result,
                error=task_result.error,
                started_at=task_result.started_at,
                completed_at=task_result.completed_at
            )
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {str(e)}")
            return None

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a queued or running task.
        
        Args:
            task_id: Task ID to cancel
        
        Returns:
            True if successfully cancelled, False otherwise
        """
        try:
            success = self.task_queue.cancel_task(task_id)
            
            if success:
                logger.info(f"Task cancelled: {task_id}")
            else:
                logger.warning(f"Failed to cancel task: {task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}")
            return False

    def retry_failed_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        Retry a failed task.
        
        Args:
            task_id: Task ID to retry
        
        Returns:
            TaskInfo for the new task or None if retry failed
        """
        try:
            job = self.task_queue.retry_failed_task(task_id)
            
            if job:
                logger.info(f"Task retried: {task_id} -> {job.id}")
                return TaskInfo(
                    task_id=job.id,
                    status=TaskStatus.QUEUED,
                    created_at=datetime.utcnow()
                )
            else:
                logger.warning(f"Failed to retry task: {task_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrying task {task_id}: {str(e)}")
            return None

    def get_user_tasks(
        self,
        user_id: int,
        limit: int = 50,
        status_filter: Optional[TaskStatus] = None
    ) -> List[TaskInfo]:
        """
        Get tasks for a specific user.
        
        Args:
            user_id: User ID to get tasks for
            limit: Maximum number of tasks to return
            status_filter: Optional status filter
        
        Returns:
            List of TaskInfo objects
        """
        # Note: This is a simplified implementation
        # In production, you'd want to store user-task mappings in Redis
        # or implement a more sophisticated task tracking system
        
        logger.info(f"Getting tasks for user {user_id} (limit: {limit})")
        
        # For now, return empty list with note about implementation
        # This would require additional Redis keys to track user tasks
        return []

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive system statistics for monitoring.
        
        Returns:
            Dict containing system statistics
        """
        try:
            queue_stats = self.task_queue.get_queue_stats()
            
            return {
                'queue_statistics': queue_stats,
                'timestamp': datetime.utcnow().isoformat(),
                'system_health': self._calculate_system_health(queue_stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def _calculate_system_health(self, queue_stats: Dict[str, Any]) -> str:
        """Calculate overall system health based on queue statistics."""
        try:
            total_failed = sum(
                queue_data.get('failed_job_count', 0) 
                for queue_data in queue_stats.values()
                if isinstance(queue_data, dict) and 'failed_job_count' in queue_data
            )
            
            total_queued = sum(
                queue_data.get('length', 0)
                for queue_data in queue_stats.values()
                if isinstance(queue_data, dict) and 'length' in queue_data
            )
            
            workers = queue_stats.get('workers', {})
            active_workers = workers.get('active', 0)
            total_workers = workers.get('total', 0)
            
            # Simple health calculation
            if total_failed > 10:
                return "degraded"
            elif total_queued > 100:
                return "busy"
            elif total_workers == 0:
                return "no_workers"
            elif active_workers / max(total_workers, 1) > 0.8:
                return "high_load"
            else:
                return "healthy"
                
        except Exception:
            return "unknown"

    # Batch operation methods for cron jobs

    def submit_daily_advice_batch(self) -> TaskInfo:
        """Submit daily AI advice batch task."""
        job = enqueue_task(daily_ai_advice_batch_task)
        
        logger.info(f"Daily advice batch task submitted: {job.id}")
        
        return TaskInfo(
            task_id=job.id,
            status=TaskStatus.QUEUED,
            created_at=datetime.utcnow(),
            estimated_completion="15-30 minutes"
        )

    def submit_monthly_redistribution_batch(self) -> TaskInfo:
        """Submit monthly budget redistribution batch task."""
        job = enqueue_task(monthly_budget_redistribution_batch_task)
        
        logger.info(f"Monthly redistribution batch task submitted: {job.id}")
        
        return TaskInfo(
            task_id=job.id,
            status=TaskStatus.QUEUED,
            created_at=datetime.utcnow(),
            estimated_completion="30-60 minutes"
        )

    def submit_cleanup_batch(self, max_age_hours: int = 48) -> TaskInfo:
        """Submit cleanup batch task."""
        job = enqueue_task(cleanup_old_tasks_batch_task, max_age_hours=max_age_hours)
        
        logger.info(f"Cleanup batch task submitted: {job.id}")
        
        return TaskInfo(
            task_id=job.id,
            status=TaskStatus.QUEUED,
            created_at=datetime.utcnow(),
            estimated_completion="5-30 minutes"
        )


# Global task manager instance
task_manager = TaskManager()