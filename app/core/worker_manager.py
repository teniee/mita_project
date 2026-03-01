"""
Production Worker Manager for MITA Task Queue System.
Provides advanced worker management, scaling, and monitoring capabilities.
"""

import os
import signal
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

import redis
from rq import Worker, Queue
# RQ 1.15.1 doesn't have middleware module - using callbacks instead

from app.core.logger import get_logger

logger = get_logger(__name__)


class WorkerState(str, Enum):
    """Worker state enumeration."""
    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class WorkerConfig:
    """Worker configuration settings."""
    worker_id: str
    queues: List[str]
    max_jobs: int = 100
    job_timeout: int = 600  # 10 minutes default
    heartbeat_interval: int = 30  # seconds
    burst_mode: bool = False
    exception_handlers: List[Callable] = None
    # Middleware functionality replaced with callbacks in RQ 1.15.1

    def __post_init__(self):
        if self.exception_handlers is None:
            self.exception_handlers = []


class MitaWorker(Worker):
    """Enhanced RQ Worker with monitoring and health checks."""
    
    def __init__(self, config: WorkerConfig, redis_conn: redis.Redis):
        """Initialize the MITA worker."""
        self.config = config
        self.redis_conn = redis_conn
        
        # Initialize queues
        queues = [Queue(name, connection=redis_conn) for name in config.queues]
        
        # Initialize parent Worker
        super().__init__(
            queues=queues,
            connection=redis_conn,
            name=config.worker_id,
            default_result_ttl=24 * 3600,  # 24 hours
            exception_handlers=config.exception_handlers
        )
        
        # Note: Middleware functionality replaced with job callbacks in RQ 1.15.1
        
        # Worker state tracking
        self.state = WorkerState.STARTING
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.start_time = None
        self.last_heartbeat = None
        
        # Health monitoring
        self.health_check_thread = None
        self.shutdown_requested = False
        
        logger.info(f"MITA Worker initialized: {config.worker_id}")

    def work(self, burst: bool = None, logging_level: str = "INFO") -> bool:
        """Start worker with enhanced monitoring."""
        try:
            self.state = WorkerState.IDLE
            self.start_time = datetime.utcnow()
            self.last_heartbeat = datetime.utcnow()
            
            # Start health monitoring thread
            self._start_health_monitoring()
            
            logger.info(f"Worker {self.config.worker_id} starting work")
            
            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            # Start the actual work loop
            burst_mode = burst if burst is not None else self.config.burst_mode
            result = super().work(burst=burst_mode, logging_level=logging_level)
            
            return result
            
        except KeyboardInterrupt:
            logger.info(f"Worker {self.config.worker_id} received interrupt signal")
            self._graceful_shutdown()
            return False
        except Exception as e:
            logger.error(f"Worker {self.config.worker_id} encountered error: {str(e)}", exc_info=True)
            self.state = WorkerState.ERROR
            return False
        finally:
            self._cleanup()

    def perform_job(self, job, queue):
        """Override job performance to add monitoring."""
        self.state = WorkerState.BUSY
        self.last_heartbeat = datetime.utcnow()
        
        try:
            result = super().perform_job(job, queue)
            self.jobs_processed += 1
            
            logger.info(
                f"Worker {self.config.worker_id} completed job {job.id}",
                extra={
                    'worker_id': self.config.worker_id,
                    'job_id': job.id,
                    'queue': queue.name,
                    'jobs_processed': self.jobs_processed
                }
            )
            
            return result
            
        except Exception as e:
            self.jobs_failed += 1
            logger.error(
                f"Worker {self.config.worker_id} failed job {job.id}: {str(e)}",
                extra={
                    'worker_id': self.config.worker_id,
                    'job_id': job.id,
                    'queue': queue.name,
                    'jobs_failed': self.jobs_failed
                },
                exc_info=True
            )
            raise
        finally:
            self.state = WorkerState.IDLE
            self.last_heartbeat = datetime.utcnow()
            
            # Check if max jobs reached
            if self.jobs_processed >= self.config.max_jobs:
                logger.info(f"Worker {self.config.worker_id} reached max jobs limit, shutting down")
                self._graceful_shutdown()

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive worker health status."""
        now = datetime.utcnow()
        uptime = (now - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            'worker_id': self.config.worker_id,
            'state': self.state.value,
            'uptime_seconds': uptime,
            'jobs_processed': self.jobs_processed,
            'jobs_failed': self.jobs_failed,
            'success_rate': (
                (self.jobs_processed - self.jobs_failed) / max(self.jobs_processed, 1) * 100
            ),
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'queues': [q.name for q in self.queues],
            'current_job': getattr(self.get_current_job(), 'id', None),
            'memory_usage': self._get_memory_usage(),
            'config': {
                'max_jobs': self.config.max_jobs,
                'job_timeout': self.config.job_timeout,
                'heartbeat_interval': self.config.heartbeat_interval
            }
        }

    def _start_health_monitoring(self):
        """Start health monitoring thread."""
        def health_monitor():
            while not self.shutdown_requested:
                try:
                    # Update heartbeat
                    self.last_heartbeat = datetime.utcnow()
                    
                    # Store health status in Redis
                    health_key = f"worker_health:{self.config.worker_id}"
                    health_data = self.get_health_status()
                    self.redis_conn.setex(
                        health_key,
                        self.config.heartbeat_interval * 2,  # TTL
                        str(health_data)
                    )
                    
                    # Sleep until next heartbeat
                    time.sleep(self.config.heartbeat_interval)
                    
                except Exception as e:
                    logger.error(f"Health monitoring error: {str(e)}")
                    time.sleep(self.config.heartbeat_interval)
        
        self.health_check_thread = threading.Thread(target=health_monitor, daemon=True)
        self.health_check_thread.start()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Worker {self.config.worker_id} received signal {signum}")
            self._graceful_shutdown()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)

    def _graceful_shutdown(self):
        """Perform graceful shutdown."""
        logger.info(f"Worker {self.config.worker_id} starting graceful shutdown")
        
        self.state = WorkerState.STOPPING
        self.shutdown_requested = True
        
        # Stop accepting new jobs
        self.should_run_maintenance_tasks = False
        
        # Wait for current job to complete (if any)
        current_job = self.get_current_job()
        if current_job:
            logger.info(f"Worker {self.config.worker_id} waiting for current job {current_job.id} to complete")
            # The worker will naturally complete the current job
        
        logger.info(f"Worker {self.config.worker_id} shutdown complete")

    def _cleanup(self):
        """Clean up resources."""
        self.state = WorkerState.STOPPED
        
        # Stop health monitoring
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.shutdown_requested = True
            self.health_check_thread.join(timeout=5)
        
        # Clean up worker health data
        try:
            health_key = f"worker_health:{self.config.worker_id}"
            self.redis_conn.delete(health_key)
        except Exception as e:
            logger.warning(f"Failed to clean up worker health data: {str(e)}")

    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss_bytes': memory_info.rss,
                'vms_bytes': memory_info.vms,
                'percent': process.memory_percent()
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}


class WorkerManager:
    """Manager for multiple workers with auto-scaling capabilities."""
    
    def __init__(self):
        """Initialize the worker manager."""
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_conn = redis.from_url(self.redis_url)
        self.workers: Dict[str, MitaWorker] = {}
        self.worker_threads: Dict[str, threading.Thread] = {}
        self.shutdown_requested = False
        
        logger.info("Worker manager initialized")

    def create_worker_config(
        self,
        worker_id: str,
        queues: List[str],
        **kwargs
    ) -> WorkerConfig:
        """Create a worker configuration."""
        return WorkerConfig(
            worker_id=worker_id,
            queues=queues,
            **kwargs
        )

    def start_worker(self, config: WorkerConfig) -> bool:
        """Start a new worker with the given configuration."""
        try:
            if config.worker_id in self.workers:
                logger.warning(f"Worker {config.worker_id} already exists")
                return False
            
            # Create and start worker
            worker = MitaWorker(config, self.redis_conn)
            
            def worker_thread():
                try:
                    worker.work()
                except Exception as e:
                    logger.error(f"Worker {config.worker_id} thread error: {str(e)}", exc_info=True)
                finally:
                    # Remove from active workers
                    if config.worker_id in self.workers:
                        del self.workers[config.worker_id]
                    if config.worker_id in self.worker_threads:
                        del self.worker_threads[config.worker_id]
            
            thread = threading.Thread(target=worker_thread, name=f"worker-{config.worker_id}")
            thread.daemon = True
            thread.start()
            
            self.workers[config.worker_id] = worker
            self.worker_threads[config.worker_id] = thread
            
            logger.info(f"Worker {config.worker_id} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start worker {config.worker_id}: {str(e)}", exc_info=True)
            return False

    def stop_worker(self, worker_id: str, graceful: bool = True) -> bool:
        """Stop a specific worker."""
        try:
            if worker_id not in self.workers:
                logger.warning(f"Worker {worker_id} not found")
                return False
            
            worker = self.workers[worker_id]
            
            if graceful:
                worker._graceful_shutdown()
            else:
                worker.shutdown_requested = True
            
            # Wait for worker thread to complete
            thread = self.worker_threads.get(worker_id)
            if thread and thread.is_alive():
                thread.join(timeout=30)
                if thread.is_alive():
                    logger.warning(f"Worker {worker_id} thread did not stop within timeout")
            
            logger.info(f"Worker {worker_id} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop worker {worker_id}: {str(e)}", exc_info=True)
            return False

    def get_worker_status(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific worker."""
        worker = self.workers.get(worker_id)
        if worker:
            return worker.get_health_status()
        return None

    def get_all_workers_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all workers."""
        return {
            worker_id: worker.get_health_status()
            for worker_id, worker in self.workers.items()
        }

    def auto_scale(self, target_workers: Dict[str, int]) -> Dict[str, Any]:
        """
        Auto-scale workers based on target configuration.
        
        Args:
            target_workers: Dict mapping queue priorities to worker counts
        
        Returns:
            Dict containing scaling results
        """
        results = {
            'started': [],
            'stopped': [],
            'errors': []
        }
        
        try:
            # Current worker count by queue type
            current_workers = {}
            for worker_id, worker in self.workers.items():
                # Determine worker type based on queues
                for queue_name in worker.config.queues:
                    if queue_name not in current_workers:
                        current_workers[queue_name] = 0
                    current_workers[queue_name] += 1
            
            # Scale up/down as needed
            for queue_name, target_count in target_workers.items():
                current_count = current_workers.get(queue_name, 0)
                
                if current_count < target_count:
                    # Scale up
                    for i in range(target_count - current_count):
                        worker_id = f"{queue_name}_worker_{int(time.time())}_{i}"
                        config = self.create_worker_config(
                            worker_id=worker_id,
                            queues=[queue_name]
                        )
                        
                        if self.start_worker(config):
                            results['started'].append(worker_id)
                        else:
                            results['errors'].append(f"Failed to start {worker_id}")
                
                elif current_count > target_count:
                    # Scale down
                    workers_to_stop = []
                    for worker_id, worker in self.workers.items():
                        if queue_name in worker.config.queues:
                            workers_to_stop.append(worker_id)
                            if len(workers_to_stop) >= (current_count - target_count):
                                break
                    
                    for worker_id in workers_to_stop:
                        if self.stop_worker(worker_id):
                            results['stopped'].append(worker_id)
                        else:
                            results['errors'].append(f"Failed to stop {worker_id}")
            
            logger.info(f"Auto-scaling completed: {results}")
            
        except Exception as e:
            logger.error(f"Auto-scaling error: {str(e)}", exc_info=True)
            results['errors'].append(str(e))
        
        return results

    def shutdown_all(self, graceful: bool = True, timeout: int = 60) -> None:
        """Shutdown all workers."""
        logger.info("Shutting down all workers")
        
        self.shutdown_requested = True
        
        # Stop all workers
        for worker_id in list(self.workers.keys()):
            self.stop_worker(worker_id, graceful=graceful)
        
        # Wait for all threads to complete
        start_time = time.time()
        while self.worker_threads and (time.time() - start_time) < timeout:
            alive_threads = [
                thread_id for thread_id, thread in self.worker_threads.items()
                if thread.is_alive()
            ]
            if not alive_threads:
                break
            time.sleep(1)
        
        # Force cleanup of remaining threads
        for thread_id, thread in self.worker_threads.items():
            if thread.is_alive():
                logger.warning(f"Worker thread {thread_id} still alive after timeout")
        
        self.workers.clear()
        self.worker_threads.clear()
        
        logger.info("All workers shut down")


# Global worker manager instance
worker_manager = WorkerManager()


def create_standard_worker_configs() -> List[WorkerConfig]:
    """Create standard worker configurations for MITA."""
    configs = []
    
    # High priority queue workers (2 workers)
    for i in range(2):
        configs.append(WorkerConfig(
            worker_id=f"high_priority_worker_{i}",
            queues=['critical', 'high'],
            max_jobs=50,
            job_timeout=600,
            heartbeat_interval=15
        ))
    
    # Normal priority queue workers (3 workers)  
    for i in range(3):
        configs.append(WorkerConfig(
            worker_id=f"normal_priority_worker_{i}",
            queues=['default'],
            max_jobs=100,
            job_timeout=300,
            heartbeat_interval=30
        ))
    
    # Low priority queue workers (1 worker)
    configs.append(WorkerConfig(
        worker_id="low_priority_worker_0",
        queues=['low'],
        max_jobs=200,
        job_timeout=1800,  # 30 minutes for long-running tasks
        heartbeat_interval=60
    ))
    
    return configs


def start_standard_workers():
    """Start the standard set of workers for MITA."""
    configs = create_standard_worker_configs()
    
    for config in configs:
        success = worker_manager.start_worker(config)
        if success:
            logger.info(f"Started worker: {config.worker_id}")
        else:
            logger.error(f"Failed to start worker: {config.worker_id}")


if __name__ == "__main__":
    """Run worker manager as standalone script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MITA Worker Manager")
    parser.add_argument("--start-standard", action="store_true", help="Start standard workers")
    parser.add_argument("--worker-id", help="Start single worker with ID")
    parser.add_argument("--queues", nargs="+", help="Queues for single worker")
    
    args = parser.parse_args()
    
    try:
        if args.start_standard:
            start_standard_workers()
            logger.info("Standard workers started. Press Ctrl+C to stop.")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received interrupt, shutting down workers...")
                worker_manager.shutdown_all()
                
        elif args.worker_id and args.queues:
            config = WorkerConfig(
                worker_id=args.worker_id,
                queues=args.queues
            )
            
            if worker_manager.start_worker(config):
                logger.info(f"Worker {args.worker_id} started. Press Ctrl+C to stop.")
                
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("Received interrupt, shutting down worker...")
                    worker_manager.stop_worker(args.worker_id)
            else:
                logger.error(f"Failed to start worker {args.worker_id}")
                sys.exit(1)
        
        else:
            parser.print_help()
    
    except Exception as e:
        logger.error(f"Worker manager error: {str(e)}", exc_info=True)
        sys.exit(1)