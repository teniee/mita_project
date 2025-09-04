# Query Result Caching Implementation
# Redis-based caching for expensive queries

import json
from typing import Any, Optional
from datetime import timedelta
import redis

class QueryCache:
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 300):
        self.redis = redis_client
        self.default_ttl = default_ttl
    
    def _get_cache_key(self, query_type: str, user_id: str, params: dict = None) -> str:
        import hashlib
        key_parts = [query_type, user_id]
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        key_string = ":".join(key_parts)
        return f"query_cache:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def get(self, query_type: str, user_id: str, params: dict = None) -> Optional[Any]:
        """Get cached query result"""
        cache_key = self._get_cache_key(query_type, user_id, params)
        cached_data = self.redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
        return None
    
    def set(self, query_type: str, user_id: str, result: Any, 
            params: dict = None, ttl: int = None) -> None:
        """Cache query result"""
        cache_key = self._get_cache_key(query_type, user_id, params)
        ttl = ttl or self.default_ttl
        self.redis.setex(cache_key, ttl, json.dumps(result, default=str))

# Usage example
async def get_user_monthly_expenses_cached(user_id: str, year: int, month: int):
    cache_key_params = {'year': year, 'month': month}
    
    # Try cache first
    cached_result = query_cache.get('monthly_expenses', user_id, cache_key_params)
    if cached_result:
        return cached_result
    
    # Query database
    result = await expensive_monthly_expenses_query(user_id, year, month)
    
    # Cache for 1 hour
    query_cache.set('monthly_expenses', user_id, result, cache_key_params, ttl=3600)
    
    return result
