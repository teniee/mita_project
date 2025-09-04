"""
Simplified Rate Limiter for MITA Finance Application
Provides robust rate limiting with Redis backend and in-memory fallback
"""

import asyncio
import hashlib
import logging
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from fastapi import Request, HTTPException

from app.core.limiter_setup import get_redis_connection
from app.core.error_handler import RateLimitException

logger = logging.getLogger(__name__)

# In-memory fallback storage
memory_store: Dict[str, Dict] = {}


class SimpleRateLimiter:
    """Simplified rate limiter with Redis and memory fallback"""
    
    def __init__(self):
        self.memory_store = memory_store
        
    def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier from request"""
        # Get real IP from headers (for proxied requests)
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
            request.headers.get("X-Real-IP", "") or
            request.headers.get("CF-Connecting-IP", "") or
            (request.client.host if request.client else "unknown")
        )
        
        # Add user agent hash for better uniqueness
        user_agent = request.headers.get("User-Agent", "")
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:8]
        
        return f"{client_ip}:{ua_hash}"
        
    async def _redis_sliding_window(self, redis_client, key: str, window_seconds: int, limit: int) -> Tuple[int, int, bool]:
        """Sliding window implementation with Redis"""
        try:
            now = time.time()
            window_start = now - window_seconds
            
            # Use pipeline for atomic operations
            pipe = redis_client.pipeline()
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Count current requests
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, window_seconds + 60)  # Extra buffer
            
            results = await pipe.execute()
            current_count = results[2]
            
            # Calculate reset time
            if current_count > 0:
                oldest_entries = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_time = oldest_entries[0][1]
                    time_until_reset = max(0, int(window_seconds - (now - oldest_time)))
                else:
                    time_until_reset = 0
            else:
                time_until_reset = 0
                
            is_exceeded = current_count > limit
            
            return current_count, time_until_reset, is_exceeded
            
        except Exception as e:
            logger.warning(f"Redis rate limiting failed: {e}")
            # Fall back to memory
            raise e
            
    def _memory_sliding_window(self, key: str, window_seconds: int, limit: int) -> Tuple[int, int, bool]:
        """Memory-based sliding window fallback"""
        now = time.time()
        window_start = now - window_seconds
        
        # Initialize if not exists
        if key not in self.memory_store:
            self.memory_store[key] = []
            
        # Remove old entries
        self.memory_store[key] = [
            timestamp for timestamp in self.memory_store[key]
            if timestamp > window_start
        ]
        
        # Add current request
        self.memory_store[key].append(now)
        
        current_count = len(self.memory_store[key])
        
        # Calculate reset time
        if self.memory_store[key]:
            oldest_time = min(self.memory_store[key])
            time_until_reset = max(0, int(window_seconds - (now - oldest_time)))
        else:
            time_until_reset = 0
            
        is_exceeded = current_count > limit
        
        return current_count, time_until_reset, is_exceeded
        
    async def check_rate_limit(self, request: Request, limit: int, window_seconds: int, 
                             endpoint: str, user_id: Optional[str] = None) -> dict:
        """Check rate limit for request"""
        from fastapi import FastAPI
        import inspect
        
        # Get app instance
        frame = inspect.currentframe()
        app = None
        while frame:
            if 'app' in frame.f_locals and isinstance(frame.f_locals['app'], FastAPI):
                app = frame.f_locals['app']
                break
            frame = frame.f_back
            
        client_id = self._get_client_identifier(request)
        
        # Create rate limit keys
        client_key = f"rate_limit:{endpoint}:client:{hashlib.sha256(client_id.encode()).hexdigest()[:16]}"
        user_key = None
        if user_id:
            user_key = f"rate_limit:{endpoint}:user:{user_id}"
        
        # Try Redis first if available
        redis_client = None
        if app and hasattr(app.state, 'redis_client'):
            redis_client = app.state.redis_client
        
        if not redis_client:
            try:
                redis_client = await get_redis_connection(app) if app else None
            except Exception:
                pass
                
        current_count = 0
        time_until_reset = 0
        
        try:
            if redis_client:
                # Use Redis
                current_count, time_until_reset, is_exceeded = await self._redis_sliding_window(
                    redis_client, client_key, window_seconds, limit
                )
                
                # Also check user-based limit if user is authenticated
                if user_key:
                    user_count, user_reset, user_exceeded = await self._redis_sliding_window(
                        redis_client, user_key, window_seconds, limit * 2  # Higher limit for authenticated users
                    )
                    if user_exceeded:
                        is_exceeded = True
                        time_until_reset = max(time_until_reset, user_reset)
                        
            else:
                # Use memory fallback
                current_count, time_until_reset, is_exceeded = self._memory_sliding_window(
                    client_key, window_seconds, limit
                )
                
                if user_key:
                    user_count, user_reset, user_exceeded = self._memory_sliding_window(
                        user_key, window_seconds, limit * 2
                    )
                    if user_exceeded:
                        is_exceeded = True
                        time_until_reset = max(time_until_reset, user_reset)
                        
        except Exception as e:
            logger.warning(f"Rate limiting check failed: {e}")
            # Fall back to memory
            current_count, time_until_reset, is_exceeded = self._memory_sliding_window(
                client_key, window_seconds, limit
            )
            
        if is_exceeded:
            logger.warning(f"Rate limit exceeded for {endpoint}: {current_count}/{limit} requests")
            raise RateLimitException(
                f"Rate limit exceeded. Try again in {time_until_reset} seconds.",
                retry_after=time_until_reset
            )
            
        return {
            "requests_made": current_count,
            "limit": limit,
            "time_until_reset": time_until_reset,
            "backend": "redis" if redis_client else "memory"
        }


# Global rate limiter instance
rate_limiter = SimpleRateLimiter()


# Rate limiting decorators for common scenarios
def auth_rate_limit(limit: int = 5, window: int = 300):  # 5 requests per 5 minutes
    """Rate limit decorator for authentication endpoints"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
                        
            if request:
                await rate_limiter.check_rate_limit(
                    request, limit, window, f"auth_{func.__name__}"
                )
                
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def api_rate_limit(limit: int = 1000, window: int = 3600):  # 1000 requests per hour
    """Rate limit decorator for API endpoints"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
                        
            if request:
                await rate_limiter.check_rate_limit(
                    request, limit, window, f"api_{func.__name__}"
                )
                
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Dependency functions for FastAPI
async def check_login_rate_limit(request: Request):
    """Dependency for login rate limiting"""
    await rate_limiter.check_rate_limit(request, 10, 900, "auth_login")  # 10 per 15 minutes (increased from emergency limits)
    return True


async def check_register_rate_limit(request: Request):
    """Dependency for registration rate limiting"""
    await rate_limiter.check_rate_limit(request, 5, 3600, "auth_register")  # 5 per hour (increased from emergency limits)
    return True


async def check_password_reset_rate_limit(request: Request):
    """Dependency for password reset rate limiting"""
    await rate_limiter.check_rate_limit(request, 3, 1800, "auth_password_reset")  # 3 per 30 minutes
    return True


async def check_token_refresh_rate_limit(request: Request):
    """Dependency for token refresh rate limiting"""
    await rate_limiter.check_rate_limit(request, 20, 300, "auth_token_refresh")  # 20 per 5 minutes
    return True


async def check_api_rate_limit(request: Request):
    """Dependency for general API rate limiting"""
    await rate_limiter.check_rate_limit(request, 1000, 3600, "api_general")  # 1000 per hour
    return True


async def check_upload_rate_limit(request: Request):
    """Dependency for file upload rate limiting"""
    await rate_limiter.check_rate_limit(request, 10, 3600, "api_upload")  # 10 per hour
    return True


# ---- EMERGENCY RATE LIMITING INTEGRATION ----
# Legacy emergency rate limiting functions - integrated into main system

def check_registration_rate_limit(client_ip: str):
    """
    Legacy emergency rate limiting - now integrated into main system.
    This function is deprecated and should use the main async rate limiting system instead.
    """
    # Emergency rate limiting has been integrated into the main system
    # Use check_register_rate_limit dependency instead
    pass


def check_login_rate_limit_sync(client_ip: str):
    """
    Legacy emergency rate limiting - now integrated into main system.
    This function is deprecated and should use the main async rate limiting system instead.
    """
    # Emergency rate limiting has been integrated into the main system
    # Use check_login_rate_limit dependency instead
    pass


def check_suspicious_activity_rate_limit_sync(client_ip: str):
    """
    Legacy emergency rate limiting - now integrated into main system.
    This function is deprecated and should use the main async rate limiting system instead.
    """
    # Emergency rate limiting has been integrated into the main system
    pass