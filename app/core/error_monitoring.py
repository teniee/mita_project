"""
Comprehensive Error Monitoring and Alerting System
Provides real-time error tracking, alerting, and performance monitoring
"""

import logging
import traceback
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from fastapi import Request, Response
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.core.config import settings

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better organization"""
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    PERFORMANCE = "performance"


@dataclass
class ErrorEvent:
    """Structured error event data"""
    id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    exception_type: str
    stack_trace: str
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    additional_context: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['severity'] = self.severity.value
        data['category'] = self.category.value
        # Ensure additional_context is JSON serializable
        if self.additional_context:
            data['additional_context'] = self._safe_serialize_context(self.additional_context)
        return data
    
    def _safe_serialize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Safely serialize context data to prevent JSON errors"""
        safe_context = {}
        for key, value in context.items():
            try:
                # Test JSON serialization
                json.dumps(value)
                safe_context[key] = value
            except (TypeError, ValueError):
                # If not serializable, convert to string representation
                if hasattr(value, '__dict__'):
                    safe_context[key] = str(type(value).__name__)
                elif hasattr(value, 'filename') and hasattr(value, 'content_type'):
                    # Handle UploadFile objects
                    safe_context[key] = {
                        'type': 'UploadFile',
                        'filename': getattr(value, 'filename', 'unknown'),
                        'content_type': getattr(value, 'content_type', 'unknown')
                    }
                else:
                    safe_context[key] = str(value)[:500]  # Truncate long strings
        return safe_context


