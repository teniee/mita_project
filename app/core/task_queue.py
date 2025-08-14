"""
Production-ready task queue system for MITA financial platform.
Provides reliable async task processing with monitoring and error handling.
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum

import redis
from rq import Queue, Worker, Connection
from rq.job import Job
from rq.middleware import Middleware
from rq.job import JobStatus
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels for queue management."""
    LOW = "low"
    NORMAL = "normal" 
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Enhanced task status tracking."""
    PENDING = "pending"
    QUEUED = "queued"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Standardized task result structure."""
    task_id: str
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for field in ['started_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        return data


class TaskLoggingMiddleware(Middleware):
    """RQ middleware for comprehensive task logging."""

    def call(self, queue: Queue, job_class, job, *args, **kwargs):
        """Log task execution with comprehensive details."""
        logger.info(
            f"Task started: {job.id} - {job.func_name}",
            extra={
                'task_id': job.id,
                'function': job.func_name,
                'queue': queue.name,
                'started_at': datetime.utcnow().isoformat(),
                'args_count': len(job.args),
                'kwargs_count': len(job.kwargs)
            }
        )
        
        start_time = time.time()
        try:
            result = super().call(queue, job_class, job, *args, **kwargs)
            duration = time.time() - start_time
            
            logger.info(
                f"Task completed: {job.id} - {job.func_name} ({duration:.2f}s)",
                extra={
                    'task_id': job.id,
                    'function': job.func_name,
                    'duration': duration,
                    'status': 'completed'
                }
            )
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Task failed: {job.id} - {job.func_name} ({duration:.2f}s): {str(e)}",
                extra={
                    'task_id': job.id,
                    'function': job.func_name,
                    'duration': duration,
                    'status': 'failed',
                    'error': str(e),
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            raise


class MitaTaskQueue:
    """Enhanced task queue system for MITA financial operations."""
    
    def __init__(self):
        """Initialize the task queue system."""
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_conn = redis.from_url(self.redis_url)
        
        # Initialize priority queues
        self.queues = {
            TaskPriority.CRITICAL: Queue('critical', connection=self.redis_conn),
            TaskPriority.HIGH: Queue('high', connection=self.redis_conn),
            TaskPriority.NORMAL: Queue('default', connection=self.redis_conn),
            TaskPriority.LOW: Queue('low', connection=self.redis_conn),
        }
        
        # Dead letter queue for failed tasks
        self.dlq = Queue('failed', connection=self.redis_conn)
        
        # Task result storage (Redis keys expire after 24 hours)
        self.result_ttl = 24 * 3600  # 24 hours
        
        logger.info("MITA task queue system initialized")

    def enqueue_task(
        self,
        func: Callable,
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        job_timeout: Optional[int] = None,
        result_ttl: Optional[int] = None,
        retry_count: int = 3,
        retry_delay: int = 60,
        task_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Job:
        """
        Enqueue a task with comprehensive error handling and retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            priority: Task priority level
            job_timeout: Maximum execution time in seconds
            result_ttl: Result storage time in seconds
            retry_count: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            task_metadata: Additional task metadata
            **kwargs: Function keyword arguments
        
        Returns:
            Job: RQ job object
        """
        queue = self.queues[priority]
        
        # Set default timeouts based on task type
        if job_timeout is None:
            job_timeout = self._get_default_timeout(func.__name__)
        
        if result_ttl is None:
            result_ttl = self.result_ttl
        
        # Prepare job metadata
        metadata = {
            'priority': priority.value,
            'retry_count': retry_count,
            'retry_delay': retry_delay,
            'enqueued_at': datetime.utcnow().isoformat(),
            'function_name': func.__name__,
            **(task_metadata or {})
        }
        
        try:
            job = queue.enqueue(
                func,
                *args,
                timeout=job_timeout,
                result_ttl=result_ttl,
                failure_ttl=result_ttl,
                meta=metadata,
                **kwargs
            )
            
            # Store initial task result
            task_result = TaskResult(
                task_id=job.id,
                status=TaskStatus.QUEUED,
                metadata=metadata
            )
            self._store_task_result(job.id, task_result)
            
            logger.info(
                f"Task enqueued: {job.id} - {func.__name__}",
                extra={
                    'task_id': job.id,
                    'function': func.__name__,
                    'priority': priority.value,
                    'queue': queue.name
                }
            )
            
            return job
            
        except Exception as e:
            logger.error(
                f"Failed to enqueue task {func.__name__}: {str(e)}",
                extra={'function': func.__name__, 'error': str(e)},
                exc_info=True
            )
            raise

    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get comprehensive task status and result."""
        try:
            # Try to get stored result first
            stored_result = self._get_stored_task_result(task_id)
            if stored_result:
                return stored_result
            
            # Fall back to RQ job status
            job = Job.fetch(task_id, connection=self.redis_conn)
            
            status_mapping = {
                JobStatus.QUEUED: TaskStatus.QUEUED,
                JobStatus.STARTED: TaskStatus.STARTED,
                JobStatus.FINISHED: TaskStatus.COMPLETED,
                JobStatus.FAILED: TaskStatus.FAILED,
                JobStatus.CANCELED: TaskStatus.CANCELLED,
            }
            
            task_status = status_mapping.get(job.get_status(), TaskStatus.PENDING)
            
            return TaskResult(
                task_id=task_id,
                status=task_status,
                result=job.result if job.is_finished else None,
                error=str(job.exc_info) if job.is_failed else None,
                started_at=job.started_at,
                completed_at=job.ended_at,
                metadata=job.meta
            )
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {str(e)}")
            return None

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued or running task."""
        try:
            job = Job.fetch(task_id, connection=self.redis_conn)
            job.cancel()
            
            # Update stored result
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED,
                completed_at=datetime.utcnow()
            )
            self._store_task_result(task_id, task_result)
            
            logger.info(f"Task cancelled: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {str(e)}")
            return False

    def retry_failed_task(self, task_id: str) -> Optional[Job]:
        """Retry a failed task."""
        try:
            job = Job.fetch(task_id, connection=self.redis_conn)
            
            if not job.is_failed:
                logger.warning(f"Task {task_id} is not in failed state")
                return None
            
            # Get original metadata
            metadata = job.meta or {}
            retry_count = metadata.get('retry_count', 0)
            
            if retry_count <= 0:
                logger.warning(f"Task {task_id} has no retries left")
                return None
            
            # Create new job with decremented retry count
            metadata['retry_count'] = retry_count - 1
            metadata['retried_from'] = task_id
            metadata['retry_at'] = datetime.utcnow().isoformat()
            
            # Determine priority from metadata
            priority = TaskPriority(metadata.get('priority', TaskPriority.NORMAL.value))
            queue = self.queues[priority]
            
            new_job = queue.enqueue(
                job.func,
                *job.args,
                timeout=job.timeout,
                meta=metadata,
                **job.kwargs
            )
            
            logger.info(f"Task retried: {task_id} -> {new_job.id}")
            return new_job
            
        except Exception as e:
            logger.error(f"Failed to retry task {task_id}: {str(e)}")
            return None

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics."""
        stats = {}
        
        for priority, queue in self.queues.items():
            stats[priority.value] = {
                'name': queue.name,
                'length': len(queue),
                'failed_job_count': queue.failed_job_registry.count,
                'started_job_count': queue.started_job_registry.count,
                'deferred_job_count': queue.deferred_job_registry.count,
                'finished_job_count': queue.finished_job_registry.count
            }
        
        # Dead letter queue stats
        stats['dead_letter'] = {
            'name': self.dlq.name,
            'length': len(self.dlq),
            'failed_job_count': self.dlq.failed_job_registry.count
        }
        
        # Worker stats
        workers = Worker.all(connection=self.redis_conn)
        stats['workers'] = {
            'total': len(workers),
            'active': len([w for w in workers if w.get_state() == 'busy']),
            'idle': len([w for w in workers if w.get_state() == 'idle'])
        }
        
        return stats

    def clean_old_jobs(self, max_age_hours: int = 48) -> Dict[str, int]:
        """Clean up old completed and failed jobs."""
        cleaned = {'completed': 0, 'failed': 0}
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        for priority, queue in self.queues.items():
            # Clean completed jobs
            for job_id in queue.finished_job_registry.get_job_ids():
                try:
                    job = Job.fetch(job_id, connection=self.redis_conn)
                    if job.ended_at and job.ended_at < cutoff:
                        job.delete()
                        cleaned['completed'] += 1
                except:
                    pass
            
            # Clean failed jobs
            for job_id in queue.failed_job_registry.get_job_ids():
                try:
                    job = Job.fetch(job_id, connection=self.redis_conn)
                    if job.ended_at and job.ended_at < cutoff:
                        job.delete()
                        cleaned['failed'] += 1
                except:
                    pass
        
        logger.info(f"Cleaned {cleaned['completed']} completed and {cleaned['failed']} failed jobs")
        return cleaned

    def _get_default_timeout(self, function_name: str) -> int:
        """Get default timeout based on function type."""
        timeout_map = {
            'process_ocr_task': 300,  # 5 minutes for OCR
            'generate_ai_analysis': 600,  # 10 minutes for AI analysis
            'redistribute_budget': 180,  # 3 minutes for budget redistribution
            'send_email_notification': 60,  # 1 minute for email
            'send_push_notification': 30,  # 30 seconds for push
            'export_user_data': 900,  # 15 minutes for data export
        }
        return timeout_map.get(function_name, 120)  # Default 2 minutes

    def _store_task_result(self, task_id: str, task_result: TaskResult) -> None:
        """Store task result in Redis."""
        key = f"task_result:{task_id}"
        try:
            self.redis_conn.setex(
                key,
                self.result_ttl,
                json.dumps(task_result.to_dict())
            )
        except Exception as e:
            logger.error(f"Failed to store task result for {task_id}: {str(e)}")

    def _get_stored_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Retrieve stored task result from Redis."""
        key = f"task_result:{task_id}"
        try:
            data = self.redis_conn.get(key)
            if data:
                result_dict = json.loads(data)
                # Convert ISO strings back to datetime objects
                for field in ['started_at', 'completed_at']:
                    if result_dict[field]:
                        result_dict[field] = datetime.fromisoformat(result_dict[field])
                return TaskResult(**result_dict)
        except Exception as e:
            logger.error(f"Failed to retrieve task result for {task_id}: {str(e)}")
        return None


# Global task queue instance
task_queue = MitaTaskQueue()


def task_wrapper(
    priority: TaskPriority = TaskPriority.NORMAL,
    timeout: Optional[int] = None,
    retry_count: int = 3,
    retry_delay: int = 60
):
    """
    Decorator for creating async tasks with error handling and monitoring.
    
    Usage:
        @task_wrapper(priority=TaskPriority.HIGH, retry_count=5)
        def my_heavy_task(user_id: int, data: dict):
            # Task implementation
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            """Execute task with comprehensive error handling."""
            task_id = kwargs.pop('_task_id', None)
            
            try:
                # Update task status to started
                if task_id:
                    task_result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.STARTED,
                        started_at=datetime.utcnow()
                    )
                    task_queue._store_task_result(task_id, task_result)
                
                # Execute the actual task
                result = func(*args, **kwargs)
                
                # Update task status to completed
                if task_id:
                    task_result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.COMPLETED,
                        result=result,
                        started_at=task_result.started_at,
                        completed_at=datetime.utcnow()
                    )
                    task_queue._store_task_result(task_id, task_result)
                
                return result
                
            except Exception as e:
                logger.error(
                    f"Task execution failed: {func.__name__}: {str(e)}",
                    extra={
                        'task_id': task_id,
                        'function': func.__name__,
                        'error': str(e),
                        'error_type': type(e).__name__
                    },
                    exc_info=True
                )
                
                # Update task status to failed
                if task_id:
                    task_result = TaskResult(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                        completed_at=datetime.utcnow()
                    )
                    task_queue._store_task_result(task_id, task_result)
                
                raise
        
        # Store task metadata for enqueueing
        wrapper._task_priority = priority
        wrapper._task_timeout = timeout
        wrapper._task_retry_count = retry_count
        wrapper._task_retry_delay = retry_delay
        
        return wrapper
    
    return decorator


def enqueue_task(func: Callable, *args, **kwargs) -> Job:
    """Convenience function to enqueue a task with its configured settings."""
    priority = getattr(func, '_task_priority', TaskPriority.NORMAL)
    timeout = getattr(func, '_task_timeout', None)
    retry_count = getattr(func, '_task_retry_count', 3)
    retry_delay = getattr(func, '_task_retry_delay', 60)
    
    return task_queue.enqueue_task(
        func,
        *args,
        priority=priority,
        job_timeout=timeout,
        retry_count=retry_count,
        retry_delay=retry_delay,
        **kwargs
    )