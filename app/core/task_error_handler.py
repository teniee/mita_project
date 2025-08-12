"""
Enhanced Error Handler and Dead Letter Queue System for MITA Tasks.
Provides comprehensive error handling, retry logic, and dead letter queue management.
"""

import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import traceback
import logging

import redis
from rq import Job, Queue, Worker
from rq.exceptions import NoSuchJobError
from rq.job import JobStatus

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RetryStrategy(str, Enum):
    """Retry strategy types."""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    IMMEDIATE = "immediate"
    NO_RETRY = "no_retry"


@dataclass
class TaskError:
    """Task error information."""
    task_id: str
    function_name: str
    queue_name: str
    error_type: str
    error_message: str
    error_details: str
    occurred_at: datetime
    worker_id: Optional[str] = None
    retry_count: int = 0
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    is_retryable: bool = True
    user_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_retries: int = 3
    base_delay: int = 60  # seconds
    max_delay: int = 3600  # 1 hour max
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_errors: Optional[List[str]] = None
    non_retryable_errors: Optional[List[str]] = None


class TaskErrorHandler:
    """Comprehensive task error handler with dead letter queue support."""
    
    def __init__(self, redis_conn: redis.Redis):
        """Initialize the error handler."""
        self.redis_conn = redis_conn
        
        # Dead letter queues
        self.dlq_permanent = Queue('dlq_permanent', connection=redis_conn)
        self.dlq_retry = Queue('dlq_retry', connection=redis_conn)
        self.dlq_investigate = Queue('dlq_investigate', connection=redis_conn)
        
        # Default retry policies by function type
        self.default_retry_policies = {
            'ocr_processing': RetryPolicy(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=3,
                base_delay=60,
                retryable_errors=['ConnectionError', 'TimeoutError', 'APIError'],
                non_retryable_errors=['ValidationError', 'AuthenticationError']
            ),
            'ai_analysis': RetryPolicy(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=2,
                base_delay=120,
                max_delay=1800,
                retryable_errors=['ConnectionError', 'TimeoutError'],
                non_retryable_errors=['ValidationError', 'InsufficientDataError']
            ),
            'budget_redistribution': RetryPolicy(
                strategy=RetryStrategy.LINEAR_BACKOFF,
                max_retries=5,
                base_delay=30,
                retryable_errors=['DatabaseError', 'LockError'],
                non_retryable_errors=['ValidationError', 'UserNotFoundError']
            ),
            'email_notification': RetryPolicy(
                strategy=RetryStrategy.FIXED_DELAY,
                max_retries=5,
                base_delay=300,  # 5 minutes
                retryable_errors=['SMTPError', 'ConnectionError'],
                non_retryable_errors=['InvalidEmailError', 'AuthenticationError']
            ),
            'push_notification': RetryPolicy(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=3,
                base_delay=30,
                retryable_errors=['ConnectionError', 'ServerError'],
                non_retryable_errors=['InvalidTokenError', 'AuthenticationError']
            )
        }
        
        logger.info("Task error handler initialized")

    def handle_task_failure(
        self,
        job: Job,
        exception: Exception,
        traceback_str: str,
        worker: Optional[Worker] = None
    ) -> Dict[str, Any]:
        """
        Handle task failure with comprehensive error processing.
        
        Args:
            job: Failed RQ job
            exception: The exception that occurred
            traceback_str: Full traceback string
            worker: Worker that was processing the job
        
        Returns:
            Dict containing error handling results
        """
        try:
            # Create task error record
            task_error = self._create_task_error(job, exception, traceback_str, worker)
            
            # Store error information
            self._store_error_record(task_error)
            
            # Determine retry policy
            retry_policy = self._get_retry_policy(task_error.function_name)
            
            # Check if error is retryable
            should_retry = self._should_retry_task(task_error, retry_policy)
            
            result = {
                'task_id': task_error.task_id,
                'error_recorded': True,
                'should_retry': should_retry,
                'retry_count': task_error.retry_count,
                'severity': task_error.severity.value
            }
            
            if should_retry:
                # Calculate retry delay
                delay = self._calculate_retry_delay(task_error, retry_policy)
                
                # Schedule retry
                retry_result = self._schedule_retry(job, delay, retry_policy)
                result.update(retry_result)
                
                logger.info(
                    f"Task {task_error.task_id} scheduled for retry in {delay} seconds "
                    f"(attempt {task_error.retry_count + 1}/{retry_policy.max_retries})"
                )
            else:
                # Move to appropriate dead letter queue
                dlq_result = self._move_to_dead_letter_queue(task_error, job)
                result.update(dlq_result)
                
                logger.error(
                    f"Task {task_error.task_id} moved to dead letter queue: {dlq_result.get('dlq_type')}"
                )
            
            # Update error statistics
            self._update_error_statistics(task_error)
            
            # Check if alert should be sent
            self._check_alert_conditions(task_error)
            
            return result
            
        except Exception as handler_error:
            logger.error(
                f"Error handler itself failed: {str(handler_error)}",
                exc_info=True
            )
            return {
                'task_id': job.id if job else 'unknown',
                'error_recorded': False,
                'handler_error': str(handler_error)
            }

    def get_error_statistics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
            
            # Get error records
            error_records = self._get_error_records_since(cutoff_time)
            
            # Calculate statistics
            stats = {
                'total_errors': len(error_records),
                'errors_by_type': {},
                'errors_by_function': {},
                'errors_by_severity': {},
                'errors_by_queue': {},
                'retry_success_rate': 0,
                'common_error_patterns': {},
                'error_trends': self._calculate_error_trends(error_records)
            }
            
            for error in error_records:
                # By error type
                error_type = error.error_type
                stats['errors_by_type'][error_type] = stats['errors_by_type'].get(error_type, 0) + 1
                
                # By function
                func_name = error.function_name
                stats['errors_by_function'][func_name] = stats['errors_by_function'].get(func_name, 0) + 1
                
                # By severity
                severity = error.severity.value
                stats['errors_by_severity'][severity] = stats['errors_by_severity'].get(severity, 0) + 1
                
                # By queue
                queue_name = error.queue_name
                stats['errors_by_queue'][queue_name] = stats['errors_by_queue'].get(queue_name, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get error statistics: {str(e)}")
            return {'error': str(e)}

    def get_dead_letter_queue_summary(self) -> Dict[str, Any]:
        """Get summary of all dead letter queues."""
        try:
            return {
                'permanent_failures': {
                    'count': len(self.dlq_permanent),
                    'jobs': self._get_dlq_job_summaries(self.dlq_permanent)
                },
                'retry_exhausted': {
                    'count': len(self.dlq_retry),
                    'jobs': self._get_dlq_job_summaries(self.dlq_retry)
                },
                'needs_investigation': {
                    'count': len(self.dlq_investigate),
                    'jobs': self._get_dlq_job_summaries(self.dlq_investigate)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get DLQ summary: {str(e)}")
            return {'error': str(e)}

    def cleanup_old_error_records(self, max_age_days: int = 30) -> Dict[str, Any]:
        """Clean up old error records."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
            
            # Scan for old error records
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = self.redis_conn.scan(
                    cursor=cursor,
                    match="task_error:*",
                    count=100
                )
                
                for key in keys:
                    try:
                        data = self.redis_conn.get(key)
                        if data:
                            error_data = json.loads(data)
                            occurred_at = datetime.fromisoformat(error_data['occurred_at'])
                            
                            if occurred_at < cutoff_time:
                                self.redis_conn.delete(key)
                                deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to process error record {key}: {str(e)}")
                
                if cursor == 0:
                    break
            
            logger.info(f"Cleaned up {deleted_count} old error records")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup old error records: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _create_task_error(
        self,
        job: Job,
        exception: Exception,
        traceback_str: str,
        worker: Optional[Worker]
    ) -> TaskError:
        """Create a TaskError record from job failure."""
        error_type = type(exception).__name__
        error_message = str(exception)
        
        # Extract context from job
        context = {}
        if hasattr(job, 'meta') and job.meta:
            context.update(job.meta)
        
        # Determine severity
        severity = self._classify_error_severity(error_type, error_message)
        
        # Check if error is retryable
        is_retryable = self._is_error_retryable(error_type, job.func_name)
        
        # Get retry count from job meta
        retry_count = context.get('retry_count', 0)
        
        return TaskError(
            task_id=job.id,
            function_name=job.func_name,
            queue_name=job.origin,
            error_type=error_type,
            error_message=error_message,
            error_details=traceback_str,
            occurred_at=datetime.utcnow(),
            worker_id=worker.name if worker else None,
            retry_count=retry_count,
            severity=severity,
            is_retryable=is_retryable,
            user_id=context.get('user_id'),
            context=context
        )

    def _classify_error_severity(self, error_type: str, error_message: str) -> ErrorSeverity:
        """Classify error severity based on type and message."""
        # Critical errors
        if error_type in ['SystemError', 'MemoryError', 'OutOfMemoryError']:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if error_type in ['DatabaseError', 'AuthenticationError', 'PermissionError']:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if error_type in ['ConnectionError', 'TimeoutError', 'APIError']:
            return ErrorSeverity.MEDIUM
        
        # Check error message patterns
        if any(pattern in error_message.lower() for pattern in ['critical', 'fatal', 'system']):
            return ErrorSeverity.HIGH
        
        return ErrorSeverity.MEDIUM

    def _is_error_retryable(self, error_type: str, function_name: str) -> bool:
        """Determine if an error is retryable."""
        retry_policy = self._get_retry_policy(function_name)
        
        # Check non-retryable errors
        if retry_policy.non_retryable_errors and error_type in retry_policy.non_retryable_errors:
            return False
        
        # Check retryable errors
        if retry_policy.retryable_errors and error_type in retry_policy.retryable_errors:
            return True
        
        # Default classification
        non_retryable_types = [
            'ValidationError', 'ValueError', 'TypeError', 'AttributeError',
            'KeyError', 'IndexError', 'AuthenticationError', 'PermissionError'
        ]
        
        return error_type not in non_retryable_types

    def _get_retry_policy(self, function_name: str) -> RetryPolicy:
        """Get retry policy for a function."""
        # Try to match function name patterns
        for pattern, policy in self.default_retry_policies.items():
            if pattern in function_name.lower():
                return policy
        
        # Default policy
        return RetryPolicy()

    def _should_retry_task(self, task_error: TaskError, retry_policy: RetryPolicy) -> bool:
        """Determine if a task should be retried."""
        if not task_error.is_retryable:
            return False
        
        if task_error.retry_count >= retry_policy.max_retries:
            return False
        
        if task_error.severity == ErrorSeverity.CRITICAL:
            return False  # Don't retry critical errors
        
        return True

    def _calculate_retry_delay(self, task_error: TaskError, retry_policy: RetryPolicy) -> int:
        """Calculate delay before retry."""
        if retry_policy.strategy == RetryStrategy.IMMEDIATE:
            return 0
        
        elif retry_policy.strategy == RetryStrategy.FIXED_DELAY:
            delay = retry_policy.base_delay
        
        elif retry_policy.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = retry_policy.base_delay * (task_error.retry_count + 1)
        
        elif retry_policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = retry_policy.base_delay * (retry_policy.backoff_factor ** task_error.retry_count)
        
        else:
            delay = retry_policy.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, retry_policy.max_delay)
        
        # Apply jitter if enabled
        if retry_policy.jitter:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay = int(delay * jitter_factor)
        
        return delay

    def _schedule_retry(self, job: Job, delay: int, retry_policy: RetryPolicy) -> Dict[str, Any]:
        """Schedule a task retry."""
        try:
            # Create retry job with updated metadata
            retry_meta = job.meta.copy() if job.meta else {}
            retry_meta['retry_count'] = retry_meta.get('retry_count', 0) + 1
            retry_meta['original_task_id'] = job.id
            retry_meta['retry_scheduled_at'] = datetime.utcnow().isoformat()
            
            # Schedule for later execution
            self.dlq_retry.enqueue_in(
                timedelta(seconds=delay),
                job.func,
                *job.args,
                timeout=job.timeout,
                meta=retry_meta,
                **job.kwargs
            )
            
            return {
                'retry_scheduled': True,
                'retry_delay': delay,
                'retry_count': retry_meta['retry_count']
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule retry for {job.id}: {str(e)}")
            return {'retry_scheduled': False, 'error': str(e)}

    def _move_to_dead_letter_queue(self, task_error: TaskError, job: Job) -> Dict[str, Any]:
        """Move failed task to appropriate dead letter queue."""
        try:
            # Determine which DLQ to use
            if task_error.severity == ErrorSeverity.CRITICAL:
                dlq = self.dlq_investigate
                dlq_type = 'investigate'
            elif task_error.retry_count >= 3:
                dlq = self.dlq_retry
                dlq_type = 'retry_exhausted'
            elif not task_error.is_retryable:
                dlq = self.dlq_permanent
                dlq_type = 'permanent_failure'
            else:
                dlq = self.dlq_investigate
                dlq_type = 'investigate'
            
            # Add job to dead letter queue with metadata
            dlq_meta = {
                'original_task_id': task_error.task_id,
                'error_type': task_error.error_type,
                'error_message': task_error.error_message,
                'failed_at': task_error.occurred_at.isoformat(),
                'retry_count': task_error.retry_count,
                'severity': task_error.severity.value,
                'dlq_type': dlq_type,
                'job_data': {
                    'function': job.func_name,
                    'args': job.args,
                    'kwargs': job.kwargs,
                    'timeout': job.timeout
                }
            }
            
            dlq.enqueue(
                'app.core.task_error_handler.dead_letter_placeholder',
                dlq_meta,
                timeout=300
            )
            
            return {
                'moved_to_dlq': True,
                'dlq_type': dlq_type
            }
            
        except Exception as e:
            logger.error(f"Failed to move task {task_error.task_id} to DLQ: {str(e)}")
            return {'moved_to_dlq': False, 'error': str(e)}

    def _store_error_record(self, task_error: TaskError) -> None:
        """Store error record in Redis."""
        try:
            redis_key = f"task_error:{task_error.task_id}"
            self.redis_conn.setex(
                redis_key,
                30 * 24 * 3600,  # 30 days TTL
                json.dumps(asdict(task_error), default=str)
            )
        except Exception as e:
            logger.error(f"Failed to store error record: {str(e)}")

    def _get_error_records_since(self, cutoff_time: datetime) -> List[TaskError]:
        """Get all error records since cutoff time."""
        records = []
        
        try:
            cursor = 0
            while True:
                cursor, keys = self.redis_conn.scan(
                    cursor=cursor,
                    match="task_error:*",
                    count=100
                )
                
                for key in keys:
                    try:
                        data = self.redis_conn.get(key)
                        if data:
                            error_dict = json.loads(data)
                            occurred_at = datetime.fromisoformat(error_dict['occurred_at'])
                            
                            if occurred_at >= cutoff_time:
                                error_dict['occurred_at'] = occurred_at
                                error_dict['severity'] = ErrorSeverity(error_dict['severity'])
                                records.append(TaskError(**error_dict))
                    except Exception as e:
                        logger.warning(f"Failed to parse error record {key}: {str(e)}")
                
                if cursor == 0:
                    break
        
        except Exception as e:
            logger.error(f"Failed to get error records: {str(e)}")
        
        return records

    def _update_error_statistics(self, task_error: TaskError) -> None:
        """Update error statistics counters."""
        try:
            # Update daily error counters
            today = datetime.utcnow().date().isoformat()
            
            # Overall error count
            self.redis_conn.hincrby(f"error_stats:{today}", "total_errors", 1)
            
            # By error type
            self.redis_conn.hincrby(f"error_stats:{today}", f"by_type:{task_error.error_type}", 1)
            
            # By function
            self.redis_conn.hincrby(f"error_stats:{today}", f"by_function:{task_error.function_name}", 1)
            
            # By severity
            self.redis_conn.hincrby(f"error_stats:{today}", f"by_severity:{task_error.severity.value}", 1)
            
            # Set TTL for stats (keep for 90 days)
            self.redis_conn.expire(f"error_stats:{today}", 90 * 24 * 3600)
            
        except Exception as e:
            logger.error(f"Failed to update error statistics: {str(e)}")

    def _check_alert_conditions(self, task_error: TaskError) -> None:
        """Check if error conditions warrant alerts."""
        try:
            # Critical errors always trigger alerts
            if task_error.severity == ErrorSeverity.CRITICAL:
                self._send_error_alert(task_error, "Critical task failure detected")
            
            # Check error rate thresholds
            today = datetime.utcnow().date().isoformat()
            total_errors = int(self.redis_conn.hget(f"error_stats:{today}", "total_errors") or 0)
            
            if total_errors > 100:  # More than 100 errors in a day
                self._send_error_alert(task_error, f"High error rate: {total_errors} errors today")
        
        except Exception as e:
            logger.error(f"Failed to check alert conditions: {str(e)}")

    def _send_error_alert(self, task_error: TaskError, message: str) -> None:
        """Send error alert (placeholder - implement with your alerting system)."""
        logger.error(
            f"ALERT: {message}",
            extra={
                'alert_type': 'task_error',
                'task_id': task_error.task_id,
                'function_name': task_error.function_name,
                'error_type': task_error.error_type,
                'severity': task_error.severity.value
            }
        )

    def _get_dlq_job_summaries(self, dlq: Queue) -> List[Dict[str, Any]]:
        """Get summaries of jobs in a dead letter queue."""
        summaries = []
        
        try:
            for job in dlq.jobs:
                try:
                    summaries.append({
                        'job_id': job.id,
                        'function_name': job.func_name,
                        'failed_at': job.meta.get('failed_at') if job.meta else None,
                        'error_type': job.meta.get('error_type') if job.meta else None,
                        'retry_count': job.meta.get('retry_count', 0) if job.meta else 0
                    })
                except Exception as e:
                    logger.warning(f"Failed to get job summary: {str(e)}")
        
        except Exception as e:
            logger.error(f"Failed to get DLQ job summaries: {str(e)}")
        
        return summaries

    def _calculate_error_trends(self, error_records: List[TaskError]) -> Dict[str, Any]:
        """Calculate error trends from error records."""
        if not error_records:
            return {}
        
        # Group errors by hour
        hourly_counts = {}
        for error in error_records:
            hour_key = error.occurred_at.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
        
        # Calculate trend
        if len(hourly_counts) >= 2:
            hours = sorted(hourly_counts.keys())
            first_half = sum(hourly_counts[h] for h in hours[:len(hours)//2])
            second_half = sum(hourly_counts[h] for h in hours[len(hours)//2:])
            
            if second_half > first_half * 1.5:
                trend = 'increasing'
            elif second_half < first_half * 0.5:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'trend': trend,
            'hourly_distribution': {h.isoformat(): count for h, count in hourly_counts.items()},
            'peak_hour': max(hourly_counts, key=hourly_counts.get).isoformat() if hourly_counts else None
        }


# Global error handler instance
task_error_handler = None


def initialize_error_handler(redis_conn: redis.Redis) -> TaskErrorHandler:
    """Initialize global error handler."""
    global task_error_handler
    if task_error_handler is None:
        task_error_handler = TaskErrorHandler(redis_conn)
        logger.info("Global task error handler initialized")
    return task_error_handler


def get_error_handler() -> Optional[TaskErrorHandler]:
    """Get global error handler instance."""
    return task_error_handler


def dead_letter_placeholder(job_data: Dict[str, Any], **kwargs):
    """Placeholder function for dead letter queue jobs."""
    logger.info(f"Dead letter job executed: {job_data}")
    return job_data