class ErrorAggregator:
    """Aggregates errors for pattern detection"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_patterns: Dict[str, List[ErrorEvent]] = {}
        self.alert_thresholds = {
            ErrorSeverity.CRITICAL: 1,  # Alert immediately
            ErrorSeverity.HIGH: 3,      # Alert after 3 occurrences
            ErrorSeverity.MEDIUM: 10,   # Alert after 10 occurrences
            ErrorSeverity.LOW: 50,      # Alert after 50 occurrences
        }
    
    def add_error(self, error: ErrorEvent) -> bool:
        """Add error and return True if alert threshold is reached"""
        error_key = f"{error.category.value}:{error.exception_type}"
        
        # Update counts
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Store pattern
        if error_key not in self.error_patterns:
            self.error_patterns[error_key] = []
        
        self.error_patterns[error_key].append(error)
        
        # Keep only recent errors (last 1000)
        if len(self.error_patterns[error_key]) > 1000:
            self.error_patterns[error_key] = self.error_patterns[error_key][-1000:]
        
        # Check if alert threshold is reached
        threshold = self.alert_thresholds.get(error.severity, 10)
        return self.error_counts[error_key] >= threshold
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_types': len(self.error_counts),
            'top_errors': sorted(
                self.error_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10],
            'recent_critical_errors': self._get_recent_critical_errors()
        }
    
    def _get_recent_critical_errors(self) -> List[Dict[str, Any]]:
        """Get recent critical errors"""
        recent_errors = []
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        for pattern_errors in self.error_patterns.values():
            for error in pattern_errors:
                if (error.severity == ErrorSeverity.CRITICAL and 
                    error.timestamp > cutoff_time):
                    recent_errors.append(error.to_dict())
        
        return sorted(recent_errors, key=lambda x: x['timestamp'], reverse=True)[:10]


class AlertManager:
    """Manages alert notifications"""
    
    def __init__(self):
        self.webhook_urls = getattr(settings, 'ALERT_WEBHOOK_URLS', [])
        self.email_alerts = getattr(settings, 'ALERT_EMAILS', [])
        self.alert_cooldown = {}  # Prevent spam
    
    async def send_alert(self, error: ErrorEvent, error_count: int = 1):
        """Send alert notifications"""
        alert_key = f"{error.category.value}:{error.exception_type}"
        
        # Check cooldown (don't spam alerts)
        cooldown_key = f"{alert_key}:{error.severity.value}"
        now = datetime.now()
        
        if cooldown_key in self.alert_cooldown:
            last_alert = self.alert_cooldown[cooldown_key]
            cooldown_minutes = {
                ErrorSeverity.CRITICAL: 5,
                ErrorSeverity.HIGH: 15,
                ErrorSeverity.MEDIUM: 60,
                ErrorSeverity.LOW: 240,
            }
            
            if now - last_alert < timedelta(minutes=cooldown_minutes[error.severity]):
                return  # Still in cooldown
        
        self.alert_cooldown[cooldown_key] = now
        
        # Prepare alert message
        alert_data = {
            'timestamp': error.timestamp.isoformat(),
            'severity': error.severity.value.upper(),
            'category': error.category.value,
            'message': error.message,
            'error_type': error.exception_type,
            'count': error_count,
            'endpoint': error.endpoint,
            'user_id': error.user_id,
            'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
            'service': 'MITA Backend'
        }
        
        # Send webhook alerts
        await self._send_webhook_alerts(alert_data)
        
        # Send email alerts (if configured)
        await self._send_email_alerts(alert_data)
    
    async def _send_webhook_alerts(self, alert_data: Dict[str, Any]):
        """Send webhook alerts (Slack, Discord, etc.)"""
        if not self.webhook_urls:
            return
        
        # Format message for Slack/Discord
        message = self._format_webhook_message(alert_data)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for webhook_url in self.webhook_urls:
                try:
                    await client.post(webhook_url, json=message)
                except Exception as e:
                    logger.error(f"Failed to send webhook alert: {str(e)}")
    
    def _format_webhook_message(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert message for webhooks"""
        severity_emoji = {
            'CRITICAL': '🚨',
            'HIGH': '⚠️',
            'MEDIUM': '⚡',
            'LOW': 'ℹ️'
        }
        
        emoji = severity_emoji.get(alert_data['severity'], '❗')
        
        return {
            "text": f"{emoji} **{alert_data['severity']} Alert - {alert_data['service']}**",
            "attachments": [
                {
                    "color": "danger" if alert_data['severity'] in ['CRITICAL', 'HIGH'] else "warning",
                    "fields": [
                        {"title": "Error Type", "value": alert_data['error_type'], "short": True},
                        {"title": "Category", "value": alert_data['category'], "short": True},
                        {"title": "Count", "value": str(alert_data['count']), "short": True},
                        {"title": "Environment", "value": alert_data['environment'], "short": True},
                        {"title": "Endpoint", "value": alert_data.get('endpoint', 'N/A'), "short": True},
                        {"title": "Time", "value": alert_data['timestamp'], "short": True},
                        {"title": "Message", "value": alert_data['message'][:500], "short": False}
                    ]
                }
            ]
        }
    
    async def _send_email_alerts(self, alert_data: Dict[str, Any]):
        """Send email alerts (implementation depends on email service)"""
        # This would integrate with your email service (SendGrid, SES, etc.)
        # For now, just log the alert
        logger.info(f"Email alert would be sent: {alert_data}")


