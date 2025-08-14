import os
import logging
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

logger = logging.getLogger(__name__)


async def init_rate_limiter(app: FastAPI):
    """Initialize rate limiter with environment variable for Redis URL"""
    redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL", "redis://localhost:6379")
    
    if not redis_url or redis_url == "redis://localhost:6379":
        logger.warning("Rate limiter: Using default Redis URL. Set UPSTASH_REDIS_URL for production.")
    
    try:
        redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,  # 5 second connection timeout
            socket_timeout=5,          # 5 second socket timeout
            retry_on_timeout=True,
            health_check_interval=30   # Health check every 30 seconds
        )

        await FastAPILimiter.init(
            redis_client,
            prefix="FASTAPI_LIMITER",
        )
        
        logger.info("Rate limiter initialized successfully")

        @app.on_event("shutdown")
        async def shutdown():
            try:
                await redis_client.aclose()
                logger.info("Rate limiter shutdown completed")
            except Exception as e:
                logger.error(f"Error during rate limiter shutdown: {e}")
                
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        # Don't raise - allow app to start without rate limiting
        logger.warning("Starting without rate limiting functionality")
