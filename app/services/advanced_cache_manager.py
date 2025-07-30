"""
Advanced Cache Management System for MITA Backend
Multi-tier caching with intelligent eviction, compression, and analytics
"""

import time
import logging
import hashlib
import pickle
import gzip
import json
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from threading import RLock, Thread
from enum import Enum
import asyncio
import weakref

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

try:
    import memcache
    MEMCACHED_AVAILABLE = True
except ImportError:
    MEMCACHED_AVAILABLE = False
    memcache = None

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheLevel(Enum):
    """Cache level enumeration"""
    L1_MEMORY = 1    # In-memory cache (fastest)
    L2_REDIS = 2     # Redis cache (fast, persistent)
    L3_MEMCACHED = 3 # Memcached (medium speed)
    L4_DATABASE = 4  # Database cache (slowest, most persistent)


class EvictionPolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"           # Least Recently Used
    LFU = "lfu"           # Least Frequently Used
    TTL = "ttl"           # Time To Live
    RANDOM = "random"     # Random eviction
    FIFO = "fifo"         # First In, First Out


@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    compressed: bool = False
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl_seconds is None:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)
    
    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds"""
        return (datetime.now() - self.created_at).total_seconds()
    
    def update_access(self):
        """Update access statistics"""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        return 100.0 - self.hit_rate


class CacheBackend(ABC):
    """Abstract cache backend interface"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        pass
    
    @abstractmethod
    def get_stats(self) -> CacheStats:
        pass