class ErrorMonitor:
    """Main error monitoring system"""
    
    def __init__(self):
        self.aggregator = ErrorAggregator()
        self.alert_manager = AlertManager()
        self.performance_tracker = PerformanceTracker()
        self._setup_sentry()
    
    def _setup_sentry(self):
        """Initialize Sentry for error tracking"""
        sentry_dsn = getattr(settings, 'SENTRY_DSN', None)
        if sentry_dsn:
            sentry_sdk.init(
                dsn=sentry_dsn,
                integrations=[
                    FastApiIntegration(auto_enable=True),
                    SqlalchemyIntegration(),
                ],
                environment=getattr(settings, 'ENVIRONMENT', 'development'),
                traces_sample_rate=0.1,  # Adjust based on traffic
                send_default_pii=False,  # Don't send PII data
            )
            logger.info("Sentry error tracking initialized")
    
    async def log_error(
        self,
        exception: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        user_id: str = None,
        request: Request = None,
        additional_context: Dict[str, Any] = None
    ):
        """Log an error event"""
        try:
            # Create error event
            error_event = ErrorEvent(
                id=f"{datetime.now().isoformat()}_{id(exception)}",
                timestamp=datetime.now(),
                severity=severity,
                category=category,
                message=str(exception),
                exception_type=type(exception).__name__,
                stack_trace=traceback.format_exc(),
                user_id=user_id,
                request_id=getattr(request, 'id', None) if request else None,
                endpoint=str(request.url.path) if request else None,
                method=request.method if request else None,
                additional_context=additional_context or {}
            )
            
            # Log to application logger
            log_level = {
                ErrorSeverity.LOW: logging.INFO,
                ErrorSeverity.MEDIUM: logging.WARNING,
                ErrorSeverity.HIGH: logging.ERROR,
                ErrorSeverity.CRITICAL: logging.CRITICAL,
            }
            # Prepare safe logging extra data
            safe_extra = {
                'error_event': error_event.to_dict(),
                'user_id': user_id,
                'endpoint': error_event.endpoint
            }
            
            logger.log(
                log_level[severity],
                f"Error [{category.value}]: {str(exception)}",
                extra=safe_extra
            )
            
            # Send to Sentry
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("category", category.value)
                scope.set_tag("severity", severity.value)
                if user_id:
                    scope.set_user({"id": user_id})
                if additional_context:
                    # Use safe serialization for Sentry context
                    safe_context = error_event._safe_serialize_context(additional_context)
                    for key, value in safe_context.items():
                        scope.set_extra(key, value)
                
                sentry_sdk.capture_exception(exception)
            
            # Check if alert should be sent
            should_alert = self.aggregator.add_error(error_event)
            if should_alert or severity == ErrorSeverity.CRITICAL:
                error_count = self.aggregator.error_counts.get(
                    f"{category.value}:{type(exception).__name__}", 1
                )
                await self.alert_manager.send_alert(error_event, error_count)
        
        except Exception as e:
            # Don't let error monitoring crash the application
            logger.error(f"Error in error monitoring system: {str(e)}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        error_stats = self.aggregator.get_error_stats()
        perf_stats = self.performance_tracker.get_stats()
        
        # Determine overall health
        critical_errors = len([
            e for e in self.aggregator.error_patterns.values()
            for error in e
            if error.severity == ErrorSeverity.CRITICAL and
            error.timestamp > datetime.now() - timedelta(hours=1)
        ])
        
        health_status = "healthy"
        if critical_errors > 0:
            health_status = "critical"
        elif error_stats['total_errors'] > 100:
            health_status = "degraded"
        
        return {
            'status': health_status,
            'timestamp': datetime.now().isoformat(),
            'error_stats': error_stats,
            'performance_stats': perf_stats,
            'critical_errors_last_hour': critical_errors
        }


class PerformanceTracker:
    """Track performance metrics"""
    
    def __init__(self):
        self.request_times: List[float] = []
        self.slow_requests: List[Dict[str, Any]] = []
        self.slow_threshold = 2.0  # seconds
    
    def record_request(self, duration: float, endpoint: str, method: str):
        """Record request performance"""
        self.request_times.append(duration)
        
        # Keep only recent data
        if len(self.request_times) > 1000:
            self.request_times = self.request_times[-1000:]
        
        # Track slow requests
        if duration > self.slow_threshold:
            self.slow_requests.append({
                'duration': duration,
                'endpoint': endpoint,
                'method': method,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only recent slow requests
            if len(self.slow_requests) > 100:
                self.slow_requests = self.slow_requests[-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.request_times:
            return {'avg_response_time': 0, 'slow_requests': 0}
        
        return {
            'avg_response_time': sum(self.request_times) / len(self.request_times),
            'max_response_time': max(self.request_times),
            'min_response_time': min(self.request_times),
            'slow_requests': len(self.slow_requests),
            'total_requests': len(self.request_times)
        }


# Global error monitor instance
error_monitor = ErrorMonitor()


async def log_error(
    exception: Exception,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.SYSTEM,
    user_id: str = None,
    request: Request = None,
    **kwargs
):
    """Convenience function for logging errors"""
    await error_monitor.log_error(
        exception=exception,
        severity=severity,
        category=category,
        user_id=user_id,
        request=request,
        additional_context=kwargs
    )


def get_health_status() -> Dict[str, Any]:
    """Get system health status"""
    return error_monitor.get_health_status()