"""
Centralized Password Security Configuration for MITA Finance Application
Provides secure bcrypt settings and performance monitoring for password operations
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import bcrypt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# CENTRALIZED BCRYPT CONFIGURATION
# ============================================================================

# Production-grade bcrypt settings - configurable via environment
BCRYPT_ROUNDS = getattr(settings, 'BCRYPT_ROUNDS_PRODUCTION', 10)  # Optimized for performance while maintaining security
BCRYPT_PERFORMANCE_TARGET_MS = getattr(settings, 'BCRYPT_PERFORMANCE_TARGET_MS', 500)  # Maximum acceptable hash time

# Emergency/development settings (only for testing)
BCRYPT_EMERGENCY_ROUNDS = 8  # Minimum acceptable for emergency scenarios
BCRYPT_DEV_ROUNDS = getattr(settings, 'BCRYPT_ROUNDS_DEVELOPMENT', 10)  # Development balance of security and speed

# Configure PassLib context with secure settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=BCRYPT_ROUNDS
)

# Thread pool for async operations (prevent blocking)
_thread_pool: Optional[ThreadPoolExecutor] = None
_performance_stats = {
    "total_hashes": 0,
    "total_hash_time": 0.0,
    "total_verifications": 0,
    "total_verify_time": 0.0,
    "slow_operations": 0
}

def get_thread_pool() -> ThreadPoolExecutor:
    """Get or create thread pool for password operations"""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(
            max_workers=8,  # Increased for better concurrency
            thread_name_prefix="password_"
        )
    return _thread_pool

def get_bcrypt_rounds() -> int:
    """Get appropriate bcrypt rounds based on environment"""
    env = getattr(settings, 'ENVIRONMENT', 'development')
    
    # Use 12 rounds for all environments to ensure consistency and security
    # Performance is acceptable (<50ms) so no need for environment-specific values
    return BCRYPT_ROUNDS

def validate_password_requirements(password: str) -> None:
    """Validate password meets security requirements"""
    if not password:
        raise ValueError("Password cannot be empty")
    
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    
    if len(password) > 128:
        raise ValueError("Password cannot exceed 128 characters")

# ============================================================================
# SECURE PASSWORD OPERATIONS
# ============================================================================

def hash_password_sync(password: str) -> str:
    """
    Synchronous password hashing with performance monitoring
    Use this for blocking contexts or when async is not needed
    """
    validate_password_requirements(password)
    
    start_time = time.time()
    rounds = get_bcrypt_rounds()
    
    try:
        # Use bcrypt directly for consistent configuration
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=rounds)
        password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        
        # Performance monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        _performance_stats["total_hashes"] += 1
        _performance_stats["total_hash_time"] += elapsed_ms
        
        if elapsed_ms > BCRYPT_PERFORMANCE_TARGET_MS:
            _performance_stats["slow_operations"] += 1
            logger.warning(
                f"Slow password hash operation: {elapsed_ms:.0f}ms "
                f"(target: {BCRYPT_PERFORMANCE_TARGET_MS}ms, rounds: {rounds})"
            )
        else:
            logger.debug(f"Password hashed in {elapsed_ms:.0f}ms with {rounds} rounds")
        
        return password_hash
        
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        raise RuntimeError(f"Password hashing failed: {e}")

async def hash_password_async(password: str) -> str:
    """
    Asynchronous password hashing to prevent blocking the event loop
    Recommended for use in FastAPI endpoints
    """
    validate_password_requirements(password)
    
    # Run in thread pool to prevent blocking
    loop = asyncio.get_event_loop()
    thread_pool = get_thread_pool()
    
    try:
        password_hash = await loop.run_in_executor(
            thread_pool,
            hash_password_sync,
            password
        )
        return password_hash
    except Exception as e:
        logger.error(f"Async password hashing failed: {e}")
        raise

def verify_password_sync(password: str, hashed_password: str) -> bool:
    """
    Synchronous password verification with performance monitoring
    Use this for blocking contexts
    """
    if not password or not hashed_password:
        return False
    
    start_time = time.time()
    
    try:
        # Use bcrypt directly for consistent behavior
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        is_valid = bcrypt.checkpw(password_bytes, hashed_bytes)
        
        # Performance monitoring
        elapsed_ms = (time.time() - start_time) * 1000
        _performance_stats["total_verifications"] += 1
        _performance_stats["total_verify_time"] += elapsed_ms
        
        if elapsed_ms > BCRYPT_PERFORMANCE_TARGET_MS:
            _performance_stats["slow_operations"] += 1
            logger.warning(f"Slow password verification: {elapsed_ms:.0f}ms")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False

async def verify_password_async(password: str, hashed_password: str) -> bool:
    """
    Asynchronous password verification to prevent blocking the event loop
    Recommended for use in FastAPI endpoints
    """
    if not password or not hashed_password:
        return False
    
    # Run in thread pool to prevent blocking
    loop = asyncio.get_event_loop()
    thread_pool = get_thread_pool()
    
    try:
        is_valid = await loop.run_in_executor(
            thread_pool,
            verify_password_sync,
            password,
            hashed_password
        )
        return is_valid
    except Exception as e:
        logger.error(f"Async password verification failed: {e}")
        return False

# ============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================================

def hash_password(password: str) -> str:
    """
    Legacy compatibility function - maps to sync version
    DEPRECATED: Use hash_password_sync() or hash_password_async() instead
    """
    logger.debug("Using legacy hash_password function - consider upgrading to hash_password_sync/async")
    return hash_password_sync(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Legacy compatibility function - maps to sync version
    DEPRECATED: Use verify_password_sync() or verify_password_async() instead
    """
    return verify_password_sync(password, hashed_password)

