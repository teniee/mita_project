import os
import logging
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

logger = logging.getLogger(__name__)


async def init_rate_limiter(app: FastAPI):
    """Initialize rate limiter with external Redis provider and graceful fallback"""
    # Priority: Upstash > REDIS_URL > fallback to memory-based rate limiting
    redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
    
    if not redis_url:
        logger.error("No Redis URL configured. Rate limiting will use in-memory fallback.")
        # Set a flag for the application to use memory-based rate limiting
        app.state.redis_available = False
        return
    
    # Validate Redis URL format
    if not (redis_url.startswith('redis://') or redis_url.startswith('rediss://')):
        logger.error(f"Invalid Redis URL format: {redis_url}")
        app.state.redis_available = False
        return
    
    try:
        # Enhanced Redis connection for production reliability
        redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=10,    # 10 second connection timeout for external Redis
            socket_timeout=10,            # 10 second socket timeout
            retry_on_timeout=True,
            retry_on_error=[redis.ConnectionError, redis.TimeoutError],
            health_check_interval=30,     # Health check every 30 seconds
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
            ssl_cert_reqs=None if redis_url.startswith('rediss://') else None  # SSL for secure connections
        )

        # Test Redis connection
        await redis_client.ping()
        
        await FastAPILimiter.init(
            redis_client,
            prefix="FASTAPI_LIMITER",
        )
        
        app.state.redis_available = True
        logger.info(f"Rate limiter initialized successfully with external Redis: {redis_url[:20]}...")

        @app.on_event("shutdown")
        async def shutdown():
            try:
                await redis_client.aclose()
                logger.info("Redis connection closed successfully")
            except Exception as e:
                logger.error(f"Error during Redis shutdown: {e}")
                
    except redis.ConnectionError as e:
        logger.error(f"Redis connection failed: {e}")
        app.state.redis_available = False
        logger.warning("Starting with in-memory rate limiting fallback")
        
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        app.state.redis_available = False
        logger.warning("Starting with in-memory rate limiting fallback")
