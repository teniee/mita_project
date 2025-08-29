import os
import logging
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

logger = logging.getLogger(__name__)


async def init_rate_limiter(app: FastAPI):
    """Initialize rate limiter with external Redis provider and graceful fallback"""
    # Priority: Upstash REST > Upstash TCP > REDIS_URL > fallback to memory-based rate limiting
    upstash_rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")
    
    # EMERGENCY FIX: Handle empty string Redis URLs gracefully
    if redis_url == "":
        redis_url = None
    
    # If Upstash REST API is configured, use it
    if upstash_rest_url and upstash_rest_token and upstash_rest_url != "" and upstash_rest_token != "":
        logger.info("Using Upstash Redis REST API for rate limiting")
        try:
            # Create Redis connection from REST URL
            # Convert REST URL to Redis URL format for redis-py
            if upstash_rest_url.startswith('https://'):
                host = upstash_rest_url.replace('https://', '').replace('http://', '')
                redis_url = f"rediss://default:{upstash_rest_token}@{host}:6380"
            app.state.redis_available = True
            app.state.upstash_rest_url = upstash_rest_url
            app.state.upstash_rest_token = upstash_rest_token
        except Exception as e:
            logger.warning(f"Upstash REST configuration error: {e}")
            app.state.redis_available = False
            return
    elif not redis_url:
        logger.info("No Redis configuration found. Rate limiting will use in-memory fallback.")
        app.state.redis_available = False
        return
    else:
        # Validate Redis URL format for TCP connections  
        if not (redis_url.startswith('redis://') or redis_url.startswith('rediss://')):
            logger.warning(f"Invalid Redis URL format: '{redis_url}' - falling back to in-memory rate limiting")
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
