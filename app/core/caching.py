"""
Comprehensive Caching Layer for MITA Backend
Provides multi-tier caching with Redis, in-memory, and database query result caching
"""

import json
import pickle
import hashlib
import asyncio
import logging
from typing import Any, Dict, List, Optional, Callable, TypeVar
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from functools import wraps
import redis.asyncio as redis

from app.core.config import settings
from app.core.error_monitoring import log_error, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheLevel(Enum):
    """Cache storage levels"""
    MEMORY = "memory"      # In-process memory cache
    REDIS = "redis"        # Redis distributed cache
    DATABASE = "database"  # Database-backed cache


class CacheStrategy(Enum):
    """Cache invalidation strategies"""
    TTL = "ttl"                    # Time-based expiration
    LRU = "lru"                    # Least Recently Used
    WRITE_THROUGH = "write_through" # Update cache on write
    WRITE_BEHIND = "write_behind"   # Async cache updates
    REFRESH_AHEAD = "refresh_ahead" # Proactive refresh


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int
    last_accessed: datetime
    size_bytes: int
    tags: List[str]
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat() if self.expires_at else None
        data['last_accessed'] = self.last_accessed.isoformat()
        return data


class MemoryCache:
    """High-performance in-memory cache with LRU eviction"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []
        self.lock = asyncio.Lock()
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_expired())
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from memory cache"""
        async with self.lock:
            entry = self.cache.get(key)
            if not entry:
                return None
            
            if entry.is_expired():
                await self._remove_key(key)
                return None
            
            # Update access metadata
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            
            # Update LRU order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
            
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: List[str] = None
    ):
        """Set value in memory cache"""
        async with self.lock:
            ttl = ttl or self.default_ttl
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
            
            # Calculate size (approximate)
            size_bytes = len(pickle.dumps(value))
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                access_count=0,
                last_accessed=datetime.utcnow(),
                size_bytes=size_bytes,
                tags=tags or []
            )
            
            self.cache[key] = entry
            
            # Update access order
            if key in self.access_order:
                self.access_order.remove(key)
            self.access_order.append(key)
            
            # Evict if necessary
            await self._evict_if_necessary()
    
    async def delete(self, key: str) -> bool:
        """Delete key from memory cache"""
        async with self.lock:
            return await self._remove_key(key)
    
    async def clear_by_tags(self, tags: List[str]):
        """Clear cache entries by tags"""
        async with self.lock:
            keys_to_remove = []
            for key, entry in self.cache.items():
                if any(tag in entry.tags for tag in tags):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                await self._remove_key(key)
    
    async def _remove_key(self, key: str) -> bool:
        """Remove key from cache"""
        if key in self.cache:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return True
        return False
    
    async def _evict_if_necessary(self):
        """Evict least recently used items if cache is full"""
        while len(self.cache) > self.max_size:
            if self.access_order:
                lru_key = self.access_order.pop(0)
                await self._remove_key(lru_key)
    
    async def _cleanup_expired(self):
        """Periodically cleanup expired entries"""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                
                async with self.lock:
                    expired_keys = []
                    for key, entry in self.cache.items():
                        if entry.is_expired():
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        await self._remove_key(key)
                    
                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            except Exception as e:
                logger.error(f"Error in cache cleanup: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        
        return {
            'entries': len(self.cache),
            'max_size': self.max_size,
            'utilization': (len(self.cache) / self.max_size) * 100,
            'total_size_bytes': total_size,
            'avg_size_bytes': total_size / len(self.cache) if self.cache else 0
        }


class RedisCache:
    """Redis-based distributed cache"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.default_ttl = 300
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection with external provider support"""
        try:
            # Priority: Upstash > REDIS_URL > fallback to None
            redis_url = getattr(settings, 'UPSTASH_REDIS_URL', None) or getattr(settings, 'REDIS_URL', None)
            
            if not redis_url:
                logger.warning("No Redis URL configured for caching. Cache will be disabled.")
                self.redis_client = None
                return
            
            # Validate Redis URL format - EMERGENCY FIX: Handle empty strings gracefully
            if redis_url == "" or not (redis_url.startswith('redis://') or redis_url.startswith('rediss://')):
                logger.warning(f"Invalid Redis URL format for caching: '{redis_url}' - using in-memory cache")
                self.redis_client = None
                return
            
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # Keep binary for pickle data
                retry_on_timeout=True,
                socket_timeout=10,       # Increased timeout for external Redis
                socket_connect_timeout=10,
                max_connections=int(getattr(settings, 'REDIS_MAX_CONNECTIONS', 20)),
                ssl_cert_reqs=None if redis_url.startswith('rediss://') else None
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis cache initialized with external provider: {redis_url[:20]}...")
            
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed for caching: {e}")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Redis cache initialization failed: {str(e)}")
            self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.redis_client:
            return None
        
        try:
            data = await self.redis_client.get(f"cache:{key}")
            if data is None:
                return None
            
            # Deserialize the data
            cache_entry = pickle.loads(data)
            
            # Update access metadata
            await self._update_access_metadata(key)
            
            return cache_entry['value']
            
        except Exception as e:
            logger.error(f"Error getting from Redis cache: {str(e)}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: List[str] = None
    ):
        """Set value in Redis cache"""
        if not self.redis_client:
            return
        
        try:
            ttl = ttl or self.default_ttl
            
            cache_entry = {
                'value': value,
                'created_at': datetime.utcnow().isoformat(),
                'tags': tags or []
            }
            
            data = pickle.dumps(cache_entry)
            await self.redis_client.setex(f"cache:{key}", ttl, data)
            
            # Store tags for invalidation
            if tags:
                for tag in tags:
                    await self.redis_client.sadd(f"tag:{tag}", key)
                    await self.redis_client.expire(f"tag:{tag}", ttl + 3600)
            
        except Exception as e:
            logger.error(f"Error setting Redis cache: {str(e)}")
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis cache"""
        if not self.redis_client:
            return False
        
        try:
            result = await self.redis_client.delete(f"cache:{key}")
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting from Redis cache: {str(e)}")
            return False
    
    async def clear_by_tags(self, tags: List[str]):
        """Clear cache entries by tags"""
        if not self.redis_client:
            return
        
        try:
            for tag in tags:
                keys = await self.redis_client.smembers(f"tag:{tag}")
                if keys:
                    cache_keys = [f"cache:{key.decode()}" if isinstance(key, bytes) else f"cache:{key}" for key in keys]
                    await self.redis_client.delete(*cache_keys)
                    await self.redis_client.delete(f"tag:{tag}")
        except Exception as e:
            logger.error(f"Error clearing Redis cache by tags: {str(e)}")
    
    async def _update_access_metadata(self, key: str):
        """Update access metadata for cache entry"""
        try:
            await self.redis_client.hincrby(f"meta:{key}", "access_count", 1)
            await self.redis_client.hset(f"meta:{key}", "last_accessed", datetime.utcnow().isoformat())
        except Exception:
            pass  # Non-critical operation
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis cache statistics"""
        if not self.redis_client:
            return {}
        
        try:
            info = await self.redis_client.info("memory")
            keyspace = await self.redis_client.info("keyspace")
            
            return {
                'connected': True,
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'keyspace': keyspace
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {str(e)}")
            return {'connected': False, 'error': str(e)}


class MultiTierCache:
    """Multi-tier cache combining memory and Redis"""
    
    def __init__(self):
        self.memory_cache = MemoryCache(max_size=1000, default_ttl=300)
        self.redis_cache = RedisCache()
        self.hit_stats = {
            'memory_hits': 0,
            'redis_hits': 0,
            'misses': 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from multi-tier cache"""
        # Try memory cache first (L1)
        value = await self.memory_cache.get(key)
        if value is not None:
            self.hit_stats['memory_hits'] += 1
            return value
        
        # Try Redis cache (L2)
        value = await self.redis_cache.get(key)
        if value is not None:
            self.hit_stats['redis_hits'] += 1
            # Promote to memory cache
            await self.memory_cache.set(key, value, ttl=300)
            return value
        
        self.hit_stats['misses'] += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: List[str] = None,
        levels: List[CacheLevel] = None
    ):
        """Set value in multi-tier cache"""
        levels = levels or [CacheLevel.MEMORY, CacheLevel.REDIS]
        
        if CacheLevel.MEMORY in levels:
            await self.memory_cache.set(key, value, ttl, tags)
        
        if CacheLevel.REDIS in levels:
            await self.redis_cache.set(key, value, ttl, tags)
    
    async def delete(self, key: str):
        """Delete from all cache levels"""
        await self.memory_cache.delete(key)
        await self.redis_cache.delete(key)
    
    async def clear_by_tags(self, tags: List[str]):
        """Clear cache by tags across all levels"""
        await self.memory_cache.clear_by_tags(tags)
        await self.redis_cache.clear_by_tags(tags)
    
    def get_hit_ratio(self) -> Dict[str, float]:
        """Get cache hit ratios"""
        total_requests = sum(self.hit_stats.values())
        if total_requests == 0:
            return {'memory': 0.0, 'redis': 0.0, 'total': 0.0}
        
        return {
            'memory': (self.hit_stats['memory_hits'] / total_requests) * 100,
            'redis': (self.hit_stats['redis_hits'] / total_requests) * 100,
            'total': ((self.hit_stats['memory_hits'] + self.hit_stats['redis_hits']) / total_requests) * 100
        }
    
    async def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        memory_stats = self.memory_cache.get_stats()
        redis_stats = await self.redis_cache.get_stats()
        hit_ratios = self.get_hit_ratio()
        
        return {
            'memory_cache': memory_stats,
            'redis_cache': redis_stats,
            'hit_ratios': hit_ratios,
            'hit_stats': self.hit_stats,
            'timestamp': datetime.utcnow().isoformat()
        }


class QueryCache:
    """Database query result cache with intelligent invalidation"""
    
    def __init__(self, cache: MultiTierCache):
        self.cache = cache
        self.query_tags = {
            'users': ['user', 'profile', 'auth'],
            'transactions': ['transaction', 'financial', 'money'],
            'goals': ['goal', 'target', 'saving'],
            'analytics': ['analytics', 'report', 'stats']
        }
    
    def _generate_cache_key(self, query: str, params: Dict[str, Any] = None) -> str:
        """Generate consistent cache key for query"""
        # Normalize query
        normalized_query = ' '.join(query.strip().split())
        
        # Include parameters in key
        param_str = json.dumps(params or {}, sort_keys=True)
        
        # Create hash
        key_data = f"{normalized_query}:{param_str}"
        return f"query:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def _get_query_tags(self, query: str) -> List[str]:
        """Determine cache tags based on query content"""
        query_lower = query.lower()
        tags = []
        
        for table, table_tags in self.query_tags.items():
            if table in query_lower:
                tags.extend(table_tags)
        
        # Add operation-based tags
        if 'select' in query_lower:
            tags.append('read')
        elif any(op in query_lower for op in ['insert', 'update', 'delete']):
            tags.append('write')
        
        return list(set(tags))
    
    async def get_cached_result(self, query: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """Get cached query result"""
        cache_key = self._generate_cache_key(query, params)
        return await self.cache.get(cache_key)
    
    async def cache_result(
        self,
        query: str,
        result: Any,
        params: Dict[str, Any] = None,
        ttl: int = 300
    ):
        """Cache query result"""
        cache_key = self._generate_cache_key(query, params)
        tags = self._get_query_tags(query)
        
        await self.cache.set(cache_key, result, ttl=ttl, tags=tags)
    
    async def invalidate_by_table(self, table_name: str):
        """Invalidate cache for specific table"""
        tags = self.query_tags.get(table_name.lower(), [table_name.lower()])
        await self.cache.clear_by_tags(tags)


# Global cache instance - lazy initialization to avoid event loop issues
cache_manager = None
query_cache = None

def get_cache_manager() -> MultiTierCache:
    """Lazy initialization of cache manager"""
    global cache_manager
    if cache_manager is None:
        cache_manager = MultiTierCache()
    return cache_manager

def get_query_cache() -> QueryCache:
    """Lazy initialization of query cache"""
    global query_cache
    if query_cache is None:
        query_cache = QueryCache(get_cache_manager())
    return query_cache


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    tags: List[str] = None,
    levels: List[CacheLevel] = None
):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_data = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl=ttl, tags=tags, levels=levels)
            
            return result
        
        return wrapper
    return decorator


def cache_query_result(ttl: int = 300):
    """Decorator for caching database query results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract query information
            query_info = kwargs.get('query_info') or {}
            query_text = query_info.get('query', '')
            query_params = query_info.get('params', {})
            
            if not query_text:
                # If no query info, execute function normally
                return await func(*args, **kwargs)
            
            # Try to get cached result
            cached_result = await query_cache.get_cached_result(query_text, query_params)
            if cached_result is not None:
                logger.debug(f"Query cache hit for: {query_text[:50]}...")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await query_cache.cache_result(query_text, result, query_params, ttl)
            
            logger.debug(f"Query result cached for: {query_text[:50]}...")
            return result
        
        return wrapper
    return decorator


async def get_cache_statistics() -> Dict[str, Any]:
    """Get comprehensive cache statistics"""
    return await cache_manager.get_comprehensive_stats()


async def warm_up_cache():
    """Warm up cache with frequently accessed data"""
    try:
        logger.info("Starting cache warm-up...")
        
        # This would be implemented based on your specific use cases
        # Example: Pre-load user profiles, common queries, etc.
        
        # For now, just log that warm-up is starting
        logger.info("Cache warm-up completed")
        
    except Exception as e:
        logger.error(f"Error during cache warm-up: {str(e)}")
        await log_error(
            e,
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.SYSTEM,
            additional_context={'operation': 'cache_warmup'}
        )


async def invalidate_user_cache(user_id: str):
    """Invalidate all cache entries for a specific user"""
    await cache_manager.clear_by_tags([f"user:{user_id}", "user"])


async def invalidate_table_cache(table_name: str):
    """Invalidate cache for a specific database table"""
    await query_cache.invalidate_by_table(table_name)


# Health check function
async def check_cache_health() -> Dict[str, Any]:
    """Check cache system health"""
    stats = await get_cache_statistics()
    
    health_status = {
        'memory_cache': 'healthy',
        'redis_cache': 'healthy' if stats['redis_cache'].get('connected', False) else 'degraded',
        'overall': 'healthy'
    }
    
    # Check memory cache utilization
    memory_util = stats['memory_cache'].get('utilization', 0)
    if memory_util > 90:
        health_status['memory_cache'] = 'critical'
        health_status['overall'] = 'degraded'
    elif memory_util > 80:
        health_status['memory_cache'] = 'warning'
    
    # Check hit ratios
    hit_ratios = stats['hit_ratios']
    total_hit_ratio = hit_ratios.get('total', 0)
    if total_hit_ratio < 30:
        health_status['overall'] = 'warning'
    
    return {
        'health_status': health_status,
        'statistics': stats,
        'recommendations': _generate_cache_recommendations(stats)
    }


def _generate_cache_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate cache optimization recommendations"""
    recommendations = []
    
    hit_ratios = stats.get('hit_ratios', {})
    total_hit_ratio = hit_ratios.get('total', 0)
    
    if total_hit_ratio < 50:
        recommendations.append("Low cache hit ratio - consider increasing TTL or cache size")
    
    memory_util = stats.get('memory_cache', {}).get('utilization', 0)
    if memory_util > 80:
        recommendations.append("High memory cache utilization - consider increasing max_size")
    
    if not stats.get('redis_cache', {}).get('connected', False):
        recommendations.append("Redis cache not available - consider fixing Redis connection")
    
    return recommendations