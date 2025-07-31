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
import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.error_handler import ValidationException, AuthenticationException, RateLimitException

logger = logging.getLogger(__name__)

# Initialize Redis for rate limiting and security monitoring
try:
    redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379')
    redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established successfully")
except redis.ConnectionError as e:
    redis_client = None
    logger.warning(f"Redis connection failed: {str(e)} - rate limiting will use in-memory storage")
except redis.RedisError as e:
    redis_client = None
    logger.error(f"Redis error: {str(e)} - rate limiting will use in-memory storage")
except Exception as e:
    redis_client = None
    logger.error(f"Unexpected error connecting to Redis: {str(e)} - rate limiting will use in-memory storage")

# In-memory fallback for rate limiting
rate_limit_memory: Dict[str, Dict] = {}

security = HTTPBearer()


class SecurityConfig:
    """Security configuration constants"""
    
    # Password security
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    PASSWORD_HASH_ROUNDS = 12
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = 100  # requests per hour
    LOGIN_RATE_LIMIT = 5      # login attempts per 15 minutes
    API_RATE_LIMIT = 1000     # API calls per hour
    
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
        """Hash password using bcrypt with high security settings"""
        if len(password) < SecurityConfig.MIN_PASSWORD_LENGTH:
            raise ValidationException(f"Password must be at least {SecurityConfig.MIN_PASSWORD_LENGTH} characters")
        
        if len(password) > SecurityConfig.MAX_PASSWORD_LENGTH:
            raise ValidationException(f"Password cannot exceed {SecurityConfig.MAX_PASSWORD_LENGTH} characters")
        
        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=SecurityConfig.PASSWORD_HASH_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.warning(f"Password verification failed: {e}")
            return False
    
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
    """Advanced rate limiting with multiple strategies"""
    
    def __init__(self):
        self.redis = redis_client
        self.memory_store = rate_limit_memory
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get unique client identifier"""
        # Try to get real IP from headers (for load balancers/proxies)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else 'unknown'
        
        # Include user agent for more specific identification
        user_agent = request.headers.get('User-Agent', '')
        user_agent_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        return f"{client_ip}:{user_agent_hash}"
    
    def _increment_counter(self, key: str, window_seconds: int, limit: int) -> tuple[int, int]:
        """Increment counter and return (current_count, ttl_seconds)"""
        if self.redis:
            try:
                pipe = self.redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds)
                results = pipe.execute()
                
                current_count = results[0]
                ttl = self.redis.ttl(key)
                return current_count, ttl
            except Exception as e:
                logger.warning(f"Redis error, falling back to memory: {e}")
        
        # Memory fallback
        now = datetime.utcnow()
        if key not in self.memory_store:
            self.memory_store[key] = {'count': 0, 'window_start': now}
        
        entry = self.memory_store[key]
        
        # Reset if window expired
        if (now - entry['window_start']).total_seconds() > window_seconds:
            entry['count'] = 0
            entry['window_start'] = now
        
        entry['count'] += 1
        ttl = window_seconds - int((now - entry['window_start']).total_seconds())
        
        return entry['count'], max(0, ttl)
    
    def check_rate_limit(self, request: Request, limit: int, window_seconds: int, 
                        identifier_suffix: str = "") -> None:
        """Check if request exceeds rate limit"""
        client_id = self._get_client_identifier(request)
        key = f"rate_limit:{client_id}:{identifier_suffix}:{request.url.path}"
        
        current_count, ttl = self._increment_counter(key, window_seconds, limit)
        
        if current_count > limit:
            logger.warning(f"Rate limit exceeded for {SecurityUtils.hash_sensitive_data(client_id)} on {request.url.path}")
            raise RateLimitException(f"Rate limit exceeded. Try again in {ttl} seconds.")
        
        # Add headers to response (this would be done in middleware)
        logger.info(f"Rate limit check: {current_count}/{limit} for {SecurityUtils.hash_sensitive_data(client_id)}")
    
    def check_login_rate_limit(self, request: Request, email: str) -> None:
        """Check login attempt rate limit"""
        email_hash = SecurityUtils.hash_sensitive_data(email)
        client_id = self._get_client_identifier(request)
        
        # Rate limit by IP
        ip_key = f"login_attempts:ip:{client_id}"
        ip_count, _ = self._increment_counter(ip_key, 900, SecurityConfig.LOGIN_RATE_LIMIT)  # 15 minutes
        
        # Rate limit by email
        email_key = f"login_attempts:email:{email_hash}"
        email_count, ttl = self._increment_counter(email_key, 900, SecurityConfig.LOGIN_RATE_LIMIT)
        
        if ip_count > SecurityConfig.LOGIN_RATE_LIMIT or email_count > SecurityConfig.LOGIN_RATE_LIMIT:
            logger.warning(f"Login rate limit exceeded for {email_hash} from {SecurityUtils.hash_sensitive_data(client_id)}")
            raise RateLimitException(f"Too many login attempts. Try again in {ttl // 60} minutes.")


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
    """Get rate limiter instance"""
    return AdvancedRateLimiter()


def get_security_monitor() -> SecurityMonitor:
    """Get security monitor instance"""
    return SecurityMonitor()


def require_api_rate_limit(request: Request, rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)):
    """Dependency to enforce API rate limiting"""
    rate_limiter.check_rate_limit(request, SecurityConfig.API_RATE_LIMIT, 3600, "api")  # 1 hour window


def require_login_rate_limit(request: Request, rate_limiter: AdvancedRateLimiter = Depends(get_rate_limiter)):
    """Dependency to enforce login rate limiting on login endpoints"""
    # This would be used specifically on login endpoints with email parameter
    pass  # Implementation would be in the specific login endpoint


def monitor_security(request: Request, monitor: SecurityMonitor = Depends(get_security_monitor)):
    """Dependency to monitor for suspicious activity"""
    monitor.check_suspicious_activity(request)


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
        if redis_client:
            try:
                redis_client.setex(f"blacklist:{jti}", 86400 * 7, "1")  # 7 days
            except Exception as e:
                logger.error(f"Failed to blacklist token: {e}")
    
    @staticmethod
    def is_token_blacklisted(jti: str) -> bool:
        """Check if token is blacklisted"""
        if redis_client:
            try:
                return redis_client.exists(f"blacklist:{jti}") > 0
            except Exception:
                return False
        return False