import os
import logging
import time
from functools import wraps

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)

UPSTASH_URL = os.getenv("UPSTASH_URL", "https://global.api.upstash.com")
UPSTASH_AUTH_TOKEN = os.getenv("UPSTASH_AUTH_TOKEN")

# Security configuration
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10
BLACKLIST_KEY_PREFIX = "revoked:jwt"

# Metrics tracking
token_operations_count = {"blacklist": 0, "check": 0, "errors": 0}


def _auth_header() -> dict:
    """Get Upstash authentication headers with validation."""
    if not UPSTASH_AUTH_TOKEN:
        logger.critical("UPSTASH_AUTH_TOKEN not configured for token blacklisting")
        raise RuntimeError("UPSTASH_AUTH_TOKEN not configured")
    return {
        "Authorization": f"Bearer {UPSTASH_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }


def _validate_jti(jti: str) -> bool:
    """Validate JWT ID format for security."""
    if not jti or len(jti) < 10 or len(jti) > 100:
        logger.warning(f"Invalid JTI format: {jti[:20]}...")
        return False
    # Additional validation for UUID format
    import re
    uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    return bool(re.match(uuid_pattern, jti))


def _handle_redis_error(operation: str):
    """Decorator for handling Redis operation errors gracefully."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except httpx.TimeoutException as e:
                logger.error(f"Redis timeout during {operation}: {e}")
                token_operations_count["errors"] += 1
                log_security_event("redis_timeout", {"operation": operation, "error": str(e)})
                if operation == "blacklist":
                    # Fail-secure: if we can't blacklist, log critical error
                    logger.critical("CRITICAL: Failed to blacklist token due to timeout")
                    raise RuntimeError(f"Token blacklisting failed: {e}")
                return False  # For check operations, assume not blacklisted on error
            except httpx.HTTPStatusError as e:
                logger.error(f"Redis HTTP error during {operation}: {e.response.status_code} - {e.response.text}")
                token_operations_count["errors"] += 1
                log_security_event("redis_http_error", {
                    "operation": operation, 
                    "status_code": e.response.status_code,
                    "error": str(e)
                })
                if operation == "blacklist":
                    logger.critical("CRITICAL: Failed to blacklist token due to HTTP error")
                    raise RuntimeError(f"Token blacklisting failed: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected Redis error during {operation}: {e}")
                token_operations_count["errors"] += 1
                log_security_event("redis_unexpected_error", {"operation": operation, "error": str(e)})
                if operation == "blacklist":
                    logger.critical("CRITICAL: Failed to blacklist token due to unexpected error")
                    raise RuntimeError(f"Token blacklisting failed: {e}")
                return False
        return wrapper
    return decorator


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError))
)
@_handle_redis_error("blacklist")
def blacklist_token(jti: str, ttl: int) -> None:
    """Blacklist a JWT token by its JTI with enhanced security and monitoring.
    
    Args:
        jti: JWT ID to blacklist
        ttl: Time to live in seconds (should match token expiry)
        
    Raises:
        RuntimeError: If blacklisting fails (fail-secure)
    """
    if not UPSTASH_AUTH_TOKEN:
        logger.critical("UPSTASH_AUTH_TOKEN not configured, cannot blacklist tokens")
        log_security_event("blacklist_config_missing", {"jti": jti[:8] + "..."})
        raise RuntimeError("Redis not configured - token blacklisting unavailable")
    
    # Validate JTI format
    if not _validate_jti(jti):
        logger.warning(f"Attempted to blacklist invalid JTI: {jti[:20]}...")
        log_security_event("blacklist_invalid_jti", {"jti": jti[:8] + "..."})
        return
    
    # Validate TTL
    if ttl <= 0 or ttl > 86400 * 7:  # Max 7 days
        logger.warning(f"Invalid TTL for token blacklisting: {ttl}")
        log_security_event("blacklist_invalid_ttl", {"jti": jti[:8] + "...", "ttl": ttl})
        ttl = min(max(ttl, 1), 86400 * 7)
    
    key = f"{BLACKLIST_KEY_PREFIX}:{jti}"
    url = f"{UPSTASH_URL}/set/{key}?EX={ttl}"
    
    logger.info(f"Blacklisting token JTI: {jti[:8]}... for {ttl}s")
    
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(url, headers=_auth_header(), json={"value": "blacklisted"})
        response.raise_for_status()
    
    token_operations_count["blacklist"] += 1
    log_security_event("token_blacklisted", {
        "jti": jti[:8] + "...",
        "ttl": ttl,
        "timestamp": str(int(time.time()))
    })
    
    logger.debug(f"Successfully blacklisted token JTI: {jti[:8]}...")


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError))
)
@_handle_redis_error("check")
def is_token_blacklisted(jti: str) -> bool:
    """Check if a JWT token is blacklisted with enhanced security.
    
    Args:
        jti: JWT ID to check
        
    Returns:
        bool: True if blacklisted, False if not (fail-open on Redis errors)
    """
    if not UPSTASH_AUTH_TOKEN:
        logger.warning("UPSTASH_AUTH_TOKEN not configured, assuming token is not blacklisted")
        log_security_event("blacklist_check_config_missing", {"jti": jti[:8] + "..."})
        return False
    
    # Validate JTI format
    if not _validate_jti(jti):
        logger.warning(f"Attempted to check invalid JTI: {jti[:20]}...")
        log_security_event("blacklist_check_invalid_jti", {"jti": jti[:8] + "..."})
        return False
    
    key = f"{BLACKLIST_KEY_PREFIX}:{jti}"
    url = f"{UPSTASH_URL}/get/{key}"
    
    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.get(url, headers=_auth_header())
        response.raise_for_status()
        result = response.json().get("result")
    
    token_operations_count["check"] += 1
    is_blacklisted = result is not None
    
    if is_blacklisted:
        logger.info(f"Token JTI {jti[:8]}... is blacklisted")
        log_security_event("blacklisted_token_access_attempted", {"jti": jti[:8] + "..."})
    
    return is_blacklisted


def get_blacklist_metrics() -> dict:
    """Get metrics about token blacklist operations."""
    return token_operations_count.copy()


def cleanup_expired_blacklist_entries() -> int:
    """Clean up expired blacklist entries (Redis handles this automatically with TTL).
    This is a placeholder for monitoring purposes."""
    logger.info("Redis TTL automatically handles blacklist cleanup")
    return 0
