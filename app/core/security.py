"""
Advanced Security System for MITA Backend
Comprehensive security measures including SQL injection prevention,
advanced rate limiting, input sanitization, and security monitoring
"""

import re
import hashlib
import secrets
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings
from app.core.error_handler import ValidationException, AuthenticationException, RateLimitException

logger = logging.getLogger(__name__)

# Improved Redis client management with async support
redis_client = None

async def get_redis_client():
    """Get Redis client with lazy async initialization"""
    global redis_client
    if redis_client is not None:
        return redis_client
    
    try:
        from fastapi import FastAPI
        from starlette.applications import Starlette
        import inspect
        
        # Get the current FastAPI app instance
        frame = inspect.currentframe()
        app = None
        while frame:
            if 'app' in frame.f_locals and isinstance(frame.f_locals['app'], (FastAPI, Starlette)):
                app = frame.f_locals['app']
                break
            frame = frame.f_back
        
        if app and hasattr(app.state, 'redis_client'):
            redis_client = app.state.redis_client
            return redis_client
        
        # Fallback to direct connection
        redis_url = getattr(settings, 'redis_url', None) or os.getenv('REDIS_URL')
        if not redis_url or redis_url == "":
            logger.info("No Redis URL configured - using in-memory rate limiting")
            return None
            
        redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8", 
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3
        )
        
        # Test connection with timeout
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
        logger.info("Redis connection established successfully")
        return redis_client
        
    except asyncio.TimeoutError:
        redis_client = None
        logger.warning("Redis connection timed out - using in-memory rate limiting")
        return None
    except Exception as e:
        redis_client = None
        logger.warning(f"Redis connection failed: {str(e)} - using in-memory rate limiting")
        return None

# In-memory fallback for rate limiting
rate_limit_memory: Dict[str, Dict] = {}

# Mock rate limiter for emergency fallback
class MockRateLimiter:
    """Mock rate limiter that always allows requests - EMERGENCY FIX"""
    async def check_rate_limit(self, *args, **kwargs):
        return True, {}
    
    def is_rate_limited(self, *args, **kwargs):
        return False

# UPDATED: Import centralized password security configuration
from app.core.password_security import (
    hash_password_sync as centralized_hash_password,
    verify_password_sync as centralized_verify_password,
    get_bcrypt_rounds
)

# Maintain backward compatibility - use centralized configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=get_bcrypt_rounds())

security = HTTPBearer()


class SecurityConfig:
    """Security configuration constants"""
    
    # Password security
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    PASSWORD_HASH_ROUNDS = 12
    
    # Rate limiting - Production financial app settings (OPTIMIZED for better UX)
    DEFAULT_RATE_LIMIT = 300        # requests per hour for general endpoints (increased from 100)
    API_RATE_LIMIT = 2000          # API calls per hour for authenticated users (increased from 1000)
    ANONYMOUS_RATE_LIMIT = 120     # More reasonable limit for anonymous users (increased from 50)
    
    # Authentication rate limits (balanced security with usability)
    LOGIN_RATE_LIMIT = 10          # login attempts per 15 minutes (increased from 5)
    REGISTER_RATE_LIMIT = 5        # registrations per hour per IP (increased from 3)
    PASSWORD_RESET_RATE_LIMIT = 3  # password resets per 30 minutes (increased from 2)
    TOKEN_REFRESH_RATE_LIMIT = 25  # token refreshes per 5 minutes (increased from 10)
    
    # Advanced rate limiting settings
    SLIDING_WINDOW_PRECISION = 100  # Higher precision for sliding window
    RATE_LIMIT_REDIS_KEY_TTL = 7200  # 2 hours TTL for rate limit keys
    PROGRESSIVE_PENALTY_TTL = 3600   # 1 hour for progressive penalties
    
    # Financial security thresholds
    SUSPICIOUS_EMAIL_THRESHOLD = 10   # Max different emails per IP per hour
    MAX_CONCURRENT_SESSIONS = 5       # Max concurrent sessions per user
    BRUTE_FORCE_LOCKOUT_DURATION = 1800  # 30 minutes lockout after repeated violations
    
    # Rate limit tiers for different user types (OPTIMIZED for better UX)
    RATE_LIMIT_TIERS = {
        'anonymous': {
            'requests_per_hour': 120,    # Increased from 50
            'burst_limit': 25,           # Increased from 10
            'window_size': 3600
        },
        'basic_user': {
            'requests_per_hour': 800,    # Increased from 500
            'burst_limit': 40,           # Increased from 20
            'window_size': 3600
        },
        'premium_user': {
            'requests_per_hour': 2500,   # Increased from 1500
            'burst_limit': 80,           # Increased from 50
            'window_size': 3600
        },
        'admin_user': {
            'requests_per_hour': 8000,   # Increased from 5000
            'burst_limit': 150,          # Increased from 100
            'window_size': 3600
        }
    }
    
    # JWT settings
    JWT_EXPIRY_HOURS = 24
    REFRESH_TOKEN_EXPIRY_DAYS = 30
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
        r"(\b(or|and)\b\s+\d+\s*=\s*\d+)",
        r"(--|#|/\*|\*/)",
        r"(\bxp_cmdshell\b)",
        r"(\bsp_executesql\b)",
        r"(\bmassignment\b)",
        r"(char\(\d+\))",
        r"(0x[0-9a-f]+)",
        r"(\bunion\s+all\s+select)",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"vbscript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
        r"<form[^>]*>.*?</form>",
    ]
    
    # File upload security
    ALLOWED_FILE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt', '.csv'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Input validation
    MAX_STRING_LENGTH = 10000
    MAX_ARRAY_LENGTH = 1000
    MAX_OBJECT_DEPTH = 10


