"""
Advanced Rate Limiting System
Provides comprehensive rate limiting with multiple algorithms and security features
"""

import time
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import redis
from fastapi import Request, HTTPException, status

from app.core.config import settings
from app.core.error_monitoring import log_error, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitRule:
    """Rate limit rule configuration"""
    key: str
    requests: int  # Number of requests allowed
    window: int    # Time window in seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    burst_multiplier: float = 1.5  # Allow burst up to this multiplier
    per: str = "ip"  # Rate limit per: 'ip', 'user', 'endpoint', 'custom'


class RateLimitExceeded(HTTPException):
    """Rate limit exceeded exception"""
    def __init__(self, retry_after: int, limit: int, window: int):
        self.retry_after = retry_after
        self.limit = limit
        self.window = window
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. {limit} requests per {window} seconds allowed. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )


class RateLimiter:
    """Advanced rate limiter with multiple algorithms"""
    
    def __init__(self):
        self.redis_client = self._init_redis()
        self.memory_store: Dict[str, Dict] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
        
        # Default rate limit rules (OPTIMIZED for better UX)
        self.default_rules = {
            'global': RateLimitRule('global', 1500, 3600, per='ip'),  # 1500 per hour per IP (increased from 1000)
            'auth': RateLimitRule('auth', 12, 300, per='ip'),          # 12 auth attempts per 5 min per IP (increased from 5)
            'api': RateLimitRule('api', 200, 300, per='user'),        # 200 API calls per 5 min per user (increased from 100)
            'upload': RateLimitRule('upload', 20, 3600, per='user'),  # 20 uploads per hour per user (increased from 10)
            'heavy': RateLimitRule('heavy', 10, 60, per='user'),       # 10 heavy operations per minute per user (increased from 5)
        }
        
        # Security rules for suspicious behavior (SOFTENED for better UX)
        self.security_rules = {
            'failed_auth': RateLimitRule('failed_auth', 6, 900, per='ip'),      # 6 failed auth per 15 min (increased from 3)
            'suspicious': RateLimitRule('suspicious', 20, 3600, per='ip'),      # 20 suspicious requests per hour (increased from 10)
            'brute_force': RateLimitRule('brute_force', 2, 3600, per='ip'),     # 2 brute force attempts per hour (increased from 1)
        }
    
    def _init_redis(self) -> Optional[redis.Redis]:
        """Initialize Redis connection"""
        try:
            redis_url = getattr(settings, 'REDIS_URL', '')
            if not redis_url:
                logger.info("No Redis URL configured - using in-memory rate limiting")
                return None
            client = redis.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            logger.info("Redis connected for rate limiting")
            return client
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {str(e)}")
            return None
    
    async def check_rate_limit(
        self,
        key: str,
        rule: RateLimitRule,
        request: Request = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit
        
        Returns:
            Tuple of (is_allowed, limit_info)
        """
        # Build full key
        full_key = self._build_key(key, rule, request)
        
        # Choose algorithm
        if rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._sliding_window_check(full_key, rule)
        elif rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._token_bucket_check(full_key, rule)
        else:  # FIXED_WINDOW
            return await self._fixed_window_check(full_key, rule)
    
    def _build_key(self, base_key: str, rule: RateLimitRule, request: Request = None) -> str:
        """Build full rate limit key"""
        if rule.per == 'ip' and request:
            client_ip = self._get_client_ip(request)
            return f"rate_limit:{base_key}:ip:{client_ip}"
        elif rule.per == 'user' and request:
            user_id = getattr(request.state, 'user_id', 'anonymous')
            return f"rate_limit:{base_key}:user:{user_id}"
        elif rule.per == 'endpoint' and request:
            endpoint = f"{request.method}:{request.url.path}"
            return f"rate_limit:{base_key}:endpoint:{endpoint}"
        else:
            return f"rate_limit:{base_key}:custom"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support"""
        # Check for forwarded headers (proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else 'unknown'
    
    async def _sliding_window_check(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """Sliding window rate limiting algorithm"""
        now = time.time()
        window_start = now - rule.window
        
        if self.redis_client:
            return await self._redis_sliding_window(key, rule, now, window_start)
        else:
            return await self._memory_sliding_window(key, rule, now, window_start)
    
    async def _redis_sliding_window(
        self,
        key: str,
        rule: RateLimitRule,
        now: float,
        window_start: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Redis-based sliding window implementation"""
        pipe = self.redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiration
        pipe.expire(key, rule.window)
        
        results = pipe.execute()
        current_count = results[1] + 1  # +1 for the request we just added
        
        # Check if within limit
        allowed = current_count <= rule.requests
        
        if not allowed:
            # Remove the request we just added since it's not allowed
            self.redis_client.zrem(key, str(now))
        
        # Calculate retry after
        if not allowed:
            # Get oldest request time
            oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + rule.window - now)
            else:
                retry_after = rule.window
        else:
            retry_after = 0
        
        return allowed, {
            'limit': rule.requests,
            'remaining': max(0, rule.requests - current_count),
            'reset_time': int(now + rule.window),
            'retry_after': retry_after,
            'window': rule.window
        }
    
    async def _memory_sliding_window(
        self,
        key: str,
        rule: RateLimitRule,
        now: float,
        window_start: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Memory-based sliding window implementation"""
        # Cleanup old data periodically
        if now - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_memory_store(now)
            self.last_cleanup = now
        
        if key not in self.memory_store:
            self.memory_store[key] = {'requests': [], 'last_access': now}
        
        store = self.memory_store[key]
        
        # Remove old requests
        store['requests'] = [req_time for req_time in store['requests'] if req_time > window_start]
        
        current_count = len(store['requests'])
        allowed = current_count < rule.requests
        
        if allowed:
            store['requests'].append(now)
            current_count += 1
        
        store['last_access'] = now
        
        # Calculate retry after
        retry_after = 0
        if not allowed and store['requests']:
            retry_after = int(store['requests'][0] + rule.window - now)
        
        return allowed, {
            'limit': rule.requests,
            'remaining': max(0, rule.requests - current_count),
            'reset_time': int(now + rule.window),
            'retry_after': retry_after,
            'window': rule.window
        }
    
    async def _token_bucket_check(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """Token bucket rate limiting algorithm"""
        now = time.time()
        
        if self.redis_client:
            return await self._redis_token_bucket(key, rule, now)
        else:
            return await self._memory_token_bucket(key, rule, now)
    
    async def _redis_token_bucket(
        self,
        key: str,
        rule: RateLimitRule,
        now: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Redis-based token bucket implementation"""
        bucket_key = f"{key}:bucket"
        
        # Get current bucket state
        bucket_data = self.redis_client.hmget(bucket_key, 'tokens', 'last_refill')
        tokens = float(bucket_data[0] or rule.requests)
        last_refill = float(bucket_data[1] or now)
        
        # Calculate tokens to add
        time_passed = now - last_refill
        tokens_to_add = time_passed * (rule.requests / rule.window)
        tokens = min(rule.requests, tokens + tokens_to_add)
        
        # Check if request is allowed
        allowed = tokens >= 1.0
        
        if allowed:
            tokens -= 1.0
        
        # Update bucket
        self.redis_client.hmset(bucket_key, {
            'tokens': tokens,
            'last_refill': now
        })
        self.redis_client.expire(bucket_key, rule.window * 2)
        
        return allowed, {
            'limit': rule.requests,
            'remaining': int(tokens),
            'reset_time': int(now + ((rule.requests - tokens) * rule.window / rule.requests)),
            'retry_after': 0 if allowed else int((1.0 - tokens) * rule.window / rule.requests),
            'window': rule.window
        }
    
    async def _memory_token_bucket(
        self,
        key: str,
        rule: RateLimitRule,
        now: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """Memory-based token bucket implementation"""
        if key not in self.memory_store:
            self.memory_store[key] = {
                'tokens': float(rule.requests),
                'last_refill': now,
                'last_access': now
            }
        
        bucket = self.memory_store[key]
        
        # Refill tokens
        time_passed = now - bucket['last_refill']
        tokens_to_add = time_passed * (rule.requests / rule.window)
        bucket['tokens'] = min(rule.requests, bucket['tokens'] + tokens_to_add)
        bucket['last_refill'] = now
        bucket['last_access'] = now
        
        # Check if request is allowed
        allowed = bucket['tokens'] >= 1.0
        
        if allowed:
            bucket['tokens'] -= 1.0
        
        return allowed, {
            'limit': rule.requests,
            'remaining': int(bucket['tokens']),
            'reset_time': int(now + ((rule.requests - bucket['tokens']) * rule.window / rule.requests)),
            'retry_after': 0 if allowed else int((1.0 - bucket['tokens']) * rule.window / rule.requests),
            'window': rule.window
        }
    
    async def _fixed_window_check(
        self,
        key: str,
        rule: RateLimitRule
    ) -> Tuple[bool, Dict[str, Any]]:
        """Fixed window rate limiting algorithm"""
        now = time.time()
        window_start = int(now // rule.window) * rule.window
        window_key = f"{key}:window:{window_start}"
        
        if self.redis_client:
            count = self.redis_client.incr(window_key)
            if count == 1:
                self.redis_client.expire(window_key, rule.window)
        else:
            if window_key not in self.memory_store:
                self.memory_store[window_key] = {'count': 0, 'expires': window_start + rule.window}
            
            self.memory_store[window_key]['count'] += 1
            count = self.memory_store[window_key]['count']
        
        allowed = count <= rule.requests
        
        return allowed, {
            'limit': rule.requests,
            'remaining': max(0, rule.requests - count),
            'reset_time': int(window_start + rule.window),
            'retry_after': int(window_start + rule.window - now) if not allowed else 0,
            'window': rule.window
        }
    
    async def _cleanup_memory_store(self, now: float):
        """Clean up expired entries from memory store"""
        expired_keys = []
        
        for key, data in self.memory_store.items():
            # Check if expired (haven't been accessed in 2x window time)
            if 'last_access' in data:
                if now - data['last_access'] > 7200:  # 2 hours
                    expired_keys.append(key)
            elif 'expires' in data:
                if now > data['expires']:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_store[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")
    
    async def record_security_event(
        self,
        event_type: str,
        request: Request,
        additional_context: Dict[str, Any] = None
    ):
        """Record security event and apply additional rate limiting"""
        if event_type in self.security_rules:
            rule = self.security_rules[event_type]
            key = f"security:{event_type}"
            
            allowed, limit_info = await self.check_rate_limit(key, rule, request)
            
            if not allowed:
                # Log security violation
                await log_error(
                    Exception(f"Security rate limit exceeded: {event_type}"),
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.AUTHORIZATION,
                    additional_context={
                        'event_type': event_type,
                        'client_ip': self._get_client_ip(request),
                        'limit_info': limit_info,
                        'additional_context': additional_context
                    }
                )
                
                raise RateLimitExceeded(
                    retry_after=limit_info['retry_after'],
                    limit=rule.requests,
                    window=rule.window
                )
    
    def get_rule(self, rule_name: str) -> Optional[RateLimitRule]:
        """Get rate limit rule by name"""
        return self.default_rules.get(rule_name) or self.security_rules.get(rule_name)
    
    async def get_limit_status(self, key: str, rule: RateLimitRule, request: Request = None) -> Dict[str, Any]:
        """Get current rate limit status without consuming a request"""
        full_key = self._build_key(key, rule, request)
        
        if rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            now = time.time()
            window_start = now - rule.window
            
            if self.redis_client:
                count = self.redis_client.zcount(full_key, window_start, now)
            else:
                if full_key in self.memory_store:
                    requests = self.memory_store[full_key]['requests']
                    count = len([r for r in requests if r > window_start])
                else:
                    count = 0
            
            return {
                'limit': rule.requests,
                'remaining': max(0, rule.requests - count),
                'reset_time': int(now + rule.window),
                'window': rule.window
            }
        
        # For other algorithms, we need to simulate the check
        allowed, limit_info = await self.check_rate_limit(key, rule, request)
        if allowed:
            # Compensate for the consumed request
            limit_info['remaining'] += 1
        
        return limit_info


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(rule_name: str = 'api'):
    """Decorator for applying rate limiting to endpoints"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract request from arguments
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                # Try to find request in kwargs
                request = kwargs.get('request')
            
            if request:
                rule = rate_limiter.get_rule(rule_name)
                if rule:
                    allowed, limit_info = await rate_limiter.check_rate_limit(
                        rule_name, rule, request
                    )
                    
                    if not allowed:
                        raise RateLimitExceeded(
                            retry_after=limit_info['retry_after'],
                            limit=rule.requests,
                            window=rule.window
                        )
                    
                    # Add rate limit headers to response
                    response = await func(*args, **kwargs)
                    if hasattr(response, 'headers'):
                        response.headers['X-RateLimit-Limit'] = str(limit_info['limit'])
                        response.headers['X-RateLimit-Remaining'] = str(limit_info['remaining'])
                        response.headers['X-RateLimit-Reset'] = str(limit_info['reset_time'])
                    
                    return response
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator