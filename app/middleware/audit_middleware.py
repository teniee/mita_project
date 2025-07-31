"""
Audit Logging Middleware
Automatically logs all requests and responses for security auditing
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import json

from app.core.audit_logging import log_request_response, log_security_violation
from app.core.error_monitoring import log_error, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class AuditMiddleware:
    """Middleware for automatic audit logging"""
    
    def __init__(self):
        # Endpoints to exclude from detailed logging (to reduce noise)
        self.excluded_endpoints = {
            '/health',
            '/metrics',
            '/favicon.ico',
            '/docs',
            '/openapi.json',
            '/redoc'
        }
        
        # Endpoints that require enhanced logging
        self.enhanced_logging_endpoints = {
            '/auth/login',
            '/auth/register',
            '/auth/logout',
            '/admin',
            '/users/profile',
            '/transactions',
            '/goals'
        }
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with audit logging"""
        start_time = time.time()
        response = None
        error_message = None
        user_id = None
        session_id = None
        
        try:
            # Extract user information if available
            user_id = getattr(request.state, 'user_id', None)
            session_id = getattr(request.state, 'session_id', None)
            
            # Check for security violations before processing
            await self._check_security_violations(request)
            
            # Store request body for logging (if needed)
            await self._store_request_body(request)
            
            # Process the request
            response = await call_next(request)
            
            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000
            
            # Log the request/response if not excluded
            if not self._should_exclude_endpoint(request.url.path):
                await log_request_response(
                    request=request,
                    response=response,
                    response_time_ms=response_time_ms,
                    user_id=user_id,
                    session_id=session_id,
                    error_message=error_message
                )
            
            # Add audit headers to response
            response.headers['X-Audit-Logged'] = 'true'
            response.headers['X-Response-Time'] = str(round(response_time_ms, 2))
            
            return response
            
        except Exception as e:
            # Log the error
            error_message = str(e)
            response_time_ms = (time.time() - start_time) * 1000
            
            # Create error response if none exists
            if response is None:
                response = Response(
                    content=json.dumps({"error": "Internal server error"}),
                    status_code=500,
                    media_type="application/json"
                )
            
            # Log the failed request
            if not self._should_exclude_endpoint(request.url.path):
                await log_request_response(
                    request=request,
                    response=response,
                    response_time_ms=response_time_ms,
                    user_id=user_id,
                    session_id=session_id,
                    error_message=error_message
                )
            
            # Log the error to error monitoring system
            await log_error(
                e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.SYSTEM,
                user_id=user_id,
                request=request,
                additional_context={
                    'response_time_ms': response_time_ms,
                    'endpoint': request.url.path
                }
            )
            
            # Re-raise the exception
            raise e
    
    async def _store_request_body(self, request: Request):
        """Store request body for logging purposes"""
        try:
            # Only store body for enhanced logging endpoints
            if request.url.path in self.enhanced_logging_endpoints:
                if request.method in ['POST', 'PUT', 'PATCH']:
                    body = await request.body()
                    # Store in request state for later access
                    request.state.original_body = body
                    
                    # Re-create the request body stream
                    async def receive():
                        return {"type": "http.request", "body": body}
                    
                    request._receive = receive
                    
        except Exception as e:
            logger.warning(f"Error storing request body: {str(e)}")
    
    async def _check_security_violations(self, request: Request):
        """Check for potential security violations"""
        try:
            # Check for suspicious patterns in URL
            url_path = request.url.path.lower()
            
            # SQL injection patterns in URL
            sql_patterns = ['union', 'select', 'insert', 'delete', 'drop', '--', ';']
            for pattern in sql_patterns:
                if pattern in url_path:
                    await log_security_violation(
                        request=request,
                        violation_type="sql_injection_attempt",
                        severity="high",
                        pattern=pattern,
                        url=str(request.url)
                    )
            
            # XSS patterns in URL
            xss_patterns = ['<script', 'javascript:', 'vbscript:', 'onload=']
            for pattern in xss_patterns:
                if pattern in url_path:
                    await log_security_violation(
                        request=request,
                        violation_type="xss_attempt",
                        severity="high",
                        pattern=pattern,
                        url=str(request.url)
                    )
            
            # Path traversal attempts
            traversal_patterns = ['../', '..\\', '%2e%2e%2f', '%2e%2e%5c']
            for pattern in traversal_patterns:
                if pattern in url_path:
                    await log_security_violation(
                        request=request,
                        violation_type="path_traversal_attempt",
                        severity="high",
                        pattern=pattern,
                        url=str(request.url)
                    )
            
            # Suspicious user agents
            user_agent = request.headers.get('User-Agent', '').lower()
            suspicious_agents = ['sqlmap', 'nikto', 'w3af', 'acunetix', 'nessus', 'burp']
            for agent in suspicious_agents:
                if agent in user_agent:
                    await log_security_violation(
                        request=request,
                        violation_type="suspicious_user_agent",
                        severity="critical",
                        user_agent=user_agent,
                        tool=agent
                    )
            
            # Check for oversized requests
            content_length = request.headers.get('Content-Length')
            if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
                await log_security_violation(
                    request=request,
                    violation_type="oversized_request",
                    severity="medium",
                    content_length=content_length
                )
            
        except Exception as e:
            logger.warning(f"Error checking security violations: {str(e)}")
    
    def _should_exclude_endpoint(self, endpoint: str) -> bool:
        """Check if endpoint should be excluded from logging"""
        return endpoint in self.excluded_endpoints
    
    def _should_enhance_logging(self, endpoint: str) -> bool:
        """Check if endpoint requires enhanced logging"""
        return endpoint in self.enhanced_logging_endpoints


class RequestResponseLoggingMiddleware:
    """Simplified middleware for request/response logging"""
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Log requests and responses with timing"""
        start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                'method': request.method,
                'path': request.url.path,
                'query_params': str(request.query_params),
                'client_ip': request.client.host if request.client else 'unknown',
                'user_agent': request.headers.get('User-Agent', ''),
                'timestamp': start_time
            }
        )
        
        try:
            response = await call_next(request)
            response_time = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"Response: {response.status_code} for {request.method} {request.url.path} ({response_time:.2f}ms)",
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'response_time_ms': response_time,
                    'timestamp': time.time()
                }
            )
            
            return response
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            # Log error response
            logger.error(
                f"Error: {str(e)} for {request.method} {request.url.path} ({response_time:.2f}ms)",
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'error': str(e),
                    'response_time_ms': response_time,
                    'timestamp': time.time()
                }
            )
            
            raise e


# Create middleware instances
audit_middleware = AuditMiddleware()
request_response_middleware = RequestResponseLoggingMiddleware()