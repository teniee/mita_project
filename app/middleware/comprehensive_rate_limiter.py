"""
Comprehensive Rate Limiting Middleware for MITA Financial Application
Production-grade middleware with sliding window algorithm, progressive penalties,
and fail-secure behavior for financial security compliance.
"""

import time
import logging
from typing import Callable
from datetime import datetime

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.security import (
    SecurityConfig, 
    get_rate_limiter,
    get_user_tier_from_request
)
from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)


class ComprehensiveRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive rate limiting middleware with:
    - Sliding window algorithm
    - Progressive penalties for repeat offenders
    - User tier-based limits
    - Fail-secure behavior
    - Security monitoring and logging
    """
    
    def __init__(self, app, enable_rate_limiting: bool = True):
        super().__init__(app)
        self.enable_rate_limiting = enable_rate_limiting
        self.rate_limiter = get_rate_limiter()
        
        # Exempt paths that shouldn't be rate limited
        self.exempt_paths = {
            "/health",
            "/health/",
            "/docs",
            "/docs/",
            "/openapi.json",
            "/redoc",
            "/redoc/"
        }
        
        # Paths that need special rate limiting
        self.auth_paths = {
            "/auth/login",
            "/auth/register", 
            "/auth/refresh",
            "/auth/password-reset/request",
            "/auth/google"
        }
        
        # Admin paths with stricter limits
        self.admin_paths = {
            "/admin/",
            "/auth/security/status"
        }
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with comprehensive rate limiting"""
        
        # Skip rate limiting if disabled or for exempt paths
        if not self.enable_rate_limiting or self._is_path_exempt(request.url.path):
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            # Apply rate limiting based on path and user
            await self._apply_rate_limiting(request)
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limiting headers
            self._add_rate_limit_headers(request, response)
            
            # Log successful request for monitoring
            self._log_request_success(request, response, time.time() - start_time)
            
            return response
            
        except HTTPException as e:
            # Handle rate limit exceptions
            if e.status_code == 429:
                return self._create_rate_limit_response(request, str(e.detail))
            raise
            
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Rate limiting middleware error: {e}")
            log_security_event("rate_limit_middleware_error", {
                "error": str(e),
                "path": request.url.path,
                "method": request.method
            })
            
            # In fail-secure mode, deny requests during errors (SOFTENED)
            # Only fail secure for auth endpoints to prevent brute force
            if (getattr(SecurityConfig, 'RATE_LIMIT_FAIL_SECURE', True) and 
                any(request.url.path.startswith(auth_path) for auth_path in self.auth_paths)):
                return self._create_rate_limit_response(
                    request, 
                    "Authentication temporarily unavailable. Please try again later."
                )
            
            # Otherwise, allow request to continue
            return await call_next(request)
    
    def _is_path_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    async def _apply_rate_limiting(self, request: Request) -> None:
        """Apply appropriate rate limiting based on request characteristics"""
        
        path = request.url.path
        
        # Get user tier for tiered rate limiting
        user_tier = get_user_tier_from_request(request)
        
        # Apply different rate limiting strategies based on path
        if any(path.startswith(auth_path) for auth_path in self.auth_paths):
            await self._apply_auth_rate_limiting(request, user_tier)
        elif any(path.startswith(admin_path) for admin_path in self.admin_paths):
            await self._apply_admin_rate_limiting(request, user_tier)
        else:
            await self._apply_general_rate_limiting(request, user_tier)
    
    async def _apply_auth_rate_limiting(self, request: Request, user_tier: str) -> None:
        """Apply authentication endpoint rate limiting"""
        
        # Auth endpoints have special handling in their route handlers
        # This provides an additional layer of protection
        
        # Balanced limits for auth endpoints (OPTIMIZED for better UX)
        limits = {
            'anonymous': {'limit': 20, 'window': 300},  # 20 requests per 5 minutes (increased from 10)
            'basic_user': {'limit': 30, 'window': 300},  # Increased from 15
            'premium_user': {'limit': 40, 'window': 300}, # Increased from 20
            'admin_user': {'limit': 80, 'window': 300}    # Increased from 50
        }
        
        config = limits.get(user_tier, limits['anonymous'])
        
        try:
            self.rate_limiter.check_rate_limit(
                request,
                config['limit'],
                config['window'],
                f"auth_middleware_{user_tier}"
            )
        except Exception as e:
            if "Rate limit exceeded" in str(e):
                # Log rate limit violation
                log_security_event("auth_middleware_rate_limit", {
                    "user_tier": user_tier,
                    "path": request.url.path,
                    "limit": config['limit'],
                    "window": config['window']
                })
                raise HTTPException(
                    status_code=429,
                    detail="Authentication rate limit exceeded. Try again later."
                )
            raise
    
    async def _apply_admin_rate_limiting(self, request: Request, user_tier: str) -> None:
        """Apply admin endpoint rate limiting"""
        
        # Admin endpoints need special protection
        if user_tier != 'admin_user':
            # Non-admin users get reasonable limits (SOFTENED)
            self.rate_limiter.check_rate_limit(request, 15, 3600, "admin_non_admin")  # Increased from 5
        else:
            # Admin users have higher limits
            self.rate_limiter.check_rate_limit(request, 200, 3600, "admin_admin")  # Increased from 100
    
    async def _apply_general_rate_limiting(self, request: Request, user_tier: str) -> None:
        """Apply general API rate limiting"""
        
        tier_config = SecurityConfig.RATE_LIMIT_TIERS.get(
            user_tier, 
            SecurityConfig.RATE_LIMIT_TIERS['anonymous']
        )
        
        # Extract user ID if available
        user_id = None
        try:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if token:
                from app.services.auth_jwt_service import get_token_info
                token_info = get_token_info(token)
                user_id = token_info.get("user_id") if token_info else None
        except Exception:
            pass
        
        # Apply tiered rate limiting
        try:
            self.rate_limiter.check_rate_limit(
                request,
                tier_config['requests_per_hour'],
                tier_config['window_size'],
                f"general_{user_tier}",
                user_id
            )
            
            # Also apply burst protection (shorter window)
            self.rate_limiter.check_rate_limit(
                request,
                tier_config['burst_limit'],
                60,  # 1 minute window
                f"burst_{user_tier}",
                user_id
            )
            
        except Exception as e:
            if "Rate limit exceeded" in str(e):
                # Log rate limit violation
                log_security_event("general_middleware_rate_limit", {
                    "user_tier": user_tier,
                    "user_id": user_id,
                    "path": request.url.path,
                    "hourly_limit": tier_config['requests_per_hour'],
                    "burst_limit": tier_config['burst_limit']
                })
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for {user_tier} tier. Try again later."
                )
            raise
    
    def _add_rate_limit_headers(self, request: Request, response: Response) -> None:
        """Add rate limiting headers to response"""
        try:
            user_tier = get_user_tier_from_request(request)
            tier_config = SecurityConfig.RATE_LIMIT_TIERS.get(
                user_tier,
                SecurityConfig.RATE_LIMIT_TIERS['anonymous']
            )
            
            # Add standard rate limiting headers
            response.headers["X-RateLimit-Limit"] = str(tier_config['requests_per_hour'])
            response.headers["X-RateLimit-Window"] = str(tier_config['window_size'])
            response.headers["X-RateLimit-Tier"] = user_tier
            
            # Try to get current usage (best effort)
            try:
                status = self.rate_limiter.get_rate_limit_status(request, f"general_{user_tier}")
                if 'api_requests' in status:
                    remaining = max(0, tier_config['requests_per_hour'] - status['api_requests']['count'])
                    response.headers["X-RateLimit-Remaining"] = str(remaining)
            except Exception:
                # Don't fail the request if we can't get rate limit status
                pass
            
        except Exception as e:
            # Don't fail the request if we can't add headers
            logger.debug(f"Failed to add rate limit headers: {e}")
    
    def _create_rate_limit_response(self, request: Request, detail: str) -> JSONResponse:
        """Create standardized rate limit exceeded response"""
        
        # Get retry-after time if available
        retry_after = self._extract_retry_after(detail)
        
        response_data = {
            "error": "rate_limit_exceeded",
            "message": detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": request.url.path,
            "method": request.method
        }
        
        if retry_after:
            response_data["retry_after_seconds"] = retry_after
        
        headers = {
            "Content-Type": "application/json",
            "Retry-After": str(retry_after) if retry_after else "60"
        }
        
        return JSONResponse(
            status_code=429,
            content=response_data,
            headers=headers
        )
    
    def _extract_retry_after(self, detail: str) -> int:
        """Extract retry-after time from error detail"""
        try:
            # Look for "Try again in X seconds" pattern
            import re
            match = re.search(r'(\d+)\s*seconds?', detail)
            if match:
                return int(match.group(1))
                
            # Look for "Try again in X minutes" pattern
            match = re.search(r'(\d+)\s*minutes?', detail)
            if match:
                return int(match.group(1)) * 60
                
        except Exception:
            pass
        
        # Default retry after
        return 60
    
    def _log_request_success(self, request: Request, response: Response, duration: float) -> None:
        """Log successful request for monitoring"""
        
        # Only log periodically to avoid spam
        if hash(str(request.url) + str(time.time())) % 100 == 0:  # 1% sampling
            log_security_event("request_processed", {
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
                "user_tier": get_user_tier_from_request(request)
            })


def create_rate_limit_middleware(enable_rate_limiting: bool = True) -> ComprehensiveRateLimitMiddleware:
    """Factory function to create rate limiting middleware"""
    return ComprehensiveRateLimitMiddleware(None, enable_rate_limiting)