import os
import asyncio
import logging
from typing import Optional
import redis.asyncio as redis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter

logger = logging.getLogger(__name__)


async def init_rate_limiter(app: FastAPI):
    """Initialize rate limiter with lazy Redis connection to prevent startup hangs"""
    # FIXED: Use lazy initialization pattern to prevent startup hangs
    # Store connection config in app state for lazy connection
    upstash_rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    redis_url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL")

    # Handle empty string Redis URLs gracefully
    if redis_url == "":
        redis_url = None

    # Store Redis configuration in app state for lazy initialization
    app.state.redis_config = {
        "upstash_rest_url": upstash_rest_url,
        "upstash_rest_token": upstash_rest_token,
        "redis_url": redis_url
    }

    # Initialize state variables
    app.state.redis_available = None  # None = not yet tested, False = failed, True = working
    app.state.redis_client = None
    app.state.fastapi_limiter_initialized = False

    # Try to initialize Redis eagerly (but with timeout to prevent hangs)
    if redis_url:
        try:
            logger.info(f"Attempting eager Redis initialization: {redis_url[:20]}...")
            redis_client = await get_redis_connection(app)
            if redis_client:
                # Also set global redis_client in security.py for AdvancedRateLimiter
                import app.core.security as security_module
                security_module.redis_client = redis_client
                logger.info("✅ Redis initialized successfully on startup")
        except Exception as e:
            logger.warning(f"⚠️ Redis eager initialization failed (will use lazy): {e}")

    # Don't test connection during startup - use lazy initialization
    if upstash_rest_url and upstash_rest_token:
        logger.info("Redis REST API configuration detected - will initialize on first use")
    elif redis_url:
        logger.info(f"Redis URL detected - will initialize on first use: {redis_url[:20]}...")
    else:
        logger.info("No Redis configuration found - will use in-memory fallback")
        app.state.redis_available = False

    logger.info("Rate limiter setup complete - using lazy initialization pattern")


async def get_redis_connection(app: FastAPI) -> Optional[redis.Redis]:
    """Get Redis connection with lazy initialization"""
    if app.state.redis_available is False:
        return None
        
    if app.state.redis_client is not None:
        return app.state.redis_client
        
    # First time initialization
    config = app.state.redis_config
    redis_url = None
    
    try:
        # Determine Redis URL
        if config["upstash_rest_url"] and config["upstash_rest_token"]:
            # Convert REST URL to Redis URL format
            if config["upstash_rest_url"].startswith('https://'):
                host = config["upstash_rest_url"].replace('https://', '').replace('http://', '')
                redis_url = f"rediss://default:{config['upstash_rest_token']}@{host}:6380"
                logger.info("Using Upstash Redis REST API configuration")
        elif config["redis_url"]:
            redis_url = config["redis_url"]
            logger.info("Using direct Redis URL configuration")
            
        if not redis_url:
            logger.info("No valid Redis configuration - using in-memory fallback")
            app.state.redis_available = False
            return None
            
        # Validate URL format
        if not (redis_url.startswith('redis://') or redis_url.startswith('rediss://')):
            logger.warning("Invalid Redis URL format - using in-memory fallback")
            app.state.redis_available = False
            return None
        
        # Create Redis connection with short timeout to prevent hangs
        # Note: redis.asyncio.from_url() returns client directly (not a coroutine)
        redis_client = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,    # Short timeout to prevent hangs
            socket_timeout=3,            # Short socket timeout
            retry_on_timeout=False,      # Don't retry on timeout
            max_connections=10,          # Smaller connection pool
        )

        # Test connection with timeout (ping IS async)
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
        
        # Initialize FastAPI-Limiter only once
        if not app.state.fastapi_limiter_initialized:
            await FastAPILimiter.init(redis_client, prefix="FASTAPI_LIMITER")
            app.state.fastapi_limiter_initialized = True
        
        app.state.redis_client = redis_client
        app.state.redis_available = True
        logger.info(f"Redis connection established successfully: {redis_url[:20]}...")
        
        return redis_client
        
    except asyncio.TimeoutError:
        logger.warning("Redis connection timed out - using in-memory fallback")
        app.state.redis_available = False
        return None
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - using in-memory fallback")
        app.state.redis_available = False
        return None
