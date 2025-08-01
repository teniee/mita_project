"""
Comprehensive Request/Response Audit Logging System
Provides detailed logging for security auditing, compliance, and monitoring
"""

import json
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import hashlib
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.async_session import get_async_db_context
from app.core.error_monitoring import log_error, ErrorSeverity, ErrorCategory

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""
    REQUEST = "request"
    RESPONSE = "response"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_EVENT = "system_event"


class SensitivityLevel(Enum):
    """Data sensitivity levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class AuditEvent:
    """Structured audit event data"""
    id: str
    timestamp: datetime
    event_type: AuditEventType
    user_id: Optional[str]
    session_id: Optional[str]
    client_ip: str
    user_agent: str
    endpoint: str
    method: str
    status_code: Optional[int]
    response_time_ms: Optional[float]
    request_size: int
    response_size: Optional[int]
    sensitivity_level: SensitivityLevel
    success: bool
    error_message: Optional[str]
    additional_context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['event_type'] = self.event_type.value
        data['sensitivity_level'] = self.sensitivity_level.value
        return data


class DataSanitizer:
    """Sanitizes sensitive data in logs"""
    
    # Patterns for sensitive data
    SENSITIVE_PATTERNS = {
        'password': re.compile(r'("password"\s*:\s*")[^"]*(")', re.IGNORECASE),
        'token': re.compile(r'("(?:access_token|refresh_token|api_key|authorization)"\s*:\s*")[^"]*(")', re.IGNORECASE),
        'email': re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'),
        'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        'phone': re.compile(r'\b\d{3}-\d{3}-\d{4}\b'),
    }
    
    # Headers to redact
    SENSITIVE_HEADERS = {
        'authorization', 'cookie', 'x-api-key', 'x-auth-token',
        'x-csrf-token', 'x-session-token'
    }
    
    @classmethod
    def sanitize_data(cls, data: Any, sensitivity_level: SensitivityLevel) -> Any:
        """Sanitize data based on sensitivity level"""
        if sensitivity_level == SensitivityLevel.PUBLIC:
            return data
        
        if isinstance(data, str):
            return cls._sanitize_string(data, sensitivity_level)
        elif isinstance(data, dict):
            return cls._sanitize_dict(data, sensitivity_level)
        elif isinstance(data, list):
            return [cls.sanitize_data(item, sensitivity_level) for item in data]
        else:
            return data
    
    @classmethod
    def _sanitize_string(cls, value: str, sensitivity_level: SensitivityLevel) -> str:
        """Sanitize string data"""
        if sensitivity_level in [SensitivityLevel.CONFIDENTIAL, SensitivityLevel.RESTRICTED]:
            # Apply all patterns
            for pattern_name, pattern in cls.SENSITIVE_PATTERNS.items():
                if pattern_name in ['password', 'token']:
                    value = pattern.sub(r'\1***REDACTED***\2', value)
                else:
                    value = pattern.sub('***REDACTED***', value)
        
        return value
    
    @classmethod
    def _sanitize_dict(cls, data: dict, sensitivity_level: SensitivityLevel) -> dict:
        """Sanitize dictionary data"""
        sanitized = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Always redact these keys
            if key_lower in ['password', 'secret', 'token', 'key', 'auth']:
                sanitized[key] = '***REDACTED***'
            elif sensitivity_level in [SensitivityLevel.CONFIDENTIAL, SensitivityLevel.RESTRICTED]:
                if key_lower in ['email', 'phone', 'ssn', 'credit_card']:
                    sanitized[key] = '***REDACTED***'
                else:
                    sanitized[key] = cls.sanitize_data(value, sensitivity_level)
            else:
                sanitized[key] = cls.sanitize_data(value, sensitivity_level)
        
        return sanitized
    
    @classmethod
    def sanitize_headers(cls, headers: dict) -> dict:
        """Sanitize HTTP headers"""
        sanitized = {}
        
        for key, value in headers.items():
            if key.lower() in cls.SENSITIVE_HEADERS:
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        
        return sanitized


class AuditLogger:
    """Main audit logging system"""
    
    def __init__(self):
        self.buffer: List[AuditEvent] = []
        self.buffer_size = 100
        self.flush_interval = 30  # seconds
        self.last_flush = time.time()
        
        # Endpoint classification
        self.sensitive_endpoints = {
            '/auth/login': SensitivityLevel.CONFIDENTIAL,
            '/auth/register': SensitivityLevel.CONFIDENTIAL,
            '/users/profile': SensitivityLevel.INTERNAL,
            '/transactions': SensitivityLevel.CONFIDENTIAL,
            '/goals': SensitivityLevel.INTERNAL,
            '/receipts/upload': SensitivityLevel.INTERNAL,
        }
        
        # Start background flush task
        asyncio.create_task(self._background_flush())
    
    async def log_request_response(
        self,
        request: Request,
        response: Response,
        response_time_ms: float,
        user_id: str = None,
        session_id: str = None,
        error_message: str = None
    ):
        """Log request/response audit event"""
        try:
            # Determine sensitivity level
            sensitivity_level = self._get_endpoint_sensitivity(request.url.path)
            
            # Extract request data
            request_body = await self._extract_request_body(request)
            response_body = await self._extract_response_body(response)
            
            # Create audit event
            audit_event = AuditEvent(
                id=f"{datetime.now().isoformat()}_{id(request)}",
                timestamp=datetime.now(),
                event_type=AuditEventType.REQUEST,
                user_id=user_id,
                session_id=session_id,
                client_ip=self._get_client_ip(request),
                user_agent=request.headers.get('User-Agent', ''),
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code if response else None,
                response_time_ms=response_time_ms,
                request_size=len(str(request_body)) if request_body else 0,
                response_size=len(str(response_body)) if response_body else 0,
                sensitivity_level=sensitivity_level,
                success=response.status_code < 400 if response else False,
                error_message=error_message,
                additional_context={
                    'query_params': dict(request.query_params),
                    'headers': DataSanitizer.sanitize_headers(dict(request.headers)),
                    'request_body': DataSanitizer.sanitize_data(request_body, sensitivity_level),
                    'response_body': DataSanitizer.sanitize_data(response_body, sensitivity_level) if sensitivity_level != SensitivityLevel.RESTRICTED else '***REDACTED***'
                }
            )
            
            await self._store_audit_event(audit_event)
            
        except Exception as e:
            # Don't let audit logging break the application
            logger.error(f"Error in audit logging: {str(e)}")
            await log_error(
                e,
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.SYSTEM,
                additional_context={'operation': 'audit_logging'}
            )
    
    async def log_authentication_event(
        self,
        request: Request,
        user_id: str = None,
        email: str = None,
        success: bool = False,
        failure_reason: str = None
    ):
        """Log authentication audit event"""
        try:
            audit_event = AuditEvent(
                id=f"auth_{datetime.now().isoformat()}_{id(request)}",
                timestamp=datetime.now(),
                event_type=AuditEventType.AUTHENTICATION,
                user_id=user_id,
                session_id=None,
                client_ip=self._get_client_ip(request),
                user_agent=request.headers.get('User-Agent', ''),
                endpoint=request.url.path,
                method=request.method,
                status_code=200 if success else 401,
                response_time_ms=None,
                request_size=0,
                response_size=None,
                sensitivity_level=SensitivityLevel.CONFIDENTIAL,
                success=success,
                error_message=failure_reason,
                additional_context={
                    'email': DataSanitizer.sanitize_data(email, SensitivityLevel.CONFIDENTIAL) if email else None,
                    'failure_reason': failure_reason
                }
            )
            
            await self._store_audit_event(audit_event)
            
        except Exception as e:
            logger.error(f"Error logging authentication event: {str(e)}")
    
    async def log_data_access_event(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str = None,
        action: str = "read",
        success: bool = True,
        additional_context: Dict[str, Any] = None
    ):
        """Log data access audit event"""
        try:
            audit_event = AuditEvent(
                id=f"data_access_{datetime.now().isoformat()}_{user_id}",
                timestamp=datetime.now(),
                event_type=AuditEventType.DATA_ACCESS,
                user_id=user_id,
                session_id=None,
                client_ip="internal",
                user_agent="system",
                endpoint=f"/{resource_type}",
                method=action.upper(),
                status_code=200 if success else 403,
                response_time_ms=None,
                request_size=0,
                response_size=None,
                sensitivity_level=SensitivityLevel.INTERNAL,
                success=success,
                error_message=None,
                additional_context={
                    'resource_type': resource_type,
                    'resource_id': resource_id,
                    'action': action,
                    **(additional_context or {})
                }
            )
            
            await self._store_audit_event(audit_event)
            
        except Exception as e:
            logger.error(f"Error logging data access event: {str(e)}")
    
    async def log_security_violation(
        self,
        request: Request,
        violation_type: str,
        severity: str = "medium",
        details: Dict[str, Any] = None
    ):
        """Log security violation audit event"""
        try:
            audit_event = AuditEvent(
                id=f"security_{datetime.now().isoformat()}_{id(request)}",
                timestamp=datetime.now(),
                event_type=AuditEventType.SECURITY_VIOLATION,
                user_id=None,
                session_id=None,
                client_ip=self._get_client_ip(request),
                user_agent=request.headers.get('User-Agent', ''),
                endpoint=request.url.path,
                method=request.method,
                status_code=403,
                response_time_ms=None,
                request_size=0,
                response_size=None,
                sensitivity_level=SensitivityLevel.RESTRICTED,
                success=False,
                error_message=f"Security violation: {violation_type}",
                additional_context={
                    'violation_type': violation_type,
                    'severity': severity,
                    'details': details or {}
                }
            )
            
            await self._store_audit_event(audit_event)
            
        except Exception as e:
            logger.error(f"Error logging security violation: {str(e)}")
    
    def _get_endpoint_sensitivity(self, endpoint: str) -> SensitivityLevel:
        """Determine sensitivity level for endpoint"""
        # Check exact matches first
        if endpoint in self.sensitive_endpoints:
            return self.sensitive_endpoints[endpoint]
        
        # Check patterns
        if '/auth/' in endpoint:
            return SensitivityLevel.CONFIDENTIAL
        elif '/admin/' in endpoint:
            return SensitivityLevel.RESTRICTED
        elif '/transactions' in endpoint or '/goals' in endpoint:
            return SensitivityLevel.CONFIDENTIAL
        elif '/users/' in endpoint:
            return SensitivityLevel.INTERNAL
        else:
            return SensitivityLevel.PUBLIC
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address with proxy support"""
        # Check for forwarded headers (proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown'
    
    async def _extract_request_body(self, request: Request) -> Any:
        """Extract request body data"""
        try:
            if hasattr(request, '_body'):
                return request._body
            
            # Try to get JSON body
            try:
                return await request.json()
            except:
                # Try to get form data
                try:
                    return await request.form()
                except:
                    return None
        except Exception:
            return None
    
    async def _extract_response_body(self, response: Response) -> Any:
        """Extract response body data"""
        try:
            if hasattr(response, 'body'):
                body = response.body
                if isinstance(body, bytes):
                    try:
                        return json.loads(body.decode())
                    except:
                        return body.decode()[:1000]  # Limit size
                return body
            return None
        except Exception:
            return None
    
    async def _store_audit_event(self, event: AuditEvent):
        """Store audit event"""
        # Add to buffer
        self.buffer.append(event)
        
        # Log immediately for high-sensitivity events
        if event.sensitivity_level == SensitivityLevel.RESTRICTED or event.event_type == AuditEventType.SECURITY_VIOLATION:
            logger.critical(f"Audit Event: {event.to_dict()}")
        
        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush audit events to database"""
        if not self.buffer:
            return
        
        try:
            async with get_async_db_context() as session:
                # Create audit_logs table if it doesn't exist
                await self._ensure_audit_table(session)
                
                # Insert audit events
                for event in self.buffer:
                    await session.execute(
                        text("""
                            INSERT INTO audit_logs (
                                id, timestamp, event_type, user_id, session_id,
                                client_ip, user_agent, endpoint, method, status_code,
                                response_time_ms, request_size, response_size,
                                sensitivity_level, success, error_message, additional_context
                            ) VALUES (
                                :id, :timestamp, :event_type, :user_id, :session_id,
                                :client_ip, :user_agent, :endpoint, :method, :status_code,
                                :response_time_ms, :request_size, :response_size,
                                :sensitivity_level, :success, :error_message, :additional_context
                            )
                        """),
                        {
                            'id': event.id,
                            'timestamp': event.timestamp,
                            'event_type': event.event_type.value,
                            'user_id': event.user_id,
                            'session_id': event.session_id,
                            'client_ip': event.client_ip,
                            'user_agent': event.user_agent,
                            'endpoint': event.endpoint,
                            'method': event.method,
                            'status_code': event.status_code,
                            'response_time_ms': event.response_time_ms,
                            'request_size': event.request_size,
                            'response_size': event.response_size,
                            'sensitivity_level': event.sensitivity_level.value,
                            'success': event.success,
                            'error_message': event.error_message,
                            'additional_context': json.dumps(event.additional_context)
                        }
                    )
                
                await session.commit()
                logger.info(f"Flushed {len(self.buffer)} audit events to database")
                
        except Exception as e:
            logger.error(f"Error flushing audit buffer: {str(e)}")
            await log_error(
                e,
                severity=ErrorSeverity.HIGH,
                category=ErrorCategory.DATABASE,
                additional_context={'operation': 'audit_flush', 'buffer_size': len(self.buffer)}
            )
        finally:
            self.buffer.clear()
            self.last_flush = time.time()
    
    async def _ensure_audit_table(self, session: AsyncSession):
        """Ensure audit logs table exists"""
        try:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id VARCHAR(255) PRIMARY KEY,
                    timestamp TIMESTAMP NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    user_id VARCHAR(255),
                    session_id VARCHAR(255),
                    client_ip VARCHAR(45) NOT NULL,
                    user_agent TEXT,
                    endpoint VARCHAR(500) NOT NULL,
                    method VARCHAR(10) NOT NULL,
                    status_code INTEGER,
                    response_time_ms FLOAT,
                    request_size INTEGER DEFAULT 0,
                    response_size INTEGER,
                    sensitivity_level VARCHAR(20) NOT NULL,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    additional_context JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_endpoint ON audit_logs(endpoint);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_client_ip ON audit_logs(client_ip);
            """))
            
        except Exception as e:
            logger.error(f"Error creating audit table: {str(e)}")
    
    async def _background_flush(self):
        """Background task to flush audit events periodically"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                
                if self.buffer and (time.time() - self.last_flush) >= self.flush_interval:
                    await self._flush_buffer()
                    
            except Exception as e:
                logger.error(f"Error in background audit flush: {str(e)}")
    
    async def get_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: str = None,
        event_type: AuditEventType = None
    ) -> Dict[str, Any]:
        """Generate audit report"""
        try:
            async with get_async_db_context() as session:
                # Build query conditions
                conditions = ["timestamp BETWEEN :start_date AND :end_date"]
                params = {'start_date': start_date, 'end_date': end_date}
                
                if user_id:
                    conditions.append("user_id = :user_id")
                    params['user_id'] = user_id
                
                if event_type:
                    conditions.append("event_type = :event_type")
                    params['event_type'] = event_type.value
                
                where_clause = " AND ".join(conditions)
                
                # Get summary statistics
                summary_result = await session.execute(
                    text(f"""
                        SELECT 
                            COUNT(*) as total_events,
                            COUNT(DISTINCT user_id) as unique_users,
                            COUNT(DISTINCT client_ip) as unique_ips,
                            AVG(response_time_ms) as avg_response_time,
                            SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_requests
                        FROM audit_logs 
                        WHERE {where_clause}
                    """),
                    params
                )
                summary = summary_result.fetchone()
                
                # Get top endpoints
                endpoints_result = await session.execute(
                    text(f"""
                        SELECT endpoint, COUNT(*) as request_count
                        FROM audit_logs 
                        WHERE {where_clause}
                        GROUP BY endpoint
                        ORDER BY request_count DESC
                        LIMIT 10
                    """),
                    params
                )
                top_endpoints = [{'endpoint': row[0], 'count': row[1]} for row in endpoints_result.fetchall()]
                
                # Get security violations
                violations_result = await session.execute(
                    text(f"""
                        SELECT client_ip, COUNT(*) as violation_count
                        FROM audit_logs 
                        WHERE {where_clause} AND event_type = 'security_violation'
                        GROUP BY client_ip
                        ORDER BY violation_count DESC
                        LIMIT 10
                    """),
                    params
                )
                security_violations = [{'ip': row[0], 'count': row[1]} for row in violations_result.fetchall()]
                
                return {
                    'summary': {
                        'total_events': summary[0],
                        'unique_users': summary[1],
                        'unique_ips': summary[2],
                        'avg_response_time_ms': float(summary[3]) if summary[3] else 0,
                        'failed_requests': summary[4]
                    },
                    'top_endpoints': top_endpoints,
                    'security_violations': security_violations,
                    'report_period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat()
                    }
                }
                
        except Exception as e:
            logger.error(f"Error generating audit report: {str(e)}")
            return {}


# Global audit logger instance
audit_logger = AuditLogger()


async def log_request_response(
    request: Request,
    response: Response,
    response_time_ms: float,
    user_id: str = None,
    session_id: str = None,
    error_message: str = None
):
    """Convenience function for logging request/response"""
    await audit_logger.log_request_response(
        request=request,
        response=response,
        response_time_ms=response_time_ms,
        user_id=user_id,
        session_id=session_id,
        error_message=error_message
    )


async def log_authentication_event(
    request: Request,
    user_id: str = None,
    email: str = None,
    success: bool = False,
    failure_reason: str = None
):
    """Convenience function for logging authentication events"""
    await audit_logger.log_authentication_event(
        request=request,
        user_id=user_id,
        email=email,
        success=success,
        failure_reason=failure_reason
    )


async def log_data_access(
    user_id: str,
    resource_type: str,
    resource_id: str = None,
    action: str = "read",
    success: bool = True,
    **kwargs
):
    """Convenience function for logging data access events"""
    await audit_logger.log_data_access_event(
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        success=success,
        additional_context=kwargs
    )


async def log_security_violation(
    request: Request,
    violation_type: str,
    severity: str = "medium",
    **details
):
    """Convenience function for logging security violations"""
    await audit_logger.log_security_violation(
        request=request,
        violation_type=violation_type,
        severity=severity,
        details=details
    )