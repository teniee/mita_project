"""
Token Security Service for MITA Financial Application

This service provides comprehensive token security monitoring, metrics,
and threat detection for the JWT-based authentication system.

Financial services compliance requirements:
- Audit trail for all token operations
- Real-time threat detection
- Performance monitoring
- Security metrics for compliance reporting
"""

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import asyncio
from threading import Lock

from app.core.audit_logging import log_security_event
from app.services.auth_jwt_service import get_token_info, is_token_blacklisted
from app.core.upstash import get_blacklist_metrics

logger = logging.getLogger(__name__)


@dataclass
class SecurityAlert:
    """Security alert for token-related threats."""
    alert_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    message: str
    user_id: Optional[str]
    timestamp: datetime
    metadata: Dict


@dataclass
class TokenMetrics:
    """Token operation metrics."""
    total_issued: int = 0
    total_verified: int = 0
    total_blacklisted: int = 0
    blacklist_hits: int = 0
    verification_failures: int = 0
    refresh_operations: int = 0
    security_alerts: int = 0


class TokenSecurityService:
    """Central service for token security monitoring and threat detection."""
    
    def __init__(self):
        self._metrics = TokenMetrics()
        self._alerts: deque = deque(maxlen=1000)  # Keep last 1000 alerts
        self._user_activity: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._suspicious_ips: Dict[str, int] = defaultdict(int)
        self._lock = Lock()
        
        # Rate limiting thresholds
        self.MAX_FAILED_ATTEMPTS = 10  # per user per hour
        self.MAX_TOKEN_REQUESTS = 100  # per user per hour
        self.SUSPICIOUS_IP_THRESHOLD = 50  # failed attempts per IP per hour
        
        logger.info("Token Security Service initialized")
    
    def record_token_issued(self, user_id: str, token_type: str, client_ip: Optional[str] = None):
        """Record token issuance for monitoring."""
        with self._lock:
            self._metrics.total_issued += 1
            
            # Track user activity
            self._user_activity[user_id].append({
                "action": "token_issued",
                "type": token_type,
                "timestamp": time.time(),
                "ip": client_ip
            })
            
            # Check for suspicious activity
            self._check_token_issuance_rate(user_id, client_ip)
            
        log_security_event("token_issued", {
            "user_id": user_id,
            "token_type": token_type,
            "client_ip": client_ip
        })
    
    def record_token_verification(self, user_id: Optional[str], success: bool, 
                                  client_ip: Optional[str] = None, token_jti: Optional[str] = None):
        """Record token verification attempt."""
        with self._lock:
            self._metrics.total_verified += 1
            
            if success:
                if user_id:
                    self._user_activity[user_id].append({
                        "action": "verification_success",
                        "timestamp": time.time(),
                        "ip": client_ip,
                        "jti": token_jti[:8] + "..." if token_jti else None
                    })
            else:
                self._metrics.verification_failures += 1
                
                if client_ip:
                    self._suspicious_ips[client_ip] += 1
                    
                if user_id:
                    self._user_activity[user_id].append({
                        "action": "verification_failure",
                        "timestamp": time.time(),
                        "ip": client_ip
                    })
                    
                    # Check for brute force attempts
                    self._check_verification_failures(user_id, client_ip)
    
    def record_token_blacklisted(self, user_id: str, token_jti: str, reason: str = "logout"):
        """Record token blacklisting."""
        with self._lock:
            self._metrics.total_blacklisted += 1
            
            self._user_activity[user_id].append({
                "action": "token_blacklisted",
                "timestamp": time.time(),
                "jti": token_jti[:8] + "...",
                "reason": reason
            })
    
    def record_blacklist_hit(self, user_id: Optional[str], token_jti: str, client_ip: Optional[str] = None):
        """Record attempt to use blacklisted token."""
        with self._lock:
            self._metrics.blacklist_hits += 1
            
            # This is always suspicious
            alert = SecurityAlert(
                alert_type="blacklisted_token_usage",
                severity="HIGH",
                message=f"Attempted use of blacklisted token {token_jti[:8]}...",
                user_id=user_id,
                timestamp=datetime.utcnow(),
                metadata={"jti": token_jti[:8] + "...", "client_ip": client_ip}
            )
            
            self._add_alert(alert)
            
        log_security_event("blacklisted_token_usage_attempt", {
            "user_id": user_id,
            "jti": token_jti[:8] + "...",
            "client_ip": client_ip
        })
    
    def record_refresh_token_operation(self, user_id: str, success: bool, client_ip: Optional[str] = None):
        """Record refresh token operation."""
        with self._lock:
            self._metrics.refresh_operations += 1
            
            self._user_activity[user_id].append({
                "action": "token_refresh",
                "success": success,
                "timestamp": time.time(),
                "ip": client_ip
            })
            
            if not success and client_ip:
                self._suspicious_ips[client_ip] += 1
    
    def _check_token_issuance_rate(self, user_id: str, client_ip: Optional[str]):
        """Check for suspicious token issuance rates."""
        now = time.time()
        hour_ago = now - 3600
        
        user_tokens_last_hour = sum(1 for activity in self._user_activity[user_id] 
                                   if activity["action"] == "token_issued" 
                                   and activity["timestamp"] > hour_ago)
        
        if user_tokens_last_hour > self.MAX_TOKEN_REQUESTS:
            alert = SecurityAlert(
                alert_type="excessive_token_requests",
                severity="MEDIUM",
                message=f"User {user_id} requested {user_tokens_last_hour} tokens in the last hour",
                user_id=user_id,
                timestamp=datetime.utcnow(),
                metadata={"token_count": user_tokens_last_hour, "client_ip": client_ip}
            )
            self._add_alert(alert)
    
    def _check_verification_failures(self, user_id: str, client_ip: Optional[str]):
        """Check for suspicious verification failure patterns."""
        now = time.time()
        hour_ago = now - 3600
        
        user_failures = sum(1 for activity in self._user_activity[user_id] 
                           if activity["action"] == "verification_failure" 
                           and activity["timestamp"] > hour_ago)
        
        if user_failures > self.MAX_FAILED_ATTEMPTS:
            alert = SecurityAlert(
                alert_type="excessive_verification_failures",
                severity="HIGH",
                message=f"User {user_id} had {user_failures} verification failures in the last hour",
                user_id=user_id,
                timestamp=datetime.utcnow(),
                metadata={"failure_count": user_failures, "client_ip": client_ip}
            )
            self._add_alert(alert)
        
        # Check IP-based failures
        if client_ip and self._suspicious_ips[client_ip] > self.SUSPICIOUS_IP_THRESHOLD:
            alert = SecurityAlert(
                alert_type="suspicious_ip_activity",
                severity="CRITICAL",
                message=f"IP {client_ip} has {self._suspicious_ips[client_ip]} failures",
                user_id=user_id,
                timestamp=datetime.utcnow(),
                metadata={"ip": client_ip, "failure_count": self._suspicious_ips[client_ip]}
            )
            self._add_alert(alert)
    
    def _add_alert(self, alert: SecurityAlert):
        """Add security alert and log it."""
        self._alerts.append(alert)
        self._metrics.security_alerts += 1
        
        logger.warning(f"SECURITY ALERT [{alert.severity}]: {alert.alert_type} - {alert.message}")
        
        log_security_event(f"security_alert_{alert.alert_type}", {
            "severity": alert.severity,
            "message": alert.message,
            "user_id": alert.user_id,
            "metadata": alert.metadata
        })
    
    def get_user_activity_summary(self, user_id: str) -> Dict:
        """Get user activity summary for the last 24 hours."""
        now = time.time()
        day_ago = now - 86400
        
        activities = [activity for activity in self._user_activity[user_id] 
                     if activity["timestamp"] > day_ago]
        
        summary = {
            "total_activities": len(activities),
            "tokens_issued": sum(1 for a in activities if a["action"] == "token_issued"),
            "successful_verifications": sum(1 for a in activities 
                                          if a["action"] == "verification_success"),
            "failed_verifications": sum(1 for a in activities 
                                      if a["action"] == "verification_failure"),
            "tokens_blacklisted": sum(1 for a in activities if a["action"] == "token_blacklisted"),
            "refresh_operations": sum(1 for a in activities if a["action"] == "token_refresh"),
            "unique_ips": len(set(a.get("ip") for a in activities if a.get("ip"))),
            "last_activity": max(activities, key=lambda a: a["timestamp"])["timestamp"] if activities else None
        }
        
        return summary
    
    def get_security_metrics(self) -> Dict:
        """Get comprehensive security metrics."""
        # Get Redis blacklist metrics
        redis_metrics = get_blacklist_metrics()
        
        return {
            "token_metrics": {
                "total_issued": self._metrics.total_issued,
                "total_verified": self._metrics.total_verified,
                "total_blacklisted": self._metrics.total_blacklisted,
                "blacklist_hits": self._metrics.blacklist_hits,
                "verification_failures": self._metrics.verification_failures,
                "refresh_operations": self._metrics.refresh_operations,
                "security_alerts": self._metrics.security_alerts
            },
            "redis_metrics": redis_metrics,
            "alert_summary": {
                "total_alerts": len(self._alerts),
                "critical_alerts": sum(1 for a in self._alerts if a.severity == "CRITICAL"),
                "high_alerts": sum(1 for a in self._alerts if a.severity == "HIGH"),
                "medium_alerts": sum(1 for a in self._alerts if a.severity == "MEDIUM"),
                "low_alerts": sum(1 for a in self._alerts if a.severity == "LOW"),
            },
            "suspicious_activity": {
                "suspicious_ips": len([ip for ip, count in self._suspicious_ips.items() 
                                     if count > self.SUSPICIOUS_IP_THRESHOLD // 2]),
                "active_users": len(self._user_activity)
            }
        }
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict]:
        """Get recent security alerts."""
        recent_alerts = list(self._alerts)[-limit:]
        return [
            {
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "user_id": alert.user_id,
                "timestamp": alert.timestamp.isoformat(),
                "metadata": alert.metadata
            }
            for alert in recent_alerts
        ]
    
    async def cleanup_old_data(self):
        """Clean up old monitoring data to prevent memory leaks."""
        now = time.time()
        day_ago = now - 86400
        
        with self._lock:
            # Clean up old user activities
            for user_id in list(self._user_activity.keys()):
                activities = self._user_activity[user_id]
                # Keep only activities from the last 24 hours
                recent_activities = deque([
                    activity for activity in activities 
                    if activity["timestamp"] > day_ago
                ], maxlen=100)
                
                if recent_activities:
                    self._user_activity[user_id] = recent_activities
                else:
                    del self._user_activity[user_id]
            
            # Clean up suspicious IPs (reset counters daily)
            hour_ago = now - 3600
            self._suspicious_ips = defaultdict(int, {
                ip: count for ip, count in self._suspicious_ips.items()
                # Keep IPs that had recent activity
            })
        
        logger.debug("Token security monitoring data cleanup completed")
    
    def check_token_health(self, token: str) -> Dict:
        """Comprehensive token health check."""
        token_info = get_token_info(token)
        
        if not token_info:
            return {
                "status": "invalid",
                "reason": "Token could not be decoded"
            }
        
        jti = token_info.get("jti")
        user_id = token_info.get("user_id")
        exp = token_info.get("exp", 0)
        now = time.time()
        
        health = {
            "status": "healthy",
            "token_info": {
                "user_id": user_id,
                "jti": jti[:8] + "..." if jti else None,
                "scope": token_info.get("scope"),
                "expires_in": max(0, int(exp - now)),
                "is_expired": exp < now
            }
        }
        
        # Check if blacklisted
        if jti:
            try:
                is_blacklisted = is_token_blacklisted(jti)
                health["is_blacklisted"] = is_blacklisted
                if is_blacklisted:
                    health["status"] = "blacklisted"
                    health["reason"] = "Token is in blacklist"
            except Exception as e:
                health["blacklist_check_error"] = str(e)
        
        # Check expiration
        if exp < now:
            health["status"] = "expired"
            health["reason"] = "Token has expired"
        
        # Check user activity
        if user_id:
            user_summary = self.get_user_activity_summary(user_id)
            health["user_activity"] = user_summary
        
        return health


# Global instance
token_security_service = TokenSecurityService()


async def start_security_monitoring():
    """Start background tasks for security monitoring."""
    logger.info("Starting token security monitoring background tasks")
    
    # Schedule periodic cleanup
    async def periodic_cleanup():
        while True:
            try:
                await token_security_service.cleanup_old_data()
                await asyncio.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Security monitoring cleanup error: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes
    
    # Start cleanup task
    asyncio.create_task(periodic_cleanup())