async def async_hash_password(password: str) -> str:
    """Legacy async function name - maps to new naming convention"""
    return await hash_password_async(password)

async def async_verify_password(password: str, hashed_password: str) -> bool:
    """Legacy async function name - maps to new naming convention"""
    return await verify_password_async(password, hashed_password)

# ============================================================================
# PERFORMANCE MONITORING AND HEALTH
# ============================================================================

def get_password_performance_stats() -> dict:
    """Get password operation performance statistics"""
    stats = _performance_stats.copy()
    
    # Calculate averages
    if stats["total_hashes"] > 0:
        stats["avg_hash_time_ms"] = stats["total_hash_time"] / stats["total_hashes"]
    else:
        stats["avg_hash_time_ms"] = 0.0
    
    if stats["total_verifications"] > 0:
        stats["avg_verify_time_ms"] = stats["total_verify_time"] / stats["total_verifications"]
    else:
        stats["avg_verify_time_ms"] = 0.0
    
    # Add configuration info
    stats["bcrypt_rounds"] = get_bcrypt_rounds()
    stats["performance_target_ms"] = BCRYPT_PERFORMANCE_TARGET_MS
    stats["environment"] = getattr(settings, 'ENVIRONMENT', 'unknown')
    
    return stats

def test_password_performance() -> dict:
    """Test password hashing performance with current configuration"""
    test_password = "TestPassword123!"
    test_results = {
        "bcrypt_rounds": get_bcrypt_rounds(),
        "tests_performed": 3,
        "times_ms": [],
        "average_ms": 0.0,
        "meets_target": False
    }
    
    # Perform multiple tests for accuracy
    for i in range(3):
        start_time = time.time()
        hash_result = hash_password_sync(test_password)
        elapsed_ms = (time.time() - start_time) * 1000
        test_results["times_ms"].append(elapsed_ms)
        
        # Verify the hash works
        if not verify_password_sync(test_password, hash_result):
            logger.error("Password hash verification failed during performance test!")
    
    # Calculate average
    if test_results["times_ms"]:
        test_results["average_ms"] = sum(test_results["times_ms"]) / len(test_results["times_ms"])
        test_results["meets_target"] = test_results["average_ms"] <= BCRYPT_PERFORMANCE_TARGET_MS
    
    logger.info(
        f"Password performance test: {test_results['average_ms']:.0f}ms "
        f"(target: {BCRYPT_PERFORMANCE_TARGET_MS}ms, rounds: {test_results['bcrypt_rounds']})"
    )
    
    return test_results

def reset_performance_stats():
    """Reset performance statistics (useful for monitoring)"""
    global _performance_stats
    _performance_stats = {
        "total_hashes": 0,
        "total_hash_time": 0.0,
        "total_verifications": 0,
        "total_verify_time": 0.0,
        "slow_operations": 0
    }
    logger.info("Password performance statistics reset")

def cleanup_thread_pool():
    """Clean up thread pool resources"""
    global _thread_pool
    if _thread_pool:
        _thread_pool.shutdown(wait=True)
        _thread_pool = None
        logger.info("Password thread pool cleaned up")

# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================

def validate_bcrypt_configuration() -> dict:
    """Validate bcrypt configuration and performance"""
    validation_result = {
        "valid": True,
        "issues": [],
        "warnings": [],
        "configuration": {
            "rounds": get_bcrypt_rounds(),
            "environment": getattr(settings, 'ENVIRONMENT', 'unknown'),
            "performance_target_ms": BCRYPT_PERFORMANCE_TARGET_MS
        }
    }
    
    # Check bcrypt rounds
    rounds = get_bcrypt_rounds()
    if rounds < 10:
        validation_result["issues"].append(
            f"Bcrypt rounds ({rounds}) below recommended minimum (10) for production"
        )
        validation_result["valid"] = False
    elif rounds < 12 and getattr(settings, 'ENVIRONMENT', '') == 'production':
        validation_result["warnings"].append(
            f"Bcrypt rounds ({rounds}) below industry standard (12) for production"
        )
    
    # Test performance
    try:
        perf_test = test_password_performance()
        validation_result["performance"] = perf_test
        
        if not perf_test["meets_target"]:
            validation_result["warnings"].append(
                f"Password hashing performance ({perf_test['average_ms']:.0f}ms) "
                f"exceeds target ({BCRYPT_PERFORMANCE_TARGET_MS}ms)"
            )
    except Exception as e:
        validation_result["issues"].append(f"Performance test failed: {e}")
        validation_result["valid"] = False
    
    # Log validation results
    if validation_result["valid"]:
        if validation_result["warnings"]:
            logger.warning(f"Password security validation passed with warnings: {validation_result['warnings']}")
        else:
            logger.info("Password security validation passed successfully")
    else:
        logger.error(f"Password security validation failed: {validation_result['issues']}")
    
    return validation_result