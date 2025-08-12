"""
Enhanced MITA Worker with production-ready features.
Supports graceful shutdown, health monitoring, and advanced queue management.
"""

import os
import sys
import signal
import logging
from typing import List

from app.core.worker_manager import worker_manager, create_standard_worker_configs, WorkerConfig
from app.core.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main worker entry point."""
    # Get configuration from environment
    worker_id = os.getenv("WORKER_ID", "mita_worker")
    queues = os.getenv("WORKER_QUEUES", "default").split(",")
    max_jobs = int(os.getenv("WORKER_MAX_JOBS", "100"))
    job_timeout = int(os.getenv("WORKER_JOB_TIMEOUT", "600"))
    burst_mode = os.getenv("WORKER_BURST_MODE", "false").lower() == "true"
    
    # Check if we should start standard workers or a single worker
    start_standard = os.getenv("START_STANDARD_WORKERS", "false").lower() == "true"
    
    try:
        if start_standard:
            logger.info("Starting standard worker configuration")
            configs = create_standard_worker_configs()
            
            # Start all standard workers
            for config in configs:
                success = worker_manager.start_worker(config)
                if success:
                    logger.info(f"Started worker: {config.worker_id}")
                else:
                    logger.error(f"Failed to start worker: {config.worker_id}")
            
            logger.info(f"Started {len(configs)} workers. Monitoring...")
            
        else:
            logger.info(f"Starting single worker: {worker_id}")
            
            # Create single worker configuration
            config = WorkerConfig(
                worker_id=worker_id,
                queues=queues,
                max_jobs=max_jobs,
                job_timeout=job_timeout,
                burst_mode=burst_mode
            )
            
            # Start single worker
            success = worker_manager.start_worker(config)
            if success:
                logger.info(f"Worker {worker_id} started successfully")
            else:
                logger.error(f"Failed to start worker {worker_id}")
                sys.exit(1)
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down workers...")
            worker_manager.shutdown_all(graceful=True, timeout=60)
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
        
        # Keep the process running
        logger.info("Workers running. Press Ctrl+C to stop.")
        
        import time
        while True:
            # Periodically log worker status
            status = worker_manager.get_all_workers_status()
            active_workers = len([w for w in status.values() if w['state'] in ['idle', 'busy']])
            logger.info(f"Active workers: {active_workers}")
            
            time.sleep(60)  # Status update every minute
            
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down workers...")
        worker_manager.shutdown_all(graceful=True, timeout=60)
    except Exception as e:
        logger.error(f"Worker process error: {str(e)}", exc_info=True)
        worker_manager.shutdown_all(graceful=False, timeout=30)
        sys.exit(1)


if __name__ == "__main__":
    main()