class MemoryCache(CacheBackend):
    """High-performance in-memory cache with advanced features"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100, 
                 eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
                 compression_threshold: int = 1024):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.eviction_policy = eviction_policy
        self.compression_threshold = compression_threshold
        
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order = OrderedDict()  # For LRU
        self._frequency_counter = defaultdict(int)  # For LFU
        self._stats = CacheStats()
        self._lock = RLock()
        
        # Background cleanup thread
        self._cleanup_thread = Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired:
                del self._cache[key]
                self._access_order.pop(key, None)
                self._stats.misses += 1
                self._stats.evictions += 1
                return None
            
            # Update access statistics
            entry.update_access()
            self._update_access_tracking(key)
            self._stats.hits += 1
            
            # Decompress if needed
            value = entry.value
            if entry.compressed:
                value = self._decompress(value)
            
            return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        with self._lock:
            try:
                # Serialize and potentially compress
                serialized_value, compressed = self._serialize_and_compress(value)
                size_bytes = len(pickle.dumps(serialized_value))
                
                # Check memory limits
                if size_bytes > self.max_memory_bytes:
                    logger.warning(f"Value too large for cache: {size_bytes} bytes")
                    return False
                
                # Evict if necessary
                while (len(self._cache) >= self.max_size or 
                       self._get_total_size() + size_bytes > self.max_memory_bytes):
                    if not self._evict_one():
                        break
                
                # Create cache entry
                entry = CacheEntry(
                    key=key,
                    value=serialized_value,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    ttl_seconds=ttl,
                    size_bytes=size_bytes,
                    compressed=compressed
                )
                
                # Store entry
                self._cache[key] = entry
                self._update_access_tracking(key)
                self._stats.sets += 1
                self._stats.size_bytes += size_bytes
                self._stats.entry_count = len(self._cache)
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to set cache entry {key}: {e}")
                return False
    
    async def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                del self._cache[key]
                self._access_order.pop(key, None)
                self._stats.deletes += 1
                self._stats.size_bytes -= entry.size_bytes
                self._stats.entry_count = len(self._cache)
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        with self._lock:
            return key in self._cache and not self._cache[key].is_expired
    
    async def clear(self) -> bool:
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._frequency_counter.clear()
            self._stats = CacheStats()
            return True
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        with self._lock:
            self._stats.entry_count = len(self._cache)
            return self._stats
    
    def _serialize_and_compress(self, value: Any) -> tuple[Any, bool]:
        """Serialize and optionally compress value"""
        # Simple JSON serialization for basic types
        if isinstance(value, (str, int, float, bool, list, dict)):
            serialized = json.dumps(value).encode('utf-8')
        else:
            serialized = pickle.dumps(value)
        
        # Compress if above threshold
        if len(serialized) > self.compression_threshold:
            compressed_data = gzip.compress(serialized)
            if len(compressed_data) < len(serialized):
                return compressed_data, True
        
        return serialized, False
    
    def _decompress(self, value: Any) -> Any:
        """Decompress and deserialize value"""
        try:
            decompressed = gzip.decompress(value)
            # Try JSON first, then pickle
            try:
                return json.loads(decompressed.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return pickle.loads(decompressed)
        except Exception as e:
            logger.error(f"Failed to decompress cache value: {e}")
            return None
    
    def _update_access_tracking(self, key: str):
        """Update access tracking for eviction policies"""
        if self.eviction_policy == EvictionPolicy.LRU:
            self._access_order[key] = datetime.now()
            self._access_order.move_to_end(key)
        elif self.eviction_policy == EvictionPolicy.LFU:
            self._frequency_counter[key] += 1
    
    def _evict_one(self) -> bool:
        """Evict one entry based on policy"""
        if not self._cache:
            return False
        
        key_to_evict = None
        
        if self.eviction_policy == EvictionPolicy.LRU:
            key_to_evict = next(iter(self._access_order))  # First (oldest) key
        
        elif self.eviction_policy == EvictionPolicy.LFU:
            min_freq = min(self._frequency_counter.values())
            for key, freq in self._frequency_counter.items():
                if freq == min_freq and key in self._cache:
                    key_to_evict = key
                    break
        
        elif self.eviction_policy == EvictionPolicy.TTL:
            # Find expired entries first, then oldest
            now = datetime.now()
            for key, entry in self._cache.items():
                if entry.is_expired:
                    key_to_evict = key
                    break
            if not key_to_evict:
                key_to_evict = min(self._cache.keys(), 
                                 key=lambda k: self._cache[k].created_at)
        
        elif self.eviction_policy == EvictionPolicy.FIFO:
            key_to_evict = min(self._cache.keys(), 
                             key=lambda k: self._cache[k].created_at)
        
        elif self.eviction_policy == EvictionPolicy.RANDOM:
            import random
            key_to_evict = random.choice(list(self._cache.keys()))
        
        if key_to_evict:
            entry = self._cache[key_to_evict]
            del self._cache[key_to_evict]
            self._access_order.pop(key_to_evict, None)
            self._frequency_counter.pop(key_to_evict, None)
            self._stats.evictions += 1
            self._stats.size_bytes -= entry.size_bytes
            return True
        
        return False
    
    def _get_total_size(self) -> int:
        """Get total cache size in bytes"""
        return sum(entry.size_bytes for entry in self._cache.values())
    
    def _cleanup_loop(self):
        """Background cleanup of expired entries"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                with self._lock:
                    expired_keys = [
                        key for key, entry in self._cache.items()
                        if entry.is_expired
                    ]
                    for key in expired_keys:
                        entry = self._cache[key]
                        del self._cache[key]
                        self._access_order.pop(key, None)
                        self._frequency_counter.pop(key, None)
                        self._stats.evictions += 1
                        self._stats.size_bytes -= entry.size_bytes
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")


