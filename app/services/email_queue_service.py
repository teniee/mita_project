"""
Email Queue Service - Enterprise Email Queue and Retry System
Handles email queuing, retry logic, delivery tracking, and monitoring
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, text
import redis.asyncio as redis

from app.core.config import settings
from app.core.external_services import RedisService
from app.services.email_service import EmailService, EmailType, EmailPriority, EmailDeliveryResult
from app.db.models.notification_log import NotificationLog

logger = logging.getLogger(__name__)


class EmailQueueStatus(Enum):
    """Email queue job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass
class EmailQueueJob:
    """Email queue job data structure"""
    id: str
    to_email: str
    email_type: EmailType
    variables: Dict[str, Any]
    priority: EmailPriority
    user_id: Optional[str]
    status: EmailQueueStatus
    retry_count: int
    max_retries: int
    created_at: datetime
    scheduled_at: datetime
    last_attempt: Optional[datetime]
    last_error: Optional[str]
    delivery_result: Optional[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Handle enum serialization
        data['email_type'] = self.email_type.value
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        # Handle datetime serialization
        for field in ['created_at', 'scheduled_at', 'last_attempt']:
            if data[field]:
                data[field] = data[field].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailQueueJob':
        """Create from dictionary"""
        # Handle enum deserialization
        data['email_type'] = EmailType(data['email_type'])
        data['priority'] = EmailPriority(data['priority'])
        data['status'] = EmailQueueStatus(data['status'])
        # Handle datetime deserialization
        for field in ['created_at', 'scheduled_at', 'last_attempt']:
            if data[field]:
                data[field] = datetime.fromisoformat(data[field])
        return cls(**data)


class EmailQueueMetrics:
    """Email queue metrics tracking"""
    
    def __init__(self):
        self.total_jobs_created = 0
        self.total_jobs_processed = 0
        self.total_jobs_failed = 0
        self.total_jobs_retried = 0
        self.total_jobs_dead_letter = 0
        self.current_queue_size = 0
        self.average_processing_time = 0.0
        self.success_rate = 0.0
        self.last_updated = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_jobs_created': self.total_jobs_created,
            'total_jobs_processed': self.total_jobs_processed,
            'total_jobs_failed': self.total_jobs_failed,
            'total_jobs_retried': self.total_jobs_retried,
            'total_jobs_dead_letter': self.total_jobs_dead_letter,
            'current_queue_size': self.current_queue_size,
            'average_processing_time': self.average_processing_time,
            'success_rate': self.success_rate,
            'last_updated': self.last_updated.isoformat()
        }


class EmailQueueService:
    """Enterprise email queue service with Redis backend"""
    
    def __init__(self):
        self.redis_service = RedisService()
        self.email_service = EmailService()
        self.metrics = EmailQueueMetrics()
        
        # Queue configuration
        self.queue_key = "mita:email:queue"
        self.retry_queue_key = "mita:email:retry_queue"
        self.dead_letter_queue_key = "mita:email:dead_letter"
        self.processing_key = "mita:email:processing"
        self.metrics_key = "mita:email:metrics"
        
        # Configuration from environment
        self.max_retries = int(os.getenv('EMAIL_MAX_RETRIES', '3'))
        self.retry_delays = [300, 900, 3600]  # 5min, 15min, 1hour
        self.max_processing_time = int(os.getenv('EMAIL_MAX_PROCESSING_TIME', '300'))  # 5 minutes
        self.batch_size = int(os.getenv('EMAIL_BATCH_SIZE', '10'))
        self.dead_letter_retention_days = int(os.getenv('EMAIL_DEAD_LETTER_RETENTION_DAYS', '7'))
        
        # Worker state
        self.is_worker_running = False
        self.worker_task: Optional[asyncio.Task] = None
        
        logger.info("Email queue service initialized")
    
    async def get_redis_client(self):
        """Get Redis client"""
        return await self.redis_service.get_client()
    
    async def enqueue_email(
        self,
        to_email: str,
        email_type: EmailType,
        variables: Dict[str, Any],
        priority: EmailPriority = EmailPriority.NORMAL,
        user_id: Optional[str] = None,
        delay_seconds: int = 0
    ) -> str:
        """Enqueue email for processing"""
        
        job_id = str(uuid.uuid4())
        scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        
        job = EmailQueueJob(
            id=job_id,
            to_email=to_email,
            email_type=email_type,
            variables=variables,
            priority=priority,
            user_id=user_id,
            status=EmailQueueStatus.PENDING,
            retry_count=0,
            max_retries=self.max_retries,
            created_at=datetime.now(timezone.utc),
            scheduled_at=scheduled_at,
            last_attempt=None,
            last_error=None,
            delivery_result=None
        )
        
        redis_client = await self.get_redis_client()
        if not redis_client:
            logger.error("Redis not available, falling back to immediate processing")
            # Fallback to immediate processing if Redis is not available
            return await self._process_email_immediately(job)
        
        try:
            # Store job data
            await redis_client.hset(
                f"{self.queue_key}:jobs",
                job_id,
                json.dumps(job.to_dict())
            )
            
            # Add to priority queue with score based on priority and scheduled time
            priority_score = self._calculate_priority_score(priority, scheduled_at)
            await redis_client.zadd(
                self.queue_key,
                {job_id: priority_score}
            )
            
            # Update metrics
            self.metrics.total_jobs_created += 1
            self.metrics.current_queue_size += 1
            await self._update_metrics()
            
            logger.info(f"Email job {job_id} enqueued for {to_email} (type: {email_type.value})")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to enqueue email job: {e}")
            # Fallback to immediate processing
            return await self._process_email_immediately(job)
        finally:
            await redis_client.aclose()
    
    def _calculate_priority_score(self, priority: EmailPriority, scheduled_at: datetime) -> float:
        """Calculate priority score for Redis sorted set"""
        # Base score from scheduled time (timestamp)
        base_score = scheduled_at.timestamp()
        
        # Priority adjustment (lower scores = higher priority)
        priority_adjustments = {
            EmailPriority.URGENT: -10000,
            EmailPriority.HIGH: -1000,
            EmailPriority.NORMAL: 0,
            EmailPriority.LOW: 1000
        }
        
        return base_score + priority_adjustments.get(priority, 0)
    
    async def _process_email_immediately(self, job: EmailQueueJob) -> str:
        """Fallback: Process email immediately without queue"""
        try:
            result = await self.email_service.send_email(
                to_email=job.to_email,
                email_type=job.email_type,
                variables=job.variables,
                priority=job.priority,
                user_id=job.user_id
            )
            
            logger.info(f"Email processed immediately: {job.id} - Success: {result.success}")
            return job.id
            
        except Exception as e:
            logger.error(f"Immediate email processing failed: {e}")
            raise
    
    async def start_worker(self):
        """Start the email queue worker"""
        if self.is_worker_running:
            logger.warning("Email queue worker is already running")
            return
        
        self.is_worker_running = True
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Email queue worker started")
    
    async def stop_worker(self):
        """Stop the email queue worker"""
        if not self.is_worker_running:
            return
        
        self.is_worker_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Email queue worker stopped")
    
    async def _worker_loop(self):
        """Main worker loop"""
        logger.info("Email queue worker loop started")
        
        while self.is_worker_running:
            try:
                # Process batch of jobs
                processed_count = await self._process_batch()
                
                # Process retry queue
                retry_count = await self._process_retry_queue()
                
                # Clean up old jobs
                await self._cleanup_old_jobs()
                
                # Update metrics
                await self._update_metrics()
                
                # Sleep if no jobs were processed
                if processed_count == 0 and retry_count == 0:
                    await asyncio.sleep(1)  # Short sleep when idle
                else:
                    await asyncio.sleep(0.1)  # Brief pause when active
                    
            except Exception as e:
                logger.error(f"Email queue worker error: {e}")
                await asyncio.sleep(5)  # Longer sleep on error
    
    async def _process_batch(self) -> int:
        """Process a batch of email jobs"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return 0
        
        try:
            # Get batch of jobs ready for processing
            now_timestamp = datetime.now(timezone.utc).timestamp()
            job_ids = await redis_client.zrangebyscore(
                self.queue_key,
                0,
                now_timestamp,
                start=0,
                num=self.batch_size
            )
            
            if not job_ids:
                return 0
            
            processed_count = 0
            for job_id in job_ids:
                try:
                    # Move job to processing queue
                    job_data = await redis_client.hget(f"{self.queue_key}:jobs", job_id)
                    if not job_data:
                        await redis_client.zrem(self.queue_key, job_id)
                        continue
                    
                    # Mark as processing
                    await redis_client.zadd(
                        self.processing_key,
                        {job_id: datetime.now(timezone.utc).timestamp()}
                    )
                    await redis_client.zrem(self.queue_key, job_id)
                    
                    # Process the job
                    success = await self._process_email_job(job_id, job_data)
                    if success:
                        processed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing email job {job_id}: {e}")
                    await self._handle_job_error(job_id, str(e))
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return 0
        finally:
            await redis_client.aclose()
    
    async def _process_email_job(self, job_id: str, job_data: str) -> bool:
        """Process individual email job"""
        try:
            job = EmailQueueJob.from_dict(json.loads(job_data))
            job.status = EmailQueueStatus.PROCESSING
            job.last_attempt = datetime.now(timezone.utc)
            
            # Send email
            result = await self.email_service.send_email(
                to_email=job.to_email,
                email_type=job.email_type,
                variables=job.variables,
                priority=job.priority,
                user_id=job.user_id
            )
            
            # Update job with result
            job.delivery_result = {
                'success': result.success,
                'message_id': result.message_id,
                'error_message': result.error_message,
                'provider': result.provider,
                'sent_at': result.sent_at.isoformat() if result.sent_at else None
            }
            
            if result.success:
                job.status = EmailQueueStatus.SENT
                await self._complete_job(job_id, job)
                logger.info(f"Email job {job_id} completed successfully")
                return True
            else:
                job.last_error = result.error_message
                await self._handle_job_failure(job_id, job)
                return False
                
        except Exception as e:
            logger.error(f"Email job processing error: {e}")
            await self._handle_job_error(job_id, str(e))
            return False
    
    async def _complete_job(self, job_id: str, job: EmailQueueJob):
        """Mark job as completed"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return
        
        try:
            # Update job data
            await redis_client.hset(
                f"{self.queue_key}:jobs",
                job_id,
                json.dumps(job.to_dict())
            )
            
            # Remove from processing queue
            await redis_client.zrem(self.processing_key, job_id)
            
            # Update metrics
            self.metrics.total_jobs_processed += 1
            self.metrics.current_queue_size = max(0, self.metrics.current_queue_size - 1)
            
        except Exception as e:
            logger.error(f"Error completing job {job_id}: {e}")
        finally:
            await redis_client.aclose()
    
    async def _handle_job_failure(self, job_id: str, job: EmailQueueJob):
        """Handle job failure with retry logic"""
        job.retry_count += 1
        
        if job.retry_count <= job.max_retries:
            # Schedule for retry
            job.status = EmailQueueStatus.RETRY
            delay_index = min(job.retry_count - 1, len(self.retry_delays) - 1)
            retry_delay = self.retry_delays[delay_index]
            job.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            
            await self._enqueue_for_retry(job_id, job)
            self.metrics.total_jobs_retried += 1
            
            logger.info(f"Email job {job_id} scheduled for retry {job.retry_count}/{job.max_retries}")
        else:
            # Move to dead letter queue
            job.status = EmailQueueStatus.DEAD_LETTER
            await self._move_to_dead_letter_queue(job_id, job)
            self.metrics.total_jobs_dead_letter += 1
            
            logger.error(f"Email job {job_id} moved to dead letter queue after {job.retry_count} attempts")
    
    async def _handle_job_error(self, job_id: str, error_message: str):
        """Handle job processing error"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return
        
        try:
            # Get job data
            job_data = await redis_client.hget(f"{self.queue_key}:jobs", job_id)
            if job_data:
                job = EmailQueueJob.from_dict(json.loads(job_data))
                job.last_error = error_message
                await self._handle_job_failure(job_id, job)
            
            # Remove from processing queue
            await redis_client.zrem(self.processing_key, job_id)
            
        except Exception as e:
            logger.error(f"Error handling job error for {job_id}: {e}")
        finally:
            await redis_client.aclose()
    
    async def _enqueue_for_retry(self, job_id: str, job: EmailQueueJob):
        """Enqueue job for retry"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return
        
        try:
            # Update job data
            await redis_client.hset(
                f"{self.queue_key}:jobs",
                job_id,
                json.dumps(job.to_dict())
            )
            
            # Add to retry queue with scheduled time
            await redis_client.zadd(
                self.retry_queue_key,
                {job_id: job.scheduled_at.timestamp()}
            )
            
            # Remove from processing queue
            await redis_client.zrem(self.processing_key, job_id)
            
        except Exception as e:
            logger.error(f"Error enqueueing retry for {job_id}: {e}")
        finally:
            await redis_client.aclose()
    
    async def _move_to_dead_letter_queue(self, job_id: str, job: EmailQueueJob):
        """Move job to dead letter queue"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return
        
        try:
            # Update job data
            await redis_client.hset(
                f"{self.queue_key}:jobs",
                job_id,
                json.dumps(job.to_dict())
            )
            
            # Add to dead letter queue
            await redis_client.zadd(
                self.dead_letter_queue_key,
                {job_id: datetime.now(timezone.utc).timestamp()}
            )
            
            # Remove from processing queue
            await redis_client.zrem(self.processing_key, job_id)
            
            # Update metrics
            self.metrics.current_queue_size = max(0, self.metrics.current_queue_size - 1)
            
        except Exception as e:
            logger.error(f"Error moving job to dead letter queue {job_id}: {e}")
        finally:
            await redis_client.aclose()
    
    async def _process_retry_queue(self) -> int:
        """Process retry queue"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return 0
        
        try:
            # Get jobs ready for retry
            now_timestamp = datetime.now(timezone.utc).timestamp()
            job_ids = await redis_client.zrangebyscore(
                self.retry_queue_key,
                0,
                now_timestamp,
                start=0,
                num=self.batch_size
            )
            
            processed_count = 0
            for job_id in job_ids:
                try:
                    # Move back to main queue
                    job_data = await redis_client.hget(f"{self.queue_key}:jobs", job_id)
                    if job_data:
                        job = EmailQueueJob.from_dict(json.loads(job_data))
                        job.status = EmailQueueStatus.PENDING
                        
                        # Calculate new priority score
                        priority_score = self._calculate_priority_score(job.priority, job.scheduled_at)
                        
                        # Move to main queue
                        await redis_client.zadd(self.queue_key, {job_id: priority_score})
                        await redis_client.zrem(self.retry_queue_key, job_id)
                        
                        # Update job data
                        await redis_client.hset(
                            f"{self.queue_key}:jobs",
                            job_id,
                            json.dumps(job.to_dict())
                        )
                        
                        processed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error processing retry job {job_id}: {e}")
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Retry queue processing error: {e}")
            return 0
        finally:
            await redis_client.aclose()
    
    async def _cleanup_old_jobs(self):
        """Clean up old completed and dead letter jobs"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return
        
        try:
            # Clean up dead letter queue (older than retention days)
            cutoff_timestamp = (
                datetime.now(timezone.utc) - timedelta(days=self.dead_letter_retention_days)
            ).timestamp()
            
            old_jobs = await redis_client.zrangebyscore(
                self.dead_letter_queue_key,
                0,
                cutoff_timestamp
            )
            
            if old_jobs:
                # Remove from dead letter queue
                await redis_client.zremrangebyscore(
                    self.dead_letter_queue_key,
                    0,
                    cutoff_timestamp
                )
                
                # Remove job data
                if old_jobs:
                    await redis_client.hdel(f"{self.queue_key}:jobs", *old_jobs)
                
                logger.info(f"Cleaned up {len(old_jobs)} old dead letter jobs")
            
            # Clean up stuck processing jobs (older than max processing time)
            processing_cutoff = (
                datetime.now(timezone.utc) - timedelta(seconds=self.max_processing_time)
            ).timestamp()
            
            stuck_jobs = await redis_client.zrangebyscore(
                self.processing_key,
                0,
                processing_cutoff
            )
            
            for job_id in stuck_jobs:
                logger.warning(f"Found stuck processing job: {job_id}")
                await self._handle_job_error(job_id, "Job stuck in processing state")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        finally:
            await redis_client.aclose()
    
    async def _update_metrics(self):
        """Update queue metrics"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return
        
        try:
            # Update current queue size
            queue_size = await redis_client.zcard(self.queue_key)
            retry_size = await redis_client.zcard(self.retry_queue_key)
            processing_size = await redis_client.zcard(self.processing_key)
            
            self.metrics.current_queue_size = queue_size + retry_size + processing_size
            
            # Calculate success rate
            total_processed = self.metrics.total_jobs_processed + self.metrics.total_jobs_failed
            if total_processed > 0:
                self.metrics.success_rate = self.metrics.total_jobs_processed / total_processed
            
            self.metrics.last_updated = datetime.now(timezone.utc)
            
            # Store metrics in Redis
            await redis_client.set(
                self.metrics_key,
                json.dumps(self.metrics.to_dict()),
                ex=3600  # Expire in 1 hour
            )
            
        except Exception as e:
            logger.error(f"Metrics update error: {e}")
        finally:
            await redis_client.aclose()
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return {
                'status': 'redis_unavailable',
                'queue_size': 0,
                'retry_queue_size': 0,
                'processing_size': 0,
                'dead_letter_size': 0,
                'metrics': self.metrics.to_dict()
            }
        
        try:
            queue_size = await redis_client.zcard(self.queue_key)
            retry_size = await redis_client.zcard(self.retry_queue_key)
            processing_size = await redis_client.zcard(self.processing_key)
            dead_letter_size = await redis_client.zcard(self.dead_letter_queue_key)
            
            return {
                'status': 'healthy' if self.is_worker_running else 'worker_stopped',
                'worker_running': self.is_worker_running,
                'queue_size': queue_size,
                'retry_queue_size': retry_size,
                'processing_size': processing_size,
                'dead_letter_size': dead_letter_size,
                'metrics': self.metrics.to_dict()
            }
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'metrics': self.metrics.to_dict()
            }
        finally:
            await redis_client.aclose()
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific job"""
        redis_client = await self.get_redis_client()
        if not redis_client:
            return None
        
        try:
            job_data = await redis_client.hget(f"{self.queue_key}:jobs", job_id)
            if job_data:
                job = EmailQueueJob.from_dict(json.loads(job_data))
                return job.to_dict()
            return None
            
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return None
        finally:
            await redis_client.aclose()


# Global email queue service instance
email_queue_service = EmailQueueService()


async def get_email_queue_service() -> EmailQueueService:
    """Get email queue service instance"""
    return email_queue_service


# Convenience functions
async def queue_email(
    to_email: str,
    email_type: EmailType,
    variables: Dict[str, Any],
    priority: EmailPriority = EmailPriority.NORMAL,
    user_id: Optional[str] = None,
    delay_seconds: int = 0
) -> str:
    """Queue email for processing"""
    return await email_queue_service.enqueue_email(
        to_email=to_email,
        email_type=email_type,
        variables=variables,
        priority=priority,
        user_id=user_id,
        delay_seconds=delay_seconds
    )


async def queue_welcome_email(user_email: str, user_name: str, user_id: str) -> str:
    """Queue welcome email"""
    variables = {
        'user_name': user_name,
        'email': user_email,
        'onboarding_link': 'https://app.mita.finance/onboarding'
    }
    
    return await queue_email(
        to_email=user_email,
        email_type=EmailType.WELCOME,
        variables=variables,
        priority=EmailPriority.HIGH,
        user_id=user_id
    )


async def queue_password_reset_email(user_email: str, user_name: str, reset_token: str, user_id: str) -> str:
    """Queue password reset email"""
    reset_link = f"https://app.mita.finance/reset-password?token={reset_token}&email={user_email}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    
    variables = {
        'user_name': user_name,
        'reset_link': reset_link,
        'expires_at': expires_at.strftime('%B %d, %Y at %I:%M %p UTC'),
        'email': user_email
    }
    
    return await queue_email(
        to_email=user_email,
        email_type=EmailType.PASSWORD_RESET,
        variables=variables,
        priority=EmailPriority.URGENT,
        user_id=user_id
    )