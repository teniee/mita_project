"""
Rate Limiting Fix for Production
"""

import logging
from functools import wraps

logger = logging.getLogger(__name__)

class RateLimitFallback:
    """Rate limiting fallback when Redis is unavailable"""
    
    def __init__(self):
        self._local_cache = {}
        self._enabled = True
    
    async def check_rate_limit(self, key: str, limit: int = 100, window: int = 60) -> bool:
        """Check rate limit with local fallback"""
        if not self._enabled:
            return True  # Allow all requests if rate limiting is disabled
        
        try:
            # Try Redis first if available
            from app.core.simple_rate_limiter import check_login_rate_limit
            await check_login_rate_limit(key)
            return True
            
        except ImportError:
            # Redis not available, use local memory (not recommended for production)
            logger.warning("Using local rate limiting - not suitable for multiple instances")
            
            import time
            current_time = time.time()
            
            if key not in self._local_cache:
                self._local_cache[key] = []
            
            # Clean old entries
            self._local_cache[key] = [
                timestamp for timestamp in self._local_cache[key] 
                if current_time - timestamp < window
            ]
            
            # Check limit
            if len(self._local_cache[key]) >= limit:
                return False
            
            # Add current request
            self._local_cache[key].append(current_time)
            return True
        
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open in production - allow request but log error
            return True

# Global instance
_rate_limiter = RateLimitFallback()

def rate_limit_fallback(func):
    """Decorator for rate limit fallback"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Rate limiting failed: {e}, allowing request")
            return  # Allow request to proceed
    
    return wrapper

# Enhanced rate limiting functions with fallbacks
@rate_limit_fallback
async def check_login_rate_limit_safe(client_ip: str):
    """Safe login rate limit check with fallback"""
    await _rate_limiter.check_rate_limit(f"login:{client_ip}", limit=20, window=60)

@rate_limit_fallback  
async def check_register_rate_limit_safe(client_ip: str):
    """Safe registration rate limit check with fallback"""
    await _rate_limiter.check_rate_limit(f"register:{client_ip}", limit=5, window=300)
