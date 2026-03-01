"""
Token Blacklist Service for MITA Finance Application

This service provides comprehensive JWT token blacklisting functionality using Redis
for immediate token revocation, performance optimization, and security incident response.

Features:
- Immediate token revocation with Redis storage
- Performance-optimized blacklist checks (<50ms)
- Automatic cleanup of expired tokens
- Batch operations for efficiency
- Admin functions for security incidents
- Comprehensive logging and monitoring

Security Requirements:
- All revoked tokens are immediately invalid
- Performance impact minimal (<50ms per request)
- Memory usage optimized with TTL management
- Support for both access and refresh tokens
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from contextlib import asynccontextmanager

import redis.asyncio as redis
import jwt
from jwt import InvalidTokenError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)


class TokenType(Enum):
    """Token types supported by blacklist service."""
    ACCESS = "access_token"
    REFRESH = "refresh_token"
    ALL = "all"


class BlacklistReason(Enum):
    """Reasons for token blacklisting."""
    LOGOUT = "user_logout"
    REVOKE = "explicit_revocation"
    SECURITY_INCIDENT = "security_incident"
    ADMIN_REVOKE = "admin_revocation"
    TOKEN_ROTATION = "token_rotation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


@dataclass
class BlacklistEntry:
    """Token blacklist entry with metadata."""
    jti: str
    user_id: str
    token_type: str
    reason: BlacklistReason
    blacklisted_at: datetime
    expires_at: datetime
    revoked_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BlacklistMetrics:
    """Blacklist operation metrics."""
    total_blacklisted: int = 0
    access_tokens_blacklisted: int = 0
    refresh_tokens_blacklisted: int = 0
    blacklist_checks: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cleanup_operations: int = 0
    average_check_time_ms: float = 0.0
    last_cleanup: Optional[datetime] = None
    redis_errors: int = 0


class TokenBlacklistService:
    """
    Comprehensive token blacklist service with Redis backend.
    
    Provides immediate token revocation, performance optimization,
    and administrative functions for security incident response.
    """

    def __init__(self, redis_url: str = None):
        """Initialize blacklist service with Redis connection."""
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_pool = None
        
        # Redis key prefixes for organization
        self.BLACKLIST_PREFIX = "mita:blacklist:token"
        self.USER_TOKENS_PREFIX = "mita:user:tokens"
        self.METRICS_KEY = "mita:blacklist:metrics"
        self.BATCH_KEY = "mita:blacklist:batch"
        
        # Performance settings
        self.BATCH_SIZE = 100
        self.CACHE_TTL = 300  # 5 minutes local cache
        self.MAX_RETRIES = 3
        self.TIMEOUT = 5  # seconds
        
        # Local cache for performance
        self._local_cache: Dict[str, Tuple[bool, float]] = {}
        self._cache_max_size = 1000
        self._metrics = BlacklistMetrics()
        
        # JTI validation pattern (UUID format)
        import re
        self._jti_pattern = re.compile(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        )

    async def initialize(self) -> bool:
        """Initialize Redis connection pool."""
        try:
            if not self.redis_url:
                logger.warning("Redis URL not configured - blacklist service will be disabled")
                return False
            
            self.redis_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_timeout=self.TIMEOUT,
                socket_connect_timeout=self.TIMEOUT
            )
            
            # Test connection
            async with redis.Redis(connection_pool=self.redis_pool) as client:
                await client.ping()
            
            logger.info("Token blacklist service initialized successfully")
            log_security_event("blacklist_service_initialized", {
                "redis_configured": True,
                "cache_size": self._cache_max_size
            })
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize token blacklist service: {e}")
            log_security_event("blacklist_service_init_failed", {"error": str(e)})
            return False

    def _validate_jti(self, jti: str) -> bool:
        """Validate JTI format for security."""
        if not jti or not isinstance(jti, str):
            return False
        return bool(self._jti_pattern.match(jti))

    def _get_blacklist_key(self, jti: str) -> str:
        """Get Redis key for blacklisted token."""
        return f"{self.BLACKLIST_PREFIX}:{jti}"

    def _get_user_tokens_key(self, user_id: str) -> str:
        """Get Redis key for user's active tokens."""
        return f"{self.USER_TOKENS_PREFIX}:{user_id}"

    def _calculate_ttl(self, token: str) -> Optional[int]:
        """Calculate TTL for blacklist entry from token expiration."""
        try:
            # Try current secret
            payload = jwt.decode(
                token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}  # We just want the exp claim
            )
            
            exp = payload.get("exp")
            if exp:
                ttl = max(1, int(exp - time.time()))
                # Cap at 7 days for safety
                return min(ttl, 86400 * 7)
                
        except InvalidTokenError:
            # Try previous secret if available
            if hasattr(settings, 'JWT_PREVIOUS_SECRET') and settings.JWT_PREVIOUS_SECRET:
                try:
                    payload = jwt.decode(
                        token,
                        settings.JWT_PREVIOUS_SECRET,
                        algorithms=[settings.ALGORITHM],
                        options={"verify_exp": False}
                    )
                    exp = payload.get("exp")
                    if exp:
                        ttl = max(1, int(exp - time.time()))
                        return min(ttl, 86400 * 7)
                except InvalidTokenError:
                    pass
        
        # Default TTL if we can't decode token
        return 86400  # 24 hours

    def _extract_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Extract information from token for blacklist entry."""
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False}
            )
            
            return {
                "jti": payload.get("jti"),
                "user_id": payload.get("sub"),
                "token_type": payload.get("token_type", "unknown"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "scope": payload.get("scope", "")
            }
            
        except InvalidTokenError:
            # Try previous secret
            if hasattr(settings, 'JWT_PREVIOUS_SECRET') and settings.JWT_PREVIOUS_SECRET:
                try:
                    payload = jwt.decode(
                        token,
                        settings.JWT_PREVIOUS_SECRET,
                        algorithms=[settings.ALGORITHM],
                        options={"verify_exp": False}
                    )
                    return {
                        "jti": payload.get("jti"),
                        "user_id": payload.get("sub"),
                        "token_type": payload.get("token_type", "unknown"),
                        "exp": payload.get("exp"),
                        "iat": payload.get("iat"),
                        "scope": payload.get("scope", "")
                    }
                except InvalidTokenError:
                    pass
        
        return None

    def _cleanup_local_cache(self):
        """Clean up expired entries from local cache."""
        current_time = time.time()
        expired_keys = [
            key for key, (cached, cache_time) in self._local_cache.items()
            if cache_time + self.CACHE_TTL < current_time
        ]
        
        for key in expired_keys:
            self._local_cache.pop(key, None)
        
        # Limit cache size
        if len(self._local_cache) > self._cache_max_size:
            # Remove oldest entries
            sorted_items = sorted(
                self._local_cache.items(),
                key=lambda x: x[1][1]  # Sort by cache time
            )
            to_remove = len(self._local_cache) - self._cache_max_size
            for i in range(to_remove):
                self._local_cache.pop(sorted_items[i][0], None)

    @asynccontextmanager
    async def _get_redis_client(self):
        """Get Redis client with connection management."""
        if not self.redis_pool:
            raise RuntimeError("Redis pool not initialized")
        
        client = redis.Redis(connection_pool=self.redis_pool)
        try:
            yield client
        finally:
            await client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError))
    )
    async def blacklist_token(
        self,
        token: str,
        reason: BlacklistReason = BlacklistReason.LOGOUT,
        revoked_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Blacklist a JWT token immediately.
        
        Args:
            token: JWT token string to blacklist
            reason: Reason for blacklisting
            revoked_by: ID of user/admin who revoked the token
            metadata: Additional metadata for audit trail
            
        Returns:
            True if successfully blacklisted, False otherwise
        """
        start_time = time.time()
        
        try:
            # Extract token information
            token_info = self._extract_token_info(token)
            if not token_info or not token_info.get("jti"):
                logger.warning("Cannot blacklist token: missing or invalid JTI")
                return False
            
            jti = token_info["jti"]
            user_id = token_info.get("user_id", "unknown")
            token_type = token_info.get("token_type", "unknown")
            
            # Validate JTI format
            if not self._validate_jti(jti):
                logger.warning(f"Invalid JTI format for blacklisting: {jti[:20]}...")
                log_security_event("blacklist_invalid_jti", {
                    "jti_prefix": jti[:8] + "...",
                    "reason": reason.value
                })
                return False
            
            # Calculate TTL
            ttl = self._calculate_ttl(token)
            if not ttl or ttl <= 0:
                logger.warning("Token already expired, skipping blacklist")
                return True
            
            # Create blacklist entry
            {
                "jti": jti,
                "user_id": user_id,
                "token_type": token_type,
                "reason": reason.value,
                "blacklisted_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=ttl)).isoformat(),
                "revoked_by": revoked_by,
                "metadata": metadata or {}
            }
            
            # Store in Redis
            async with self._get_redis_client() as client:
                blacklist_key = self._get_blacklist_key(jti)
                user_tokens_key = self._get_user_tokens_key(user_id)
                
                # Use pipeline for atomic operations
                async with client.pipeline() as pipe:
                    # Blacklist the token
                    pipe.setex(blacklist_key, ttl, "blacklisted")
                    
                    # Add to user's blacklisted tokens set
                    pipe.sadd(user_tokens_key, jti)
                    pipe.expire(user_tokens_key, ttl)
                    
                    # Update metrics
                    pipe.hincrby(self.METRICS_KEY, "total_blacklisted", 1)
                    if token_type == TokenType.ACCESS.value:
                        pipe.hincrby(self.METRICS_KEY, "access_tokens_blacklisted", 1)
                    elif token_type == TokenType.REFRESH.value:
                        pipe.hincrby(self.METRICS_KEY, "refresh_tokens_blacklisted", 1)
                    
                    await pipe.execute()
            
            # Update local cache
            cache_key = hashlib.sha256(jti.encode()).hexdigest()[:16]
            self._local_cache[cache_key] = (True, time.time())
            
            # Update metrics
            self._metrics.total_blacklisted += 1
            if token_type == TokenType.ACCESS.value:
                self._metrics.access_tokens_blacklisted += 1
            elif token_type == TokenType.REFRESH.value:
                self._metrics.refresh_tokens_blacklisted += 1
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            logger.info(f"Token blacklisted successfully: {jti[:8]}... "
                       f"(user: {user_id}, reason: {reason.value}, {elapsed_ms:.2f}ms)")
            
            log_security_event("token_blacklisted", {
                "jti_prefix": jti[:8] + "...",
                "user_id": user_id,
                "token_type": token_type,
                "reason": reason.value,
                "revoked_by": revoked_by,
                "ttl_seconds": ttl,
                "processing_time_ms": elapsed_ms
            })
            
            return True
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Failed to blacklist token: {e} (took {elapsed_ms:.2f}ms)")
            self._metrics.redis_errors += 1
            log_security_event("token_blacklist_failed", {
                "error": str(e),
                "processing_time_ms": elapsed_ms
            })
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError))
    )
    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if a token is blacklisted with performance optimization.
        
        Args:
            jti: JWT ID to check
            
        Returns:
            True if blacklisted, False otherwise
        """
        start_time = time.time()
        
        try:
            # Input validation
            if not self._validate_jti(jti):
                logger.warning(f"Invalid JTI format for blacklist check: {jti[:20]}...")
                return False
            
            # Check local cache first
            cache_key = hashlib.sha256(jti.encode()).hexdigest()[:16]
            if cache_key in self._local_cache:
                cached_result, cache_time = self._local_cache[cache_key]
                if cache_time + self.CACHE_TTL > time.time():
                    self._metrics.cache_hits += 1
                    return cached_result
            
            # Clean up cache periodically
            if len(self._local_cache) > self._cache_max_size * 0.8:
                self._cleanup_local_cache()
            
            # Check Redis
            async with self._get_redis_client() as client:
                blacklist_key = self._get_blacklist_key(jti)
                result = await client.get(blacklist_key)
                is_blacklisted = result is not None
            
            # Update local cache
            self._local_cache[cache_key] = (is_blacklisted, time.time())
            self._metrics.cache_misses += 1
            self._metrics.blacklist_checks += 1
            
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics.average_check_time_ms = (
                (self._metrics.average_check_time_ms * (self._metrics.blacklist_checks - 1) + elapsed_ms)
                / self._metrics.blacklist_checks
            )
            
            if is_blacklisted:
                logger.info(f"Token {jti[:8]}... is blacklisted (check took {elapsed_ms:.2f}ms)")
                log_security_event("blacklisted_token_access_attempt", {
                    "jti_prefix": jti[:8] + "...",
                    "check_time_ms": elapsed_ms
                })
            
            return is_blacklisted
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Error checking token blacklist: {e} (took {elapsed_ms:.2f}ms)")
            self._metrics.redis_errors += 1
            
            # Fail-open for availability (assume not blacklisted on error)
            log_security_event("blacklist_check_failed", {
                "jti_prefix": jti[:8] + "...",
                "error": str(e),
                "processing_time_ms": elapsed_ms,
                "fail_open": True
            })
            return False

    async def blacklist_user_tokens(
        self,
        user_id: str,
        token_type: TokenType = TokenType.ALL,
        reason: BlacklistReason = BlacklistReason.SECURITY_INCIDENT,
        revoked_by: Optional[str] = None
    ) -> int:
        """
        Blacklist all tokens for a specific user.
        
        Args:
            user_id: User ID whose tokens should be blacklisted
            token_type: Type of tokens to blacklist
            reason: Reason for mass revocation
            revoked_by: ID of admin who initiated the revocation
            
        Returns:
            Number of tokens blacklisted
        """
        try:
            async with self._get_redis_client() as client:
                user_tokens_key = self._get_user_tokens_key(user_id)
                token_jtis = await client.smembers(user_tokens_key)
            
            if not token_jtis:
                logger.info(f"No active tokens found for user {user_id}")
                return 0
            
            blacklisted_count = 0
            
            # Process tokens in batches
            for i in range(0, len(token_jtis), self.BATCH_SIZE):
                batch = token_jtis[i:i + self.BATCH_SIZE]
                
                async with self._get_redis_client() as client:
                    async with client.pipeline() as pipe:
                        for jti_bytes in batch:
                            jti = jti_bytes.decode('utf-8') if isinstance(jti_bytes, bytes) else jti_bytes
                            
                            # For user-level revocation, we set a longer TTL
                            # since we don't have individual token expiration times
                            blacklist_key = self._get_blacklist_key(jti)
                            pipe.setex(blacklist_key, 86400 * 7, "user_revocation")  # 7 days
                            blacklisted_count += 1
                        
                        await pipe.execute()
            
            # Clear user's token set
            async with self._get_redis_client() as client:
                await client.delete(user_tokens_key)
            
            logger.info(f"Blacklisted {blacklisted_count} tokens for user {user_id}")
            log_security_event("user_tokens_revoked", {
                "user_id": user_id,
                "tokens_revoked": blacklisted_count,
                "reason": reason.value,
                "revoked_by": revoked_by
            })
            
            return blacklisted_count
            
        except Exception as e:
            logger.error(f"Failed to blacklist user tokens for {user_id}: {e}")
            log_security_event("user_token_revocation_failed", {
                "user_id": user_id,
                "error": str(e)
            })
            raise

    async def revoke_token_by_jti(
        self,
        jti: str,
        reason: BlacklistReason = BlacklistReason.ADMIN_REVOKE,
        revoked_by: Optional[str] = None
    ) -> bool:
        """
        Revoke a token by its JTI (for admin use).
        
        Args:
            jti: JWT ID to revoke
            reason: Reason for revocation
            revoked_by: ID of admin who revoked the token
            
        Returns:
            True if successfully revoked
        """
        try:
            if not self._validate_jti(jti):
                logger.warning(f"Invalid JTI format: {jti}")
                return False
            
            # Set blacklist entry with admin metadata
            async with self._get_redis_client() as client:
                blacklist_key = self._get_blacklist_key(jti)
                ttl = 86400 * 7  # 7 days default for admin revocations
                
                {
                    "reason": reason.value,
                    "revoked_by": revoked_by,
                    "revoked_at": datetime.utcnow().isoformat()
                }
                
                await client.setex(blacklist_key, ttl, f"admin_revocation:{revoked_by}")
            
            # Update local cache
            cache_key = hashlib.sha256(jti.encode()).hexdigest()[:16]
            self._local_cache[cache_key] = (True, time.time())
            
            logger.info(f"Token {jti[:8]}... revoked by admin {revoked_by}")
            log_security_event("admin_token_revocation", {
                "jti_prefix": jti[:8] + "...",
                "reason": reason.value,
                "revoked_by": revoked_by
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke token {jti}: {e}")
            log_security_event("admin_token_revocation_failed", {
                "jti_prefix": jti[:8] + "...",
                "error": str(e)
            })
            return False

    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired blacklist entries (Redis handles TTL automatically).
        This method provides metrics and manual cleanup capabilities.
        
        Returns:
            Number of entries cleaned up (always 0 as Redis handles TTL)
        """
        try:
            # Redis automatically handles TTL cleanup, but we can clean our local cache
            self._cleanup_local_cache()
            
            # Update cleanup metrics
            self._metrics.cleanup_operations += 1
            self._metrics.last_cleanup = datetime.utcnow()
            
            # Get current Redis stats
            async with self._get_redis_client() as client:
                info = await client.info('memory')
                used_memory = info.get('used_memory', 0)
            
            logger.info(f"Blacklist cleanup completed - Redis memory: {used_memory / 1024 / 1024:.2f}MB")
            log_security_event("blacklist_cleanup", {
                "local_cache_size": len(self._local_cache),
                "redis_memory_mb": used_memory / 1024 / 1024,
                "cleanup_operations": self._metrics.cleanup_operations
            })
            
            return 0  # Redis handles cleanup automatically
            
        except Exception as e:
            logger.error(f"Error during blacklist cleanup: {e}")
            log_security_event("blacklist_cleanup_failed", {"error": str(e)})
            return 0

    async def get_blacklist_metrics(self) -> BlacklistMetrics:
        """Get comprehensive blacklist service metrics."""
        try:
            # Get Redis metrics
            async with self._get_redis_client() as client:
                redis_metrics = await client.hgetall(self.METRICS_KEY)
                
                # Convert bytes to appropriate types
                for key, value in redis_metrics.items():
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')
                    if isinstance(value, bytes):
                        value = int(value.decode('utf-8'))
                    setattr(self._metrics, key, value)
            
            # Add current state metrics
            self._metrics.cache_hits = getattr(self._metrics, 'cache_hits', 0)
            self._metrics.cache_misses = getattr(self._metrics, 'cache_misses', 0)
            
            return self._metrics
            
        except Exception as e:
            logger.error(f"Error getting blacklist metrics: {e}")
            return self._metrics

    async def get_user_blacklisted_tokens(self, user_id: str) -> List[str]:
        """Get list of blacklisted token JTIs for a user."""
        try:
            async with self._get_redis_client() as client:
                user_tokens_key = self._get_user_tokens_key(user_id)
                token_jtis = await client.smembers(user_tokens_key)
                
                return [
                    jti.decode('utf-8') if isinstance(jti, bytes) else jti
                    for jti in token_jtis
                ]
        
        except Exception as e:
            logger.error(f"Error getting blacklisted tokens for user {user_id}: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on blacklist service."""
        health_status = {
            "service": "token_blacklist",
            "status": "unknown",
            "redis_connected": False,
            "local_cache_size": len(self._local_cache),
            "metrics": {
                "total_blacklisted": self._metrics.total_blacklisted,
                "blacklist_checks": self._metrics.blacklist_checks,
                "average_check_time_ms": self._metrics.average_check_time_ms,
                "redis_errors": self._metrics.redis_errors
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            if self.redis_pool:
                async with self._get_redis_client() as client:
                    start_time = time.time()
                    await client.ping()
                    ping_time = (time.time() - start_time) * 1000
                    
                    health_status.update({
                        "status": "healthy",
                        "redis_connected": True,
                        "redis_ping_ms": ping_time
                    })
            else:
                health_status["status"] = "disabled"
                health_status["reason"] = "Redis not configured"
                
        except Exception as e:
            health_status.update({
                "status": "unhealthy",
                "redis_connected": False,
                "error": str(e)
            })
        
        return health_status

    async def close(self):
        """Close Redis connection pool."""
        if self.redis_pool:
            await self.redis_pool.disconnect()
            logger.info("Token blacklist service closed")


# Global blacklist service instance
_blacklist_service: Optional[TokenBlacklistService] = None


async def get_blacklist_service() -> TokenBlacklistService:
    """Get or create global blacklist service instance."""
    global _blacklist_service
    
    if _blacklist_service is None:
        _blacklist_service = TokenBlacklistService()
        await _blacklist_service.initialize()
    
    return _blacklist_service


async def cleanup_blacklist_service():
    """Clean up global blacklist service."""
    global _blacklist_service
    
    if _blacklist_service:
        await _blacklist_service.close()
        _blacklist_service = None