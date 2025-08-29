"""
Enhanced task metrics collection for production monitoring.
Provides detailed metrics for task queue performance and business operations.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import contextmanager
import threading
from collections import defaultdict, Counter

from prometheus_client import Counter as PrometheusCounter, Histogram, Gauge, CollectorRegistry
import redis

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class TaskMetrics:
    """Enhanced task metrics collection with Prometheus integration."""
    
    def __init__(self, redis_conn: redis.Redis):
        """Initialize task metrics collector."""
        self.redis_conn = redis_conn
        self._registry = CollectorRegistry()
        self._metrics_lock = threading.Lock()
        
        # Prometheus metrics
        self.task_counter = PrometheusCounter(
            'rq_jobs_total',
            'Total number of RQ jobs processed',
            ['queue', 'function', 'status'],
            registry=self._registry
        )
        
        self.task_duration = Histogram(
            'rq_task_duration_seconds',
            'Time spent processing RQ tasks',
            ['queue', 'function'],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0),
            registry=self._registry
        )
        
        self.task_wait_duration = Histogram(
            'rq_task_wait_duration_seconds',
            'Time tasks spend waiting in queue',
            ['queue', 'priority'],
            buckets=(0.1, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0),
            registry=self._registry
        )
        
        self.queue_depth = Gauge(
            'rq_queue_depth',
            'Number of jobs in queue',
            ['queue'],
            registry=self._registry
        )
        
        self.workers_gauge = Gauge(
            'rq_workers_total',
            'Total number of workers',
            ['state'],
            registry=self._registry
        )
        
        self.worker_memory = Gauge(
            'rq_worker_memory_bytes',
            'Worker memory usage in bytes',
            ['worker_id'],
            registry=self._registry
        )
        
        # Financial operation specific metrics
        self.financial_operation_counter = PrometheusCounter(
            'mita_financial_operations_total',
            'Total financial operations processed',
            ['operation_type', 'status', 'user_tier'],
            registry=self._registry
        )
        
        self.financial_operation_duration = Histogram(
            'mita_financial_operation_duration_seconds',
            'Duration of financial operations',
            ['operation_type', 'user_tier'],
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0),
            registry=self._registry
        )
        
        # Revenue impact metrics
        self.ocr_processing_counter = PrometheusCounter(
            'mita_ocr_processing_total',
            'OCR processing requests',
            ['user_type', 'status'],
            registry=self._registry
        )
        
        self.ai_analysis_counter = PrometheusCounter(
            'mita_ai_analysis_total',
            'AI analysis requests',
            ['analysis_type', 'status'],
            registry=self._registry
        )
        
        # Business metrics
        self.revenue_impact = Counter(
            'mita_revenue_impact_operations_total',
            'Operations that directly impact revenue',
            ['operation', 'impact_type'],
            registry=self._registry
        )
        
        # System health metrics
        self.error_counter = PrometheusCounter(
            'rq_errors_total',
            'Total task errors by type',
            ['error_type', 'function', 'queue'],
            registry=self._registry
        )
        
        # Start metrics collection thread
        self._collection_thread = None
        self._stop_collection = False
        
        if settings.ENABLE_TASK_METRICS:
            self.start_collection()
    
    def start_collection(self):
        """Start periodic metrics collection."""
        if self._collection_thread and self._collection_thread.is_alive():
            return
        
        def collect_metrics():
            while not self._stop_collection:
                try:
                    self.collect_queue_metrics()
                    self.collect_worker_metrics()
                    time.sleep(settings.METRICS_COLLECTION_INTERVAL)
                except Exception as e:
                    logger.error(f"Error collecting metrics: {e}")
                    time.sleep(10)  # Shorter sleep on error
        
        self._collection_thread = threading.Thread(target=collect_metrics, daemon=True)
        self._collection_thread.start()
        logger.info("Task metrics collection started")
    
    def stop_collection(self):
        """Stop metrics collection."""
        self._stop_collection = True
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        logger.info("Task metrics collection stopped")
    
    def collect_queue_metrics(self):
        """Collect queue depth and status metrics."""
        try:
            from app.core.task_queue import get_task_queue
            
            # Get queue statistics
            stats = get_task_queue().get_queue_stats()
            
            with self._metrics_lock:
                # Update queue depth metrics
                for queue_name, queue_stats in stats.items():
                    if isinstance(queue_stats, dict) and 'length' in queue_stats:
                        self.queue_depth.labels(queue=queue_name).set(queue_stats['length'])
                
                # Update worker metrics
                worker_stats = stats.get('workers', {})
                for state in ['total', 'active', 'idle']:
                    if state in worker_stats:
                        self.workers_gauge.labels(state=state).set(worker_stats[state])
                        
        except Exception as e:
            logger.error(f"Error collecting queue metrics: {e}")
    
    def collect_worker_metrics(self):
        """Collect worker-specific metrics."""
        try:
            # Get worker health data from Redis
            worker_keys = self.redis_conn.keys("worker_health:*")
            
            with self._metrics_lock:
                for key in worker_keys:
                    try:
                        worker_id = key.decode().split(":")[-1]
                        health_data = self.redis_conn.get(key)
                        if health_data:
                            # Parse worker health data (stored as string representation)
                            # In production, you'd want to store this as JSON
                            # For now, we'll extract memory info if available
                            if "memory_usage" in health_data.decode():
                                # This is a simplified extraction
                                # In production, parse the actual JSON data
                                pass
                    except Exception as e:
                        logger.debug(f"Error parsing worker health data for {key}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error collecting worker metrics: {e}")
    
    @contextmanager
    def time_task(self, queue: str, function: str):
        """Context manager to time task execution."""
        start_time = time.time()
        try:
            yield
            # Task succeeded
            duration = time.time() - start_time
            with self._metrics_lock:
                self.task_duration.labels(queue=queue, function=function).observe(duration)
                self.task_counter.labels(queue=queue, function=function, status='success').inc()
        except Exception as e:
            # Task failed
            duration = time.time() - start_time
            with self._metrics_lock:
                self.task_duration.labels(queue=queue, function=function).observe(duration)
                self.task_counter.labels(queue=queue, function=function, status='failed').inc()
                self.error_counter.labels(
                    error_type=type(e).__name__,
                    function=function,
                    queue=queue
                ).inc()
            raise
    
    def record_task_wait_time(self, queue: str, priority: str, wait_seconds: float):
        """Record task wait time in queue."""
        with self._metrics_lock:
            self.task_wait_duration.labels(queue=queue, priority=priority).observe(wait_seconds)
    
    def record_financial_operation(
        self,
        operation_type: str,
        status: str,
        user_tier: str = "free",
        duration_seconds: Optional[float] = None
    ):
        """Record financial operation metrics."""
        with self._metrics_lock:
            self.financial_operation_counter.labels(
                operation_type=operation_type,
                status=status,
                user_tier=user_tier
            ).inc()
            
            if duration_seconds is not None:
                self.financial_operation_duration.labels(
                    operation_type=operation_type,
                    user_tier=user_tier
                ).observe(duration_seconds)
    
    def record_ocr_processing(self, user_type: str, status: str):
        """Record OCR processing event."""
        with self._metrics_lock:
            self.ocr_processing_counter.labels(user_type=user_type, status=status).inc()
            
            # Track revenue impact
            if user_type == "premium":
                self.revenue_impact.labels(operation="ocr", impact_type="premium_feature").inc()
    
    def record_ai_analysis(self, analysis_type: str, status: str):
        """Record AI analysis event."""
        with self._metrics_lock:
            self.ai_analysis_counter.labels(analysis_type=analysis_type, status=status).inc()
            
            # Track computational cost
            if analysis_type in ["comprehensive", "personalized"]:
                self.revenue_impact.labels(operation="ai_analysis", impact_type="high_cost").inc()
    
    def record_worker_memory(self, worker_id: str, memory_bytes: int):
        """Record worker memory usage."""
        with self._metrics_lock:
            self.worker_memory.labels(worker_id=worker_id).set(memory_bytes)
    
    def get_registry(self) -> CollectorRegistry:
        """Get Prometheus registry for metrics endpoint."""
        return self._registry
    
    def get_business_metrics_summary(self) -> Dict[str, Any]:
        """Get business-relevant metrics summary."""
        try:
            from app.core.task_queue import get_task_queue
            stats = get_task_queue().get_queue_stats()
            
            # Calculate key business metrics
            total_queued = sum(
                queue_data.get('length', 0)
                for queue_data in stats.values()
                if isinstance(queue_data, dict)
            )
            
            total_failed = sum(
                queue_data.get('failed_job_count', 0)
                for queue_data in stats.values()
                if isinstance(queue_data, dict)
            )
            
            workers = stats.get('workers', {})
            worker_utilization = 0
            if workers.get('total', 0) > 0:
                worker_utilization = workers.get('active', 0) / workers.get('total', 1)
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'queue_health': {
                    'total_queued_tasks': total_queued,
                    'total_failed_tasks': total_failed,
                    'worker_utilization': round(worker_utilization * 100, 1),
                    'active_workers': workers.get('active', 0),
                    'total_workers': workers.get('total', 0)
                },
                'financial_operations': {
                    'ocr_queue_depth': stats.get('high', {}).get('length', 0),
                    'ai_analysis_queue_depth': stats.get('default', {}).get('length', 0),
                    'budget_queue_depth': stats.get('normal', {}).get('length', 0)
                },
                'system_status': 'healthy' if total_queued < 50 and total_failed < 10 else 'degraded'
            }
            
        except Exception as e:
            logger.error(f"Error generating business metrics summary: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'system_status': 'unknown'
            }


# Global metrics instance
_task_metrics: Optional[TaskMetrics] = None


def get_task_metrics() -> TaskMetrics:
    """Get or create global task metrics instance."""
    global _task_metrics
    
    if _task_metrics is None:
        try:
            from app.core.task_queue import get_task_queue
            _task_metrics = TaskMetrics(get_task_queue().redis_conn)
        except Exception as e:
            logger.error(f"Failed to initialize task metrics: {e}")
            # Return a no-op metrics instance
            class NoOpMetrics:
                def __getattr__(self, name):
                    return lambda *args, **kwargs: None
                
                def time_task(self, *args, **kwargs):
                    from contextlib import nullcontext
                    return nullcontext()
                
                def get_registry(self):
                    return CollectorRegistry()
                
                def get_business_metrics_summary(self):
                    return {'error': 'Metrics not available'}
            
            _task_metrics = NoOpMetrics()
    
    return _task_metrics


# Convenience functions
def time_task(queue: str, function: str):
    """Context manager to time task execution."""
    return get_task_metrics().time_task(queue, function)


def record_financial_operation(operation_type: str, status: str, user_tier: str = "free", duration_seconds: Optional[float] = None):
    """Record financial operation metrics."""
    return get_task_metrics().record_financial_operation(operation_type, status, user_tier, duration_seconds)


def record_ocr_processing(user_type: str, status: str):
    """Record OCR processing event."""
    return get_task_metrics().record_ocr_processing(user_type, status)


def record_ai_analysis(analysis_type: str, status: str):
    """Record AI analysis event."""
    return get_task_metrics().record_ai_analysis(analysis_type, status)