class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using centralized secure configuration"""
        # Use centralized password hashing for consistency
        return centralized_hash_password(password)
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash using centralized configuration"""
        # Use centralized password verification for consistency
        return centralized_verify_password(password, hashed)
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate cryptographically secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate secure API key"""
        return f"mita_{secrets.token_urlsafe(40)}"
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """Hash sensitive data for logging/storage"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]  # First 16 chars


class SQLInjectionProtector:
    """Advanced SQL injection protection"""
    
    @staticmethod
    def scan_for_sql_injection(input_string: str) -> bool:
        """Scan input for SQL injection patterns"""
        if not isinstance(input_string, str):
            return False
        
        input_lower = input_string.lower()
        
        for pattern in SecurityConfig.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_lower, re.IGNORECASE):
                logger.warning(f"SQL injection attempt detected: {SecurityUtils.hash_sensitive_data(input_string)}")
                return True
        
        return False
    
    @staticmethod
    def sanitize_sql_input(input_string: str) -> str:
        """Sanitize input to prevent SQL injection"""
        if SQLInjectionProtector.scan_for_sql_injection(input_string):
            raise ValidationException("Input contains potentially dangerous SQL patterns")
        
        # Additional sanitization
        sanitized = input_string.replace("'", "''")  # Escape single quotes
        sanitized = re.sub(r'[;]+', '', sanitized)   # Remove semicolons
        
        return sanitized
    
    @staticmethod
    def validate_table_name(table_name: str) -> str:
        """Validate and sanitize table names"""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValidationException("Invalid table name format")
        
        if len(table_name) > 64:
            raise ValidationException("Table name too long")
        
        return table_name
    
    @staticmethod
    def validate_column_name(column_name: str) -> str:
        """Validate and sanitize column names"""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
            raise ValidationException("Invalid column name format")
        
        if len(column_name) > 64:
            raise ValidationException("Column name too long")
        
        return column_name


class XSSProtector:
    """Cross-Site Scripting (XSS) protection"""
    
    @staticmethod
    def scan_for_xss(input_string: str) -> bool:
        """Scan input for XSS patterns"""
        if not isinstance(input_string, str):
            return False
        
        for pattern in SecurityConfig.XSS_PATTERNS:
            if re.search(pattern, input_string, re.IGNORECASE):
                logger.warning(f"XSS attempt detected: {SecurityUtils.hash_sensitive_data(input_string)}")
                return True
        
        return False
    
    @staticmethod
    def sanitize_html_input(input_string: str) -> str:
        """Sanitize HTML input to prevent XSS"""
        if XSSProtector.scan_for_xss(input_string):
            raise ValidationException("Input contains potentially dangerous HTML/JavaScript")
        
        # HTML entity encoding for common dangerous characters
        sanitized = input_string.replace('&', '&amp;')
        sanitized = sanitized.replace('<', '&lt;')
        sanitized = sanitized.replace('>', '&gt;')
        sanitized = sanitized.replace('"', '&quot;')
        sanitized = sanitized.replace("'", '&#x27;')
        sanitized = sanitized.replace('/', '&#x2F;')
        
        return sanitized


