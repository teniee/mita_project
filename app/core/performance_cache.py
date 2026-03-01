"""
Performance Caching System for MITA Finance Backend
Provides in-memory caching for frequently accessed data to improve response times
"""

import time
import asyncio
import logging
from typing import Any, Dict, Optional, Callable
from functools import wraps
from threading import RLock

logger = logging.getLogger(__name__)


class PerformanceCache:
    """High-performance in-memory cache with TTL and automatic cleanup"""
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Clean up every minute
    
    def _cleanup_expired(self):
        """Remove expired entries and enforce size limits"""
        with self._lock:
            current_time = time.time()
            
            # Remove expired entries
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.get('expires_at', 0) < current_time
            ]
            
            for key in expired_keys:
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
            
            # Enforce size limit by removing least recently used items
            if len(self._cache) > self.max_size:
                # Sort by access time and remove oldest
                sorted_keys = sorted(
                    self._access_times.items(),
                    key=lambda x: x[1]
                )
                
                to_remove = len(self._cache) - self.max_size
                for i in range(to_remove):
                    key_to_remove = sorted_keys[i][0]
                    self._cache.pop(key_to_remove, None)
                    self._access_times.pop(key_to_remove, None)
            
            self._last_cleanup = current_time
            
            if expired_keys:
                logger.debug(f"Cache cleanup: removed {len(expired_keys)} expired entries")
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value by key"""
        current_time = time.time()
        
        # Periodic cleanup
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
        
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            
            # Check if expired
            if entry.get('expires_at', 0) < current_time:
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
                return None
            
            # Update access time
            self._access_times[key] = current_time
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cached value with optional TTL"""
        current_time = time.time()
        ttl = ttl or self.default_ttl
        
        with self._lock:
            self._cache[key] = {
                'value': value,
                'created_at': current_time,
                'expires_at': current_time + ttl
            }
            self._access_times[key] = current_time
    
    def delete(self, key: str) -> bool:
        """Delete cached entry"""
        with self._lock:
            if key in self._cache:
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached entries"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'utilization': len(self._cache) / self.max_size,
                'last_cleanup': self._last_cleanup
            }


# Global cache instances
user_cache = PerformanceCache(max_size=5000, default_ttl=600)  # 10 minutes for user data
token_cache = PerformanceCache(max_size=10000, default_ttl=300)  # 5 minutes for tokens
query_cache = PerformanceCache(max_size=2000, default_ttl=120)  # 2 minutes for query results


def cache_result(cache: PerformanceCache, key_func: Callable = None, ttl: int = None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default key generation
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {func.__name__}: {cache_key}")
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def cache_user_data(ttl: int = 600):
    """Cache user-related data"""
    return cache_result(user_cache, ttl=ttl)


def cache_query_result(ttl: int = 120):
    """Cache database query results"""
    return cache_result(query_cache, ttl=ttl)


def cache_token_validation(ttl: int = 300):
    """Cache token validation results"""
    return cache_result(token_cache, ttl=ttl)


# Cache warming functions for frequently accessed data
async def warm_user_cache(user_ids: list):
    """Pre-warm user cache with frequently accessed users"""
    # This would be implemented to pre-load user data
    pass


def get_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches"""
    return {
        'user_cache': user_cache.stats(),
        'token_cache': token_cache.stats(),
        'query_cache': query_cache.stats()
    }


def clear_all_caches():
    """Clear all performance caches"""
    user_cache.clear()
    token_cache.clear()
    query_cache.clear()
    logger.info("All performance caches cleared")