"""
Token Security Monitoring Service for MITA Financial Application

This service provides comprehensive monitoring and alerting for JWT token security events,
including suspicious activity detection, token usage analytics, and security reporting.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from app.core.audit_logging import log_security_event

logger = logging.getLogger(__name__)


class SecurityAlertLevel(Enum):
    """Security alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TokenSecurityMetrics:
    """Token security metrics for monitoring."""
    total_tokens_issued: int = 0
    total_tokens_revoked: int = 0
    invalid_token_attempts: int = 0
    scope_violations: int = 0
    suspicious_activities: int = 0
    token_refresh_rate: float = 0.0
    average_token_lifetime: float = 0.0


class TokenSecurityMonitor:
    """
    Comprehensive token security monitoring system.
    """
    
    def __init__(self):
        self.metrics = TokenSecurityMetrics()
        self.suspicious_ips = set()
        self.rate_limit_violations = {}
        self.failed_attempts = {}
        
    def log_token_creation(
        self, 
        user_id: str, 
        token_type: str, 
        scopes: List[str],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log token creation event with security monitoring."""
        self.metrics.total_tokens_issued += 1
        
        # Log security event
        log_security_event("token_created", {
            "user_id": user_id,
            "token_type": token_type,
            "scopes": scopes,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Check for suspicious token creation patterns
        self._check_suspicious_token_creation(user_id, ip_address, scopes)
        
    def log_token_usage(
        self,
        user_id: str,
        endpoint: str,
        scopes_used: List[str],
        ip_address: Optional[str] = None,
        success: bool = True
    ):
        """Log token usage with security analysis."""
        event_type = "token_usage_success" if success else "token_usage_failed"
        
        log_security_event(event_type, {
            "user_id": user_id,
            "endpoint": endpoint,
            "scopes_used": scopes_used,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        if not success:
            self.metrics.invalid_token_attempts += 1
            self._track_failed_attempt(user_id, ip_address)
            
    def log_scope_violation(
        self,
        user_id: str,
        endpoint: str,
        required_scopes: List[str],
        token_scopes: List[str],
        ip_address: Optional[str] = None
    ):
        """Log scope violation with security analysis."""
        self.metrics.scope_violations += 1
        
        log_security_event("scope_violation", {
            "user_id": user_id,
            "endpoint": endpoint,
            "required_scopes": required_scopes,
            "token_scopes": token_scopes,
            "missing_scopes": list(set(required_scopes) - set(token_scopes)),
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": self._calculate_violation_severity(required_scopes)
        })
        
        # Check for privilege escalation attempts
        self._check_privilege_escalation(user_id, required_scopes, token_scopes, ip_address)
        
    def log_token_revocation(
        self,
        user_id: str,
        token_type: str,
        reason: str,
        ip_address: Optional[str] = None
    ):
        """Log token revocation event."""
        self.metrics.total_tokens_revoked += 1
        
        log_security_event("token_revoked", {
            "user_id": user_id,
            "token_type": token_type,
            "reason": reason,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def detect_suspicious_activity(
        self,
        user_id: str,
        activity_type: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None
    ) -> SecurityAlertLevel:
        """
        Detect and classify suspicious activity.
        
        Returns:
            SecurityAlertLevel indicating the severity of the activity
        """
        self.metrics.suspicious_activities += 1
        
        alert_level = self._classify_activity(activity_type, details)
        
        log_security_event("suspicious_activity_detected", {
            "user_id": user_id,
            "activity_type": activity_type,
            "alert_level": alert_level.value,
            "details": details,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Take automated actions based on severity
        self._handle_security_alert(user_id, alert_level, activity_type, ip_address)
        
        return alert_level
        
    def check_token_anomalies(
        self,
        user_id: str,
        token_payload: Dict[str, Any],
        request_context: Dict[str, Any]
    ) -> List[str]:
        """
        Check for token-related anomalies.
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Check for unusual token age
        token_age = time.time() - token_payload.get('iat', 0)
        if token_age > 86400:  # 24 hours
            anomalies.append("token_age_unusual")
            
        # Check for scope creep
        token_scopes = token_payload.get('scope', '').split()
        if len(token_scopes) > 15:  # Unusually high number of scopes
            anomalies.append("excessive_scopes")
            
        # Check for geographic anomaly
        current_country = request_context.get('country')
        token_country = token_payload.get('country')
        if current_country and token_country and current_country != token_country:
            anomalies.append("geographic_anomaly")
            
        # Check for unusual user agent
        if self._is_suspicious_user_agent(request_context.get('user_agent', '')):
            anomalies.append("suspicious_user_agent")
            
        if anomalies:
            log_security_event("token_anomalies_detected", {
                "user_id": user_id,
                "anomalies": anomalies,
                "token_claims": {k: v for k, v in token_payload.items() if k not in ['sub', 'jti']},
                "request_context": request_context,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        return anomalies
        
    def get_security_metrics(self) -> TokenSecurityMetrics:
        """Get current security metrics."""
        return self.metrics
        
    def get_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        return {
            "metrics": {
                "total_tokens_issued": self.metrics.total_tokens_issued,
                "total_tokens_revoked": self.metrics.total_tokens_revoked,
                "invalid_token_attempts": self.metrics.invalid_token_attempts,
                "scope_violations": self.metrics.scope_violations,
                "suspicious_activities": self.metrics.suspicious_activities,
                "token_refresh_rate": self.metrics.token_refresh_rate,
                "average_token_lifetime": self.metrics.average_token_lifetime
            },
            "suspicious_ips": list(self.suspicious_ips),
            "rate_limit_violations_count": len(self.rate_limit_violations),
            "failed_attempts_count": len(self.failed_attempts),
            "report_generated": datetime.utcnow().isoformat()
        }
        
    def _check_suspicious_token_creation(
        self, 
        user_id: str, 
        ip_address: Optional[str], 
        scopes: List[str]
    ):
        """Check for suspicious patterns in token creation."""
        # Check for rapid token creation
        current_time = time.time()
        user_key = f"token_creation_{user_id}"
        
        if user_key not in self.rate_limit_violations:
            self.rate_limit_violations[user_key] = []
            
        # Clean old entries
        self.rate_limit_violations[user_key] = [
            t for t in self.rate_limit_violations[user_key] 
            if current_time - t < 3600  # Last hour
        ]
        
        self.rate_limit_violations[user_key].append(current_time)
        
        # Alert if too many tokens created in short time
        if len(self.rate_limit_violations[user_key]) > 10:  # 10 tokens per hour
            self.detect_suspicious_activity(
                user_id,
                "rapid_token_creation",
                {
                    "tokens_created_last_hour": len(self.rate_limit_violations[user_key]),
                    "scopes": scopes
                },
                ip_address
            )
            
    def _track_failed_attempt(self, user_id: str, ip_address: Optional[str]):
        """Track failed authentication attempts."""
        current_time = time.time()
        
        # Track by user
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []
            
        self.failed_attempts[user_id] = [
            t for t in self.failed_attempts[user_id]
            if current_time - t < 3600  # Last hour
        ]
        self.failed_attempts[user_id].append(current_time)
        
        # Track by IP if available
        if ip_address:
            ip_key = f"ip_{ip_address}"
            if ip_key not in self.failed_attempts:
                self.failed_attempts[ip_key] = []
                
            self.failed_attempts[ip_key] = [
                t for t in self.failed_attempts[ip_key]
                if current_time - t < 3600  # Last hour
            ]
            self.failed_attempts[ip_key].append(current_time)
            
            # Mark IP as suspicious if too many failures
            if len(self.failed_attempts[ip_key]) > 5:
                self.suspicious_ips.add(ip_address)
                
    def _check_privilege_escalation(
        self,
        user_id: str,
        required_scopes: List[str],
        token_scopes: List[str],
        ip_address: Optional[str]
    ):
        """Check for potential privilege escalation attempts."""
        admin_scopes = ["admin:system", "admin:users", "admin:audit"]
        premium_scopes = ["premium:features", "premium:ai_insights", "advanced:analytics"]
        
        # Check if attempting to access admin scopes without having them
        admin_attempt = any(scope in required_scopes for scope in admin_scopes)
        has_admin = any(scope in token_scopes for scope in admin_scopes)
        
        if admin_attempt and not has_admin:
            self.detect_suspicious_activity(
                user_id,
                "admin_privilege_escalation_attempt",
                {
                    "required_admin_scopes": [s for s in required_scopes if s in admin_scopes],
                    "user_scopes": token_scopes
                },
                ip_address
            )
            
        # Check for premium feature access attempts
        premium_attempt = any(scope in required_scopes for scope in premium_scopes)
        has_premium = any(scope in token_scopes for scope in premium_scopes)
        
        if premium_attempt and not has_premium:
            self.detect_suspicious_activity(
                user_id,
                "premium_privilege_escalation_attempt",
                {
                    "required_premium_scopes": [s for s in required_scopes if s in premium_scopes],
                    "user_scopes": token_scopes
                },
                ip_address
            )
            
    def _calculate_violation_severity(self, required_scopes: List[str]) -> str:
        """Calculate severity of scope violation."""
        admin_scopes = ["admin:system", "admin:users", "admin:audit"]
        financial_scopes = ["write:financial_data", "delete:transactions"]
        
        if any(scope in required_scopes for scope in admin_scopes):
            return "critical"
        elif any(scope in required_scopes for scope in financial_scopes):
            return "high"
        elif len(required_scopes) > 3:
            return "medium"
        else:
            return "low"
            
    def _classify_activity(self, activity_type: str, details: Dict[str, Any]) -> SecurityAlertLevel:
        """Classify suspicious activity severity."""
        if activity_type in ["admin_privilege_escalation_attempt", "token_tampering"]:
            return SecurityAlertLevel.CRITICAL
        elif activity_type in ["premium_privilege_escalation_attempt", "rapid_token_creation"]:
            return SecurityAlertLevel.HIGH
        elif activity_type in ["unusual_geographic_access", "suspicious_user_agent"]:
            return SecurityAlertLevel.MEDIUM
        else:
            return SecurityAlertLevel.LOW
            
    def _handle_security_alert(
        self,
        user_id: str,
        alert_level: SecurityAlertLevel,
        activity_type: str,
        ip_address: Optional[str]
    ):
        """Handle security alerts with automated responses."""
        if alert_level == SecurityAlertLevel.CRITICAL:
            # Critical: Immediate token revocation and user lockout
            logger.critical(
                f"CRITICAL security alert for user {user_id}: {activity_type} "
                f"from IP {ip_address}. Immediate action required."
            )
            # Here you would integrate with your alerting system
            
        elif alert_level == SecurityAlertLevel.HIGH:
            # High: Enhanced monitoring and potential rate limiting
            logger.error(
                f"HIGH security alert for user {user_id}: {activity_type} "
                f"from IP {ip_address}. Enhanced monitoring activated."
            )
            
        elif alert_level == SecurityAlertLevel.MEDIUM:
            # Medium: Increased logging and monitoring
            logger.warning(
                f"MEDIUM security alert for user {user_id}: {activity_type} "
                f"from IP {ip_address}. Monitoring increased."
            )
            
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent appears suspicious."""
        suspicious_patterns = [
            "bot", "crawler", "spider", "scraper", "curl", "wget",
            "python-requests", "postman", "insomnia"
        ]
        
        if not user_agent or len(user_agent) < 10:
            return True
            
        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)


# Global instance
security_monitor = TokenSecurityMonitor()


def get_security_monitor() -> TokenSecurityMonitor:
    """Get the global security monitor instance."""
    return security_monitor


def log_token_security_event(
    event_type: str,
    user_id: str,
    details: Dict[str, Any],
    ip_address: Optional[str] = None
):
    """Convenience function to log token security events."""
    security_monitor.detect_suspicious_activity(
        user_id=user_id,
        activity_type=event_type,
        details=details,
        ip_address=ip_address
    )