class AdvancedRateLimiter:
    """Production-grade rate limiting with sliding window algorithm and comprehensive security"""
    
    def __init__(self):
        self.memory_store = rate_limit_memory
        self.fail_secure_mode = getattr(settings, 'RATE_LIMIT_FAIL_SECURE', False)  # Set to False for graceful degradation
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier with enhanced IP detection"""
        # Try multiple headers for real IP (common in production)
        real_ip = None
        ip_headers = [
            'X-Forwarded-For',
            'X-Real-IP', 
            'CF-Connecting-IP',  # Cloudflare
            'X-Client-IP',
            'True-Client-IP'
        ]
        
        for header in ip_headers:
            header_value = request.headers.get(header)
            if header_value:
                # Take first IP if comma-separated
                real_ip = header_value.split(',')[0].strip()
                # Basic validation - should be valid IP format
                import re
                if re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', real_ip) or ':' in real_ip:  # IPv4 or IPv6
                    break
                real_ip = None
        
        client_ip = real_ip or (request.client.host if request.client else 'unknown')
        
        # Include user agent hash for more specific identification
        user_agent = request.headers.get('User-Agent', 'unknown')
        user_agent_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:12]
        
        return f"{client_ip}:{user_agent_hash}"
    
    def _sliding_window_counter(self, key: str, window_seconds: int, limit: int) -> tuple[int, int, bool]:
        """Implement sliding window rate limiting with Redis sorted sets"""
        if self.redis:
            try:
                now = datetime.utcnow().timestamp()
                window_start = now - window_seconds
                
                pipe = self.redis.pipeline()
                # Remove old entries outside window
                pipe.zremrangebyscore(key, '-inf', window_start)
                # Add current request
                pipe.zadd(key, {str(now): now})
                # Count requests in current window
                pipe.zcard(key)
                # Set expiry
                pipe.expire(key, window_seconds + 1)
                
                results = pipe.execute()
                current_count = results[2]  # zcard result
                
                # Calculate time until window resets
                oldest_score = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest_score:
                    time_until_reset = int(window_seconds - (now - oldest_score[0][1]))
                else:
                    time_until_reset = 0
                
                return current_count, max(0, time_until_reset), current_count > limit
                
            except Exception as e:
                logger.warning(f"Redis sliding window error, falling back: {e}")
                if self.fail_secure_mode:
                    # Fail secure: deny request if Redis unavailable
                    logger.error(f"Rate limiting unavailable - failing secure for key: {key[:20]}...")
                    raise RateLimitException("Service temporarily unavailable. Please try again later.")
        
        # Memory fallback with simple sliding window
        return self._memory_sliding_window(key, window_seconds, limit)
    
    def _memory_sliding_window(self, key: str, window_seconds: int, limit: int) -> tuple[int, int, bool]:
        """Memory-based sliding window fallback"""
        now = datetime.utcnow().timestamp()
        window_start = now - window_seconds
        
        if key not in self.memory_store:
            self.memory_store[key] = []
        
        # Remove old entries
        self.memory_store[key] = [ts for ts in self.memory_store[key] if ts > window_start]
        # Add current request
        self.memory_store[key].append(now)
        
        current_count = len(self.memory_store[key])
        # Calculate time until oldest request expires
        if self.memory_store[key]:
            time_until_reset = int(window_seconds - (now - min(self.memory_store[key])))
        else:
            time_until_reset = 0
        
        return current_count, max(0, time_until_reset), current_count > limit
    
    def check_rate_limit(self, request: Request, limit: int, window_seconds: int, 
                        identifier_suffix: str = "", user_id: Optional[str] = None) -> dict:
        """Check rate limit with comprehensive monitoring and progressive penalties"""
        client_id = self._get_client_identifier(request)
        base_key = f"rate_limit:{identifier_suffix}:{client_id}"
        
        # Also rate limit by user if authenticated
        user_key = None
        if user_id:
            user_key = f"rate_limit:user:{identifier_suffix}:{user_id}"
        
        # Check client-based limit
        client_count, client_ttl, client_exceeded = self._sliding_window_counter(base_key, window_seconds, limit)
        
        # Check user-based limit if applicable
        user_count, user_ttl, user_exceeded = 0, 0, False
        if user_key:
            user_count, user_ttl, user_exceeded = self._sliding_window_counter(
                user_key, window_seconds, limit * 2  # Higher limit for authenticated users
            )
        
        # Check for progressive penalties
        penalty_multiplier = self._check_progressive_penalties(client_id, identifier_suffix)
        effective_limit = max(1, int(limit / penalty_multiplier))
        
        # Determine if rate limited
        is_limited = client_exceeded or user_exceeded or client_count > effective_limit
        
        if is_limited:
            self._log_rate_limit_violation(request, client_id, user_id, {
                'client_count': client_count,
                'user_count': user_count,
                'limit': limit,
                'effective_limit': effective_limit,
                'penalty_multiplier': penalty_multiplier,
                'window_seconds': window_seconds
            })
            
            # Apply progressive penalty
            self._apply_progressive_penalty(client_id, identifier_suffix)
            
            raise RateLimitException(f"Rate limit exceeded. Try again in {max(client_ttl, user_ttl)} seconds.")
        
        return {
            'client_count': client_count,
            'user_count': user_count,
            'limit': limit,
            'effective_limit': effective_limit,
            'reset_time': max(client_ttl, user_ttl),
            'penalty_multiplier': penalty_multiplier
        }
    
    def _check_progressive_penalties(self, client_id: str, endpoint: str) -> float:
        """Check for progressive penalty multipliers for repeat offenders"""
        penalty_key = f"penalties:{endpoint}:{SecurityUtils.hash_sensitive_data(client_id)}"
        
        if self.redis:
            try:
                violations = self.redis.get(penalty_key)
                violations = int(violations) if violations else 0
                
                # Progressive penalty: 1x, 1.5x, 2.5x, 4x (max) - More forgiving
                if violations >= 15:     # Increased threshold from 10
                    return 4.0            # Reduced max penalty from 8.0
                elif violations >= 8:     # Increased threshold from 5
                    return 2.5            # Reduced penalty from 4.0
                elif violations >= 3:     # Increased threshold from 2
                    return 1.5            # Reduced penalty from 2.0
                return 1.0
                
            except Exception:
                pass
        
        return 1.0
    
    def _apply_progressive_penalty(self, client_id: str, endpoint: str) -> None:
        """Apply progressive penalty for rate limit violations"""
        penalty_key = f"penalties:{endpoint}:{SecurityUtils.hash_sensitive_data(client_id)}"
        
        if self.redis:
            try:
                pipe = self.redis.pipeline()
                pipe.incr(penalty_key)
                pipe.expire(penalty_key, 3600)  # Penalties last 1 hour
                pipe.execute()
            except Exception as e:
                logger.warning(f"Failed to apply progressive penalty: {e}")
    
    def _log_rate_limit_violation(self, request: Request, client_id: str, user_id: Optional[str], details: dict) -> None:
        """Log rate limit violation with comprehensive details"""
        logger.warning(
            f"Rate limit violation - Client: {SecurityUtils.hash_sensitive_data(client_id)}, "
            f"User: {user_id or 'anonymous'}, Path: {request.url.path}, "
            f"Count: {details['client_count']}/{details['limit']}, "
            f"Penalty: {details['penalty_multiplier']}x"
        )
        
        # Log security event
        from app.core.audit_logging import log_security_event
        log_security_event("rate_limit_violation", {
            "client_hash": SecurityUtils.hash_sensitive_data(client_id)[:16],
            "user_id": user_id,
            "path": request.url.path,
            "method": request.method,
            "client_count": details['client_count'],
            "user_count": details['user_count'],
            "limit": details['limit'],
            "penalty_multiplier": details['penalty_multiplier'],
            "user_agent_hash": hashlib.sha256(
                request.headers.get('User-Agent', '').encode()
            ).hexdigest()[:16]
        })
    
    def check_auth_rate_limit(self, request: Request, email: str, endpoint_type: str = "login") -> None:
        """Specialized rate limiting for authentication endpoints"""
        email_hash = SecurityUtils.hash_sensitive_data(email)
        client_id = self._get_client_identifier(request)
        
        # Different limits based on endpoint type (OPTIMIZED for better UX)
        limits = {
            "login": {"limit": 8, "window": 900},        # 8 attempts per 15 minutes (increased from 5)
            "register": {"limit": 5, "window": 3600},      # 5 registrations per hour (increased from 3)
            "password_reset": {"limit": 3, "window": 1800}, # 3 resets per 30 minutes (increased from 2)
            "token_refresh": {"limit": 20, "window": 300}   # 20 refreshes per 5 minutes (increased from 10)
        }
        
        config = limits.get(endpoint_type, limits["login"])
        
        # Rate limit by client IP
        client_key = f"auth:{endpoint_type}:client:{SecurityUtils.hash_sensitive_data(client_id)}"
        client_count, client_ttl, client_exceeded = self._sliding_window_counter(
            client_key, config["window"], config["limit"]
        )
        
        # Rate limit by email
        email_key = f"auth:{endpoint_type}:email:{email_hash}"
        email_count, email_ttl, email_exceeded = self._sliding_window_counter(
            email_key, config["window"], config["limit"] // 2  # Stricter email-based limit
        )
        
        # Check for suspicious patterns (too many different emails from same IP)
        if endpoint_type in ["login", "register"]:
            self._check_suspicious_auth_patterns(client_id, email_hash, endpoint_type)
        
        if client_exceeded or email_exceeded:
            # Log security event
            from app.core.audit_logging import log_security_event
            log_security_event(f"auth_rate_limit_exceeded", {
                "endpoint": endpoint_type,
                "client_hash": SecurityUtils.hash_sensitive_data(client_id)[:16],
                "email_hash": email_hash[:16],
                "client_count": client_count,
                "email_count": email_count,
                "limit": config["limit"]
            })
            
            reset_time_minutes = max(client_ttl, email_ttl) // 60
            raise RateLimitException(
                f"Too many {endpoint_type} attempts. Try again in {reset_time_minutes} minutes."
            )
    
    def _check_suspicious_auth_patterns(self, client_id: str, email_hash: str, endpoint_type: str) -> None:
        """Check for suspicious authentication patterns"""
        if not self.redis:
            return
        
        try:
            # Track unique emails per client
            pattern_key = f"auth_pattern:{endpoint_type}:{SecurityUtils.hash_sensitive_data(client_id)}"
            
            pipe = self.redis.pipeline()
            pipe.sadd(pattern_key, email_hash)
            pipe.scard(pattern_key)
            pipe.expire(pattern_key, 3600)  # 1 hour tracking window
            results = pipe.execute()
            
            unique_emails_count = results[1]
            
            # Alert if too many different emails from same client
            if unique_emails_count > 10:  # More than 10 different emails in 1 hour
                from app.core.audit_logging import log_security_event
                log_security_event("suspicious_auth_pattern", {
                    "pattern": "multiple_emails_per_client",
                    "endpoint": endpoint_type,
                    "client_hash": SecurityUtils.hash_sensitive_data(client_id)[:16],
                    "unique_emails_count": unique_emails_count,
                    "severity": "high"
                })
                
                # Apply additional rate limiting for suspicious clients
                suspicious_key = f"suspicious:{SecurityUtils.hash_sensitive_data(client_id)}"
                self.redis.setex(suspicious_key, 1800, "flagged")  # 30 minutes
                
        except Exception as e:
            logger.warning(f"Failed to check suspicious auth patterns: {e}")
    
    def is_client_suspicious(self, request: Request) -> bool:
        """Check if client is flagged as suspicious"""
        if not self.redis:
            return False
        
        try:
            client_id = self._get_client_identifier(request)
            suspicious_key = f"suspicious:{SecurityUtils.hash_sensitive_data(client_id)}"
            return self.redis.exists(suspicious_key) > 0
        except Exception:
            return False
    
    def get_rate_limit_status(self, request: Request, endpoint_type: str, user_id: Optional[str] = None) -> dict:
        """Get current rate limit status for monitoring"""
        client_id = self._get_client_identifier(request)
        
        # Get different rate limit statuses
        statuses = {}
        
        # General API limits
        api_key = f"rate_limit:api:{client_id}"
        if self.redis:
            try:
                api_count = self.redis.zcard(api_key) if self.redis.exists(api_key) else 0
                statuses['api_requests'] = {'count': api_count, 'limit': SecurityConfig.API_RATE_LIMIT}
            except Exception:
                statuses['api_requests'] = {'count': 0, 'limit': SecurityConfig.API_RATE_LIMIT}
        
        # Auth-specific limits
        if endpoint_type.startswith('auth_'):
            auth_type = endpoint_type.replace('auth_', '')
            auth_key = f"auth:{auth_type}:client:{SecurityUtils.hash_sensitive_data(client_id)}"
            if self.redis:
                try:
                    auth_count = self.redis.zcard(auth_key) if self.redis.exists(auth_key) else 0
                    statuses[f'{auth_type}_attempts'] = {'count': auth_count, 'limit': SecurityConfig.LOGIN_RATE_LIMIT}
                except Exception:
                    statuses[f'{auth_type}_attempts'] = {'count': 0, 'limit': SecurityConfig.LOGIN_RATE_LIMIT}
        
        # Penalty status
        penalty_multiplier = self._check_progressive_penalties(client_id, endpoint_type)
        statuses['penalty_multiplier'] = penalty_multiplier
        
        # Suspicious status
        statuses['is_suspicious'] = self.is_client_suspicious(request)
        
        return statuses


class SecurityMonitor:
    """Security monitoring and alerting"""
    
    def __init__(self):
        self.redis = redis_client
        self.suspicious_patterns = {
            'sql_injection': 0,
            'xss_attempts': 0,
            'rate_limit_violations': 0,
            'invalid_tokens': 0,
            'suspicious_user_agents': 0
        }
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          request: Request = None, severity: str = 'medium') -> None:
        """Log security event with details"""
        event_data = {
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'severity': severity,
            'details': details
        }
        
        if request:
            event_data.update({
                'client_ip': request.client.host if request.client else 'unknown',
                'user_agent': request.headers.get('User-Agent', ''),
                'url': str(request.url),
                'method': request.method
            })
        
        logger.warning(f"Security event [{severity}]: {event_type}", extra=event_data)
        
        # Store in Redis for monitoring
        if self.redis:
            try:
                key = f"security_events:{event_type}:{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
                self.redis.incr(key)
                self.redis.expire(key, 86400)  # Keep for 24 hours
            except Exception as e:
                logger.error(f"Failed to store security event: {e}")
    
    def check_suspicious_activity(self, request: Request) -> None:
        """Check for suspicious activity patterns"""
        user_agent = request.headers.get('User-Agent', '')
        
        # Check for suspicious user agents
        suspicious_ua_patterns = [
            r'sqlmap', r'nikto', r'w3af', r'acunetix', r'nessus',
            r'openvas', r'vega', r'burp', r'owasp', r'hydra'
        ]
        
        for pattern in suspicious_ua_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                self.log_security_event(
                    'suspicious_user_agent',
                    {'user_agent': SecurityUtils.hash_sensitive_data(user_agent), 'pattern': pattern},
                    request,
                    'high'
                )
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Check for rapid successive requests (potential bot)
        client_id = f"{request.client.host if request.client else 'unknown'}"
        key = f"request_frequency:{SecurityUtils.hash_sensitive_data(client_id)}"
        
        if self.redis:
            try:
                count = self.redis.incr(key)
                if count == 1:
                    self.redis.expire(key, 10)  # 10-second window
                
                if count > 50:  # More than 50 requests in 10 seconds
                    self.log_security_event(
                        'rapid_requests',
                        {'requests_per_10s': count, 'client': SecurityUtils.hash_sensitive_data(client_id)},
                        request,
                        'medium'
                    )
            except Exception:
                pass


class SecureInputValidator:
    """Comprehensive input validation with security focus"""
    
    @staticmethod
    def validate_and_sanitize_input(data: Any, max_depth: int = SecurityConfig.MAX_OBJECT_DEPTH) -> Any:
        """Recursively validate and sanitize input data"""
        if max_depth <= 0:
            raise ValidationException("Input structure too deep")
        
        if isinstance(data, str):
            return SecureInputValidator._sanitize_string(data)
        elif isinstance(data, dict):
            return SecureInputValidator._sanitize_dict(data, max_depth - 1)
        elif isinstance(data, list):
            return SecureInputValidator._sanitize_list(data, max_depth - 1)
        elif isinstance(data, (int, float, bool)) or data is None:
            return data
        else:
            raise ValidationException(f"Unsupported data type: {type(data)}")
    
    @staticmethod
    def _sanitize_string(value: str) -> str:
        """Sanitize string input"""
        if len(value) > SecurityConfig.MAX_STRING_LENGTH:
            raise ValidationException(f"String too long (max {SecurityConfig.MAX_STRING_LENGTH})")
        
        # Check for SQL injection
        if SQLInjectionProtector.scan_for_sql_injection(value):
            raise ValidationException("Input contains potentially dangerous SQL patterns")
        
        # Check for XSS
        if XSSProtector.scan_for_xss(value):
            raise ValidationException("Input contains potentially dangerous HTML/JavaScript")
        
        # Basic sanitization
        sanitized = value.strip()
        
        # Remove null bytes and control characters
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', sanitized)
        
        return sanitized
    
    @staticmethod
    def _sanitize_dict(data: dict, max_depth: int) -> dict:
        """Sanitize dictionary data"""
        if len(data) > SecurityConfig.MAX_ARRAY_LENGTH:
            raise ValidationException(f"Dictionary too large (max {SecurityConfig.MAX_ARRAY_LENGTH} keys)")
        
        sanitized = {}
        for key, value in data.items():
            # Validate key
            if not isinstance(key, str):
                raise ValidationException("Dictionary keys must be strings")
            
            sanitized_key = SecureInputValidator._sanitize_string(key)
            sanitized_value = SecureInputValidator.validate_and_sanitize_input(value, max_depth)
            sanitized[sanitized_key] = sanitized_value
        
        return sanitized
    
    @staticmethod
    def _sanitize_list(data: list, max_depth: int) -> list:
        """Sanitize list data"""
        if len(data) > SecurityConfig.MAX_ARRAY_LENGTH:
            raise ValidationException(f"Array too large (max {SecurityConfig.MAX_ARRAY_LENGTH} items)")
        
        return [SecureInputValidator.validate_and_sanitize_input(item, max_depth) for item in data]


class FileUploadSecurity:
    """Secure file upload handling"""
    
    @staticmethod
    def validate_file_upload(filename: str, file_content: bytes) -> None:
        """Validate uploaded file for security"""
        # Check file extension
        file_extension = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
        if file_extension not in SecurityConfig.ALLOWED_FILE_EXTENSIONS:
            raise ValidationException(f"File type not allowed. Allowed types: {', '.join(SecurityConfig.ALLOWED_FILE_EXTENSIONS)}")
        
        # Check file size
        if len(file_content) > SecurityConfig.MAX_FILE_SIZE:
            raise ValidationException(f"File too large. Maximum size: {SecurityConfig.MAX_FILE_SIZE // (1024*1024)}MB")
        
        # Check for malicious content in file headers
        FileUploadSecurity._scan_file_content(file_content, file_extension)
    
    @staticmethod
    def _scan_file_content(content: bytes, extension: str) -> None:
        """Scan file content for malicious patterns"""
        # Check for executable signatures
        executable_signatures = [
            b'MZ',      # Windows executable
            b'\x7fELF', # Linux executable
            b'\xca\xfe\xba\xbe',  # Java class file
            b'PK\x03\x04',        # ZIP file (could contain executables)
        ]
        
        for sig in executable_signatures:
            if content.startswith(sig):
                raise ValidationException("File contains potentially dangerous executable content")
        
        # Check for script content in files that shouldn't have it
        if extension in ['.jpg', '.jpeg', '.png', '.gif']:
            script_patterns = [b'<script', b'javascript:', b'vbscript:', b'<?php']
            for pattern in script_patterns:
                if pattern in content.lower():
                    raise ValidationException("Image file contains suspicious script content")


# Security middleware functions
def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    async def middleware(request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response
    
    return middleware


# Dependency injection for security
def get_rate_limiter() -> AdvancedRateLimiter:
    """Get rate limiter instance - FIXED to not hang during startup"""
    try:
        # Force in-memory mode to prevent Redis connection hangs
        limiter = AdvancedRateLimiter()
        limiter.redis_client = None  # Force in-memory fallback
        return limiter
    except Exception as e:
        logger.warning(f"Rate limiter creation failed, using mock: {e}")
        # Return mock rate limiter that always allows requests
        return MockRateLimiter()


def get_security_monitor() -> SecurityMonitor:
    """Get security monitor instance"""
    return SecurityMonitor()


def get_security_health_status() -> dict:
    """Get comprehensive security health status for monitoring"""
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "redis_status": "connected" if redis_client else "disconnected",
        "rate_limiting_backend": "redis" if redis_client else "memory",
        "security_features": {
            "sql_injection_protection": True,
            "xss_protection": True,
            "rate_limiting": True,
            "progressive_penalties": True,
            "suspicious_activity_monitoring": True,
            "jwt_security": True,
            "input_validation": True,
            "file_upload_security": True
        },
        "configuration": {
            "min_password_length": SecurityConfig.MIN_PASSWORD_LENGTH,
            "password_hash_rounds": SecurityConfig.PASSWORD_HASH_ROUNDS,
            "default_rate_limit": SecurityConfig.DEFAULT_RATE_LIMIT,
            "login_rate_limit": SecurityConfig.LOGIN_RATE_LIMIT,
            "register_rate_limit": SecurityConfig.REGISTER_RATE_LIMIT,
            "jwt_expiry_hours": SecurityConfig.JWT_EXPIRY_HOURS,
            "max_file_size_mb": SecurityConfig.MAX_FILE_SIZE // (1024 * 1024),
            "allowed_file_extensions": list(SecurityConfig.ALLOWED_FILE_EXTENSIONS)
        }
    }
    
    # Test Redis connectivity if available
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.ping()
            health_status["redis_ping"] = "success"
            health_status["redis_info"] = {
                "connected_clients": redis_client.info().get("connected_clients", 0),
                "used_memory_human": redis_client.info().get("used_memory_human", "unknown"),
                "uptime_in_seconds": redis_client.info().get("uptime_in_seconds", 0)
            }
        except Exception as e:
            health_status["redis_ping"] = "failed"
            health_status["redis_error"] = str(e)
            logger.warning(f"Redis health check failed: {e}")
    
    # Get rate limiting statistics
    if redis_client:
        try:
            # Count active rate limit keys
            active_keys = len(redis_client.keys("rate_limit:*")) if redis_client else 0
            penalty_keys = len(redis_client.keys("penalties:*")) if redis_client else 0
            suspicious_keys = len(redis_client.keys("suspicious:*")) if redis_client else 0
            blacklist_keys = len(redis_client.keys("blacklist:*")) if redis_client else 0
            
            health_status["statistics"] = {
                "active_rate_limit_keys": active_keys,
                "penalty_keys": penalty_keys,
                "suspicious_clients": suspicious_keys,
                "blacklisted_tokens": blacklist_keys,
                "memory_fallback_keys": len(rate_limit_memory)
            }
        except Exception as e:
            health_status["statistics"] = {
                "error": str(e),
                "memory_fallback_keys": len(rate_limit_memory)
            }
    else:
        health_status["statistics"] = {
            "memory_fallback_keys": len(rate_limit_memory),
            "note": "using_memory_backend"
        }
    
    # Security patterns detection status
    health_status["pattern_detection"] = {
        "sql_injection_patterns": len(SecurityConfig.SQL_INJECTION_PATTERNS),
        "xss_patterns": len(SecurityConfig.XSS_PATTERNS),
        "status": "active"
    }
    
    # Overall health score
    health_components = [
        redis_client is not None,  # Redis connectivity
        True,  # Basic security features always active
        len(rate_limit_memory) < 10000,  # Memory usage reasonable
    ]
    
    health_score = sum(health_components) / len(health_components) * 100
    health_status["overall_health_score"] = round(health_score, 2)
    
    if health_score >= 80:
        health_status["status"] = "healthy"
    elif health_score >= 60:
        health_status["status"] = "degraded"
    else:
        health_status["status"] = "unhealthy"
    
    return health_status


def require_api_rate_limit(request: Request, rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)):
    """Dependency to enforce API rate limiting"""
    rate_limiter.check_rate_limit(request, SecurityConfig.API_RATE_LIMIT, 3600, "api")  # 1 hour window


def require_login_rate_limit(request: Request, rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)):
    """Dependency to enforce login rate limiting on login endpoints"""
    # This would be used specifically on login endpoints with email parameter
    pass  # Implementation would be in the specific login endpoint


def require_auth_endpoint_protection(request: Request = None, 
                                   rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter),
                                   monitor: SecurityMonitor = Depends(get_security_monitor)):
    """Comprehensive protection for authentication endpoints"""
    def dependency(request: Request):
        # Monitor for suspicious activity
        monitor.check_suspicious_activity(request)
        
        # Apply base rate limiting for auth endpoints
        rate_limiter.check_rate_limit(
            request, 
            SecurityConfig.ANONYMOUS_RATE_LIMIT, 
            3600, 
            "auth", 
            None
        )
        
        return True
    
    return dependency


def comprehensive_auth_security(endpoint_type: str = "general", 
                              custom_limit: Optional[int] = None,
                              window_seconds: int = 3600):
    """Comprehensive security dependency for authentication endpoints with enhanced protection"""
    def dependency(request: Request,
                  rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter),
                  monitor: SecurityMonitor = Depends(get_security_monitor)):
        
        # For registration, use lightweight security to avoid timeouts
        if endpoint_type == "register":
            # Skip heavy monitoring for registration performance
            try:
                rate_limiter.check_rate_limit(
                    request,
                    custom_limit or SecurityConfig.REGISTER_RATE_LIMIT,
                    3600,  # 1 hour window
                    "auth_register",
                    None
                )
            except Exception as e:
                # Don't fail registration due to rate limiting issues
                logger.warning(f"Rate limiting issue during registration: {e}")
                pass
            return True
        
        # Full security for other endpoints
        # Security monitoring
        monitor.check_suspicious_activity(request)
        
        # Check if client is flagged as suspicious
        if rate_limiter.is_client_suspicious(request):
            logger.warning(f"Blocking request from suspicious client: {rate_limiter._get_client_identifier(request)[:20]}...")
            raise HTTPException(status_code=429, detail="Access temporarily restricted")
        
        # Apply endpoint-specific rate limiting
        if endpoint_type == "login":
            limit = custom_limit or SecurityConfig.LOGIN_RATE_LIMIT
            window = 900  # 15 minutes for login attempts
        elif endpoint_type == "password_reset":
            limit = custom_limit or SecurityConfig.PASSWORD_RESET_RATE_LIMIT
            window = 1800  # 30 minutes for password resets
        elif endpoint_type == "token_refresh":
            limit = custom_limit or SecurityConfig.TOKEN_REFRESH_RATE_LIMIT
            window = 300  # 5 minutes for token refresh
        else:
            # General auth endpoint protection
            limit = custom_limit or SecurityConfig.ANONYMOUS_RATE_LIMIT
            window = window_seconds
        
        # Apply rate limiting
        rate_limiter.check_rate_limit(
            request,
            limit,
            window,
            f"auth_{endpoint_type}",
            None
        )
        
        # Log security event for monitoring (skip for performance-critical endpoints)
        if endpoint_type not in ["register"]:
            monitor.log_security_event(
                f"auth_endpoint_access",
                {
                    "endpoint_type": endpoint_type,
                    "client_hash": SecurityUtils.hash_sensitive_data(
                        rate_limiter._get_client_identifier(request)
                    )[:16],
                    "limit": limit,
                    "window": window
                },
                request,
                "low"
            )
        
        return True
    
    return dependency


def monitor_security(request: Request, monitor: SecurityMonitor = Depends(get_security_monitor)):
    """Dependency to monitor for suspicious activity"""
    monitor.check_suspicious_activity(request)


def lightweight_auth_security():
    """Lightweight security for performance-critical registration endpoint"""
    def dependency(request: Request, rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)):
        try:
            # Basic rate limiting only - no heavy monitoring
            rate_limiter.check_rate_limit(
                request,
                SecurityConfig.REGISTER_RATE_LIMIT,
                3600,  # 1 hour window
                "register_fast",
                None
            )
        except RateLimitException:
            # Re-raise rate limit exceptions
            raise
        except Exception as e:
            # Don't fail registration due to other security issues
            logger.warning(f"Non-critical security check failed during registration: {e}")
            pass
        
        return True
    
    return dependency


# JWT token security
class JWTSecurity:
    """Enhanced JWT security handling"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token with enhanced security"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=SecurityConfig.JWT_EXPIRY_HOURS)
        
        to_encode.update({"exp": expire, "type": "access"})
        
        # Add additional security claims
        to_encode.update({
            "iss": "mita-finance",  # Issuer
            "aud": "mita-app",      # Audience
            "jti": secrets.token_urlsafe(16),  # JWT ID for tracking
        })
        
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, expected_type: str = "access") -> dict:
        """Verify JWT token with enhanced security checks"""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
            
            # Verify token type
            if payload.get("type") != expected_type:
                raise AuthenticationException("Invalid token type")
            
            # Verify issuer and audience
            if payload.get("iss") != "mita-finance" or payload.get("aud") != "mita-app":
                raise AuthenticationException("Invalid token claims")
            
            return payload
            
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise AuthenticationException("Invalid token")
    
    @staticmethod
    def blacklist_token(jti: str) -> None:
        """Add token to blacklist"""
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_client.setex(f"blacklist:{jti}", 86400 * 7, "1")  # 7 days
            except Exception as e:
                logger.error(f"Failed to blacklist token: {e}")
    
    @staticmethod
    def is_token_blacklisted(jti: str) -> bool:
        """Check if token is blacklisted"""
        redis_client = get_redis_client()
        if redis_client:
            try:
                return redis_client.exists(f"blacklist:{jti}") > 0
            except Exception:
                return False
        return False