#!/usr/bin/env python3
"""
MITA Finance Email Worker Startup Script
Production-ready email queue worker with health monitoring and graceful shutdown
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Optional

# Set up logging before importing app modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        (
            logging.FileHandler("/var/log/mita/email-worker.log", mode="a")
            if sys.platform != "win32"
            else logging.StreamHandler(sys.stdout)
        ),
    ],
)

logger = logging.getLogger(__name__)

from app.core.external_services import get_services_health

# Import after logging setup
from app.services.email_queue_service import get_email_queue_service


class EmailWorkerManager:
    """Email worker manager with health monitoring and graceful shutdown"""

    def __init__(self):
        self.queue_service: Optional = None
        self.is_running = False
        self.shutdown_requested = False

    async def start(self):
        """Start the email worker with health monitoring"""
        logger.info("🚀 Starting MITA Finance Email Worker")

        try:
            # Get email queue service
            self.queue_service = await get_email_queue_service()

            # Validate dependencies
            await self._validate_dependencies()

            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # Start the worker
            logger.info("Starting email queue worker...")
            await self.queue_service.start_worker()
            self.is_running = True

            logger.info("✅ Email worker started successfully")

            # Health monitoring loop
            await self._health_monitoring_loop()

        except Exception as e:
            logger.error(f"❌ Failed to start email worker: {e}")
            await self.shutdown()
            sys.exit(1)

    async def _validate_dependencies(self):
        """Validate that all required dependencies are available"""
        logger.info("🔍 Validating dependencies...")

        # Check external services
        services_health = get_services_health()

        # Check SendGrid
        sendgrid_status = services_health.get("services", {}).get("sendgrid", {})
        if not sendgrid_status.get("enabled", False):
            logger.warning("⚠️  SendGrid is not configured - emails will fail")
        elif sendgrid_status.get("status") != "healthy":
            logger.warning(f"⚠️  SendGrid status: {sendgrid_status.get('status')}")

        # Check Redis
        redis_status = services_health.get("services", {}).get("redis", {})
        if not redis_status.get("enabled", False):
            logger.warning(
                "⚠️  Redis is not configured - queue will fall back to immediate processing"
            )
        elif redis_status.get("status") != "healthy":
            logger.warning(f"⚠️  Redis status: {redis_status.get('status')}")

        # Check database connectivity
        # This would be done by the queue service during initialization

        logger.info("✅ Dependency validation completed")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
            self.shutdown_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        if hasattr(signal, "SIGHUP"):  # Unix only
            signal.signal(signal.SIGHUP, signal_handler)

    async def _health_monitoring_loop(self):
        """Main health monitoring and worker supervision loop"""
        logger.info("📊 Starting health monitoring loop")

        last_health_check = time.time()
        health_check_interval = 60  # Check every minute

        while not self.shutdown_requested:
            try:
                # Health check every minute
                current_time = time.time()
                if current_time - last_health_check >= health_check_interval:
                    await self._perform_health_check()
                    last_health_check = current_time

                # Check if worker is still running
                if not self.queue_service.is_worker_running:
                    logger.error("❌ Email worker stopped unexpectedly")
                    if not self.shutdown_requested:
                        logger.info("🔄 Restarting email worker...")
                        await self.queue_service.start_worker()

                # Sleep for a short interval
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"💥 Error in health monitoring loop: {e}")
                await asyncio.sleep(10)  # Longer sleep on error

        logger.info("🛑 Health monitoring loop stopped")

    async def _perform_health_check(self):
        """Perform comprehensive health check"""
        try:
            # Get queue status
            queue_status = await self.queue_service.get_queue_status()

            # Log key metrics
            logger.info(
                f"📊 Queue Status: "
                f"Size={queue_status.get('queue_size', 0)}, "
                f"Processing={queue_status.get('processing_size', 0)}, "
                f"Retry={queue_status.get('retry_queue_size', 0)}, "
                f"Dead={queue_status.get('dead_letter_size', 0)}"
            )

            # Check for concerning metrics
            queue_size = queue_status.get("queue_size", 0)
            processing_size = queue_status.get("processing_size", 0)
            dead_letter_size = queue_status.get("dead_letter_size", 0)

            if queue_size > 1000:
                logger.warning(f"⚠️  Large queue size: {queue_size}")

            if processing_size > 50:
                logger.warning(f"⚠️  Many jobs processing: {processing_size}")

            if dead_letter_size > 100:
                logger.warning(f"⚠️  High dead letter count: {dead_letter_size}")

            # Get worker metrics
            metrics = queue_status.get("metrics", {})
            success_rate = metrics.get("success_rate", 0)

            if success_rate < 0.95:  # Less than 95% success rate
                logger.warning(f"⚠️  Low success rate: {success_rate:.2%}")

            logger.debug(f"📈 Success rate: {success_rate:.2%}")

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")

    async def shutdown(self):
        """Graceful shutdown of the email worker"""
        if not self.is_running:
            return

        logger.info("🛑 Initiating graceful shutdown...")
        self.shutdown_requested = True

        if self.queue_service:
            try:
                # Stop the worker
                await self.queue_service.stop_worker()
                logger.info("✅ Email worker stopped gracefully")

                # Get final queue status
                final_status = await self.queue_service.get_queue_status()
                logger.info(f"📊 Final queue status: {final_status}")

            except Exception as e:
                logger.error(f"❌ Error during shutdown: {e}")

        self.is_running = False
        logger.info("🏁 Email worker shutdown complete")


async def main():
    """Main entry point"""
    worker_manager = EmailWorkerManager()

    try:
        await worker_manager.start()
    except KeyboardInterrupt:
        logger.info("🔸 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)
    finally:
        await worker_manager.shutdown()
        logger.info("👋 Email worker exited")


if __name__ == "__main__":
    # Ensure we're using the correct event loop policy for the platform
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Run the worker
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔸 Shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)