class RedisCache(CacheBackend):
    """Redis-based cache backend"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 key_prefix: str = "mita_cache:", compression_threshold: int = 1024):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available")
        
        self.redis_client = redis.from_url(redis_url)
        self.key_prefix = key_prefix
        self.compression_threshold = compression_threshold
        self._stats = CacheStats()
    
    def _make_key(self, key: str) -> str:
        """Create full Redis key with prefix"""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        try:
            redis_key = self._make_key(key)
            data = self.redis_client.get(redis_key)
            
            if data is None:
                self._stats.misses += 1
                return None
            
            # Deserialize
            value = self._deserialize(data)
            self._stats.hits += 1
            return value
            
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            self._stats.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in Redis"""
        try:
            redis_key = self._make_key(key)
            serialized_data = self._serialize(value)
            
            if ttl:
                result = self.redis_client.setex(redis_key, ttl, serialized_data)
            else:
                result = self.redis_client.set(redis_key, serialized_data)
            
            if result:
                self._stats.sets += 1
                return True
            return False
            
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            redis_key = self._make_key(key)
            result = self.redis_client.delete(redis_key)
            if result:
                self._stats.deletes += 1
                return True
            return False
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            redis_key = self._make_key(key)
            return bool(self.redis_client.exists(redis_key))
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False
    
    async def clear(self) -> bool:
        """Clear all keys with prefix"""
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        return self._stats
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize and optionally compress value"""
        if isinstance(value, (str, int, float, bool, list, dict)):
            data = json.dumps(value).encode('utf-8')
        else:
            data = pickle.dumps(value)
        
        # Compress if above threshold
        if len(data) > self.compression_threshold:
            compressed = gzip.compress(data)
            if len(compressed) < len(data):
                return b'GZIP:' + compressed
        
        return data
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize and decompress value"""
        try:
            # Check for compression marker
            if data.startswith(b'GZIP:'):
                data = gzip.decompress(data[5:])
            
            # Try JSON first, then pickle
            try:
                return json.loads(data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to deserialize cache data: {e}")
            return None


class MultiTierCache:
    """Multi-tier cache system with intelligent promotion/demotion"""
    
    def __init__(self, tiers: List[CacheBackend], 
                 promotion_threshold: int = 3, demotion_threshold: int = 10):
        self.tiers = tiers
        self.promotion_threshold = promotion_threshold
        self.demotion_threshold = demotion_threshold
        self._access_counter = defaultdict(int)
        self._tier_stats = {i: CacheStats() for i in range(len(tiers))}
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache tiers"""
        for tier_idx, tier in enumerate(self.tiers):
            try:
                value = await tier.get(key)
                if value is not None:
                    self._access_counter[key] += 1
                    self._tier_stats[tier_idx].hits += 1
                    
                    # Promote to higher tiers if accessed frequently
                    if (self._access_counter[key] >= self.promotion_threshold and 
                        tier_idx > 0):
                        await self._promote_to_higher_tiers(key, value, tier_idx)
                    
                    return value
                else:
                    self._tier_stats[tier_idx].misses += 1
            except Exception as e:
                logger.error(f"Error accessing tier {tier_idx}: {e}")
                continue
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                  tier_level: Optional[int] = None) -> bool:
        """Set value in cache tiers"""
        if tier_level is not None:
            # Set in specific tier
            if 0 <= tier_level < len(self.tiers):
                result = await self.tiers[tier_level].set(key, value, ttl)
                if result:
                    self._tier_stats[tier_level].sets += 1
                return result
            return False
        else:
            # Set in all tiers (write-through)
            results = []
            for tier_idx, tier in enumerate(self.tiers):
                try:
                    result = await tier.set(key, value, ttl)
                    results.append(result)
                    if result:
                        self._tier_stats[tier_idx].sets += 1
                except Exception as e:
                    logger.error(f"Error setting in tier {tier_idx}: {e}")
                    results.append(False)
            
            return any(results)
    
    async def delete(self, key: str) -> bool:
        """Delete from all tiers"""
        results = []
        for tier_idx, tier in enumerate(self.tiers):
            try:
                result = await tier.delete(key)
                results.append(result)
                if result:
                    self._tier_stats[tier_idx].deletes += 1
            except Exception as e:
                logger.error(f"Error deleting from tier {tier_idx}: {e}")
                results.append(False)
        
        # Clean up access counter
        self._access_counter.pop(key, None)
        
        return any(results)
    
    async def clear(self) -> bool:
        """Clear all tiers"""
        results = []
        for tier in self.tiers:
            try:
                result = await tier.clear()
                results.append(result)
            except Exception as e:
                logger.error(f"Error clearing tier: {e}")
                results.append(False)
        
        self._access_counter.clear()
        return all(results)
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get statistics for all tiers"""
        stats = {}
        for tier_idx, tier in enumerate(self.tiers):
            tier_name = f"tier_{tier_idx}"
            stats[tier_name] = asdict(tier.get_stats())
        
        # Overall statistics
        total_hits = sum(s.hits for s in self._tier_stats.values())
        total_misses = sum(s.misses for s in self._tier_stats.values())
        
        stats['overall'] = {
            'total_hits': total_hits,
            'total_misses': total_misses,
            'hit_rate': (total_hits / max(total_hits + total_misses, 1)) * 100,
            'frequently_accessed_keys': len([k for k, c in self._access_counter.items() if c >= self.promotion_threshold])
        }
        
        return stats
    
    async def _promote_to_higher_tiers(self, key: str, value: Any, current_tier: int):
        """Promote key to higher (faster) tiers"""
        for tier_idx in range(current_tier):
            try:
                await self.tiers[tier_idx].set(key, value)
                logger.debug(f"Promoted key {key} to tier {tier_idx}")
            except Exception as e:
                logger.error(f"Failed to promote key {key} to tier {tier_idx}: {e}")


class SmartCacheManager:
    """Intelligent cache manager with analytics and optimization"""
    
    def __init__(self, cache_backend: Union[CacheBackend, MultiTierCache]):
        self.cache = cache_backend
        self._analytics = {
            'access_patterns': defaultdict(list),
            'key_popularity': defaultdict(int),
            'cache_effectiveness': defaultdict(float),
            'optimization_suggestions': []
        }
        self._key_tags = defaultdict(set)
    
    async def get(self, key: str, tags: List[str] = None) -> Optional[Any]:
        """Get with analytics tracking"""
        start_time = time.time()
        value = await self.cache.get(key)
        end_time = time.time()
        
        # Track analytics
        self._track_access(key, value is not None, end_time - start_time, tags)
        
        return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, 
                  tags: List[str] = None) -> bool:
        """Set with tagging support"""
        result = await self.cache.set(key, value, ttl)
        
        if result and tags:
            self._key_tags[key].update(tags)
        
        return result
    
    async def get_or_set(self, key: str, factory: Callable, 
                        ttl: Optional[int] = None, tags: List[str] = None) -> Any:
        """Get value or set using factory function"""
        value = await self.get(key, tags)
        
        if value is None:
            # Generate value using factory
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
            
            await self.set(key, value, ttl, tags)
        
        return value
    
    async def delete_by_tags(self, tags: List[str]) -> int:
        """Delete all keys with specified tags"""
        keys_to_delete = []
        
        for key, key_tags in self._key_tags.items():
            if any(tag in key_tags for tag in tags):
                keys_to_delete.append(key)
        
        deleted_count = 0
        for key in keys_to_delete:
            if await self.cache.delete(key):
                deleted_count += 1
                self._key_tags.pop(key, None)
        
        return deleted_count
    
    def _track_access(self, key: str, hit: bool, response_time: float, tags: List[str]):
        """Track access patterns for analytics"""
        now = datetime.now()
        
        self._analytics['access_patterns'][key].append({
            'timestamp': now,
            'hit': hit,
            'response_time': response_time,
            'tags': tags or []
        })
        
        if hit:
            self._analytics['key_popularity'][key] += 1
        
        # Keep only recent access patterns (last 1000 per key)
        if len(self._analytics['access_patterns'][key]) > 1000:
            self._analytics['access_patterns'][key] = self._analytics['access_patterns'][key][-1000:]
    
    def get_analytics_report(self) -> Dict[str, Any]:
        """Generate comprehensive analytics report"""
        now = datetime.now()
        
        # Popular keys
        popular_keys = sorted(
            self._analytics['key_popularity'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        
        # Cache effectiveness by key
        effectiveness = {}
        for key, accesses in self._analytics['access_patterns'].items():
            if accesses:
                hits = sum(1 for a in accesses if a['hit'])
                total = len(accesses)
                effectiveness[key] = (hits / total) * 100
        
        # Recent activity (last hour)
        recent_activity = defaultdict(int)
        one_hour_ago = now - timedelta(hours=1)
        
        for key, accesses in self._analytics['access_patterns'].items():
            recent_accesses = [a for a in accesses if a['timestamp'] > one_hour_ago]
            recent_activity[key] = len(recent_accesses)
        
        # Cache statistics
        cache_stats = {}
        if hasattr(self.cache, 'get_comprehensive_stats'):
            cache_stats = self.cache.get_comprehensive_stats()
        elif hasattr(self.cache, 'get_stats'):
            cache_stats = asdict(self.cache.get_stats())
        
        return {
            'timestamp': now.isoformat(),
            'popular_keys': popular_keys,
            'cache_effectiveness': dict(sorted(effectiveness.items(), key=lambda x: x[1], reverse=True)[:20]),
            'recent_activity': dict(sorted(recent_activity.items(), key=lambda x: x[1], reverse=True)[:20]),
            'cache_statistics': cache_stats,
            'optimization_suggestions': self._generate_optimization_suggestions(),
            'tag_analysis': self._analyze_tags()
        }
    
    def _generate_optimization_suggestions(self) -> List[str]:
        """Generate cache optimization suggestions"""
        suggestions = []
        
        # Analyze hit rates
        for key, accesses in self._analytics['access_patterns'].items():
            if len(accesses) >= 10:  # Only analyze keys with sufficient data
                hits = sum(1 for a in accesses if a['hit'])
                hit_rate = (hits / len(accesses)) * 100
                
                if hit_rate < 20:
                    suggestions.append(f"Low hit rate for key '{key}' ({hit_rate:.1f}%) - consider increasing TTL or removing")
                elif hit_rate > 90 and self._analytics['key_popularity'][key] > 50:
                    suggestions.append(f"Highly effective key '{key}' ({hit_rate:.1f}% hit rate) - consider promoting to higher cache tier")
        
        # Analyze access patterns
        popular_keys = [k for k, count in self._analytics['key_popularity'].items() if count > 100]
        if len(popular_keys) > 50:
            suggestions.append(f"Many popular keys ({len(popular_keys)}) - consider implementing key partitioning")
        
        # Memory usage suggestions
        if hasattr(self.cache, 'get_stats'):
            stats = self.cache.get_stats()
            if stats.entry_count > 5000:
                suggestions.append(f"High entry count ({stats.entry_count}) - consider implementing more aggressive eviction")
        
        return suggestions or ["Cache performance is optimal"]
    
    def _analyze_tags(self) -> Dict[str, Any]:
        """Analyze tag usage patterns"""
        tag_counts = defaultdict(int)
        tag_key_counts = defaultdict(int)
        
        for key, tags in self._key_tags.items():
            for tag in tags:
                tag_counts[tag] += 1
                tag_key_counts[tag] += 1
        
        return {
            'most_popular_tags': dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'total_tags': len(tag_counts),
            'total_tagged_keys': len(self._key_tags),
            'avg_tags_per_key': sum(len(tags) for tags in self._key_tags.values()) / max(len(self._key_tags), 1)
        }


# Factory functions for easy setup
def create_memory_cache(max_size: int = 1000, max_memory_mb: int = 100) -> MemoryCache:
    """Create optimized memory cache"""
    return MemoryCache(max_size=max_size, max_memory_mb=max_memory_mb)


def create_redis_cache(redis_url: str = "redis://localhost:6379") -> Optional[RedisCache]:
    """Create Redis cache if available"""
    if not REDIS_AVAILABLE:
        logger.warning("Redis not available, falling back to memory cache")
        return None
    
    try:
        return RedisCache(redis_url)
    except Exception as e:
        logger.error(f"Failed to create Redis cache: {e}")
        return None


def create_multi_tier_cache(redis_url: str = "redis://localhost:6379") -> MultiTierCache:
    """Create optimized multi-tier cache system"""
    tiers = []
    
    # L1: Memory cache (fastest)
    tiers.append(create_memory_cache(max_size=500, max_memory_mb=50))
    
    # L2: Redis cache (if available)
    redis_cache = create_redis_cache(redis_url)
    if redis_cache:
        tiers.append(redis_cache)
    
    return MultiTierCache(tiers)


def create_smart_cache_manager(redis_url: str = "redis://localhost:6379") -> SmartCacheManager:
    """Create intelligent cache manager with multi-tier backend"""
    cache_backend = create_multi_tier_cache(redis_url)
    return SmartCacheManager(cache_backend)


# Global cache manager instance
_global_cache_manager: Optional[SmartCacheManager] = None

def get_cache_manager() -> SmartCacheManager:
    """Get global cache manager instance"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = create_smart_cache_manager()
    return _global_cache_manager