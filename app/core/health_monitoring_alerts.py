"""
Health Monitoring and Alerting System
Advanced alerting and notification system for middleware health issues
"""

import asyncio
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from threading import Lock

from app.core.config import settings
from app.core.middleware_health_monitor import MiddlewareHealthReport, HealthStatus

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert notification channels"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    LOG = "log"


@dataclass
class Alert:
    """Alert object"""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    component: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledgements: List[str] = field(default_factory=list)


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    condition: Callable[[MiddlewareHealthReport], bool]
    severity: AlertSeverity
    channels: List[AlertChannel]
    cooldown_minutes: int = 5
    require_acknowledgement: bool = False
    auto_resolve: bool = True
    escalation_minutes: Optional[int] = None


class HealthAlertManager:
    """
    Manages health monitoring alerts and notifications
    Designed to prevent alert fatigue while ensuring critical issues are escalated
    """
    
    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history_size = 10000
        self.alert_rules = self._initialize_alert_rules()
        self.cooldown_tracker: Dict[str, datetime] = {}
        self.lock = Lock()
        self.notification_channels = self._setup_notification_channels()
    
    def _initialize_alert_rules(self) -> List[AlertRule]:
        """Initialize default alert rules for middleware health monitoring"""
        return [
            # Critical system health alerts
            AlertRule(
                name="system_unhealthy",
                condition=lambda report: report.overall_status == HealthStatus.UNHEALTHY,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK, AlertChannel.PAGERDUTY],
                cooldown_minutes=1,  # Very short cooldown for critical alerts
                require_acknowledgement=True,
                escalation_minutes=10
            ),
            
            # Performance degradation alerts
            AlertRule(
                name="performance_critical",
                condition=lambda report: report.response_time_ms > 10000,  # 10+ seconds
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=2,
                require_acknowledgement=True,
                escalation_minutes=15
            ),
            
            AlertRule(
                name="component_timeout_risk",
                condition=lambda report: any(
                    metric.response_time_ms and metric.response_time_ms > 5000 
                    for metric in report.metrics.values()
                ),
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=5
            ),
            
            # Database-specific alerts
            AlertRule(
                name="database_critical",
                condition=lambda report: (
                    'database_session' in report.metrics and 
                    report.metrics['database_session'].status == HealthStatus.CRITICAL
                ),
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK, AlertChannel.PAGERDUTY],
                cooldown_minutes=2,
                require_acknowledgement=True
            ),
            
            AlertRule(
                name="database_slow_queries",
                condition=lambda report: (
                    'database_session' in report.metrics and
                    report.metrics['database_session'].response_time_ms and
                    report.metrics['database_session'].response_time_ms > 3000
                ),
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=10
            ),
            
            # Rate limiter alerts
            AlertRule(
                name="rate_limiter_failure",
                condition=lambda report: (
                    'rate_limiter' in report.metrics and 
                    report.metrics['rate_limiter'].status in [HealthStatus.UNHEALTHY, HealthStatus.CRITICAL]
                ),
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=5
            ),
            
            # JWT service alerts
            AlertRule(
                name="jwt_service_failure",
                condition=lambda report: (
                    'jwt_service' in report.metrics and 
                    report.metrics['jwt_service'].status == HealthStatus.UNHEALTHY
                ),
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=5
            ),
            
            # Redis cache alerts
            AlertRule(
                name="redis_cache_failure",
                condition=lambda report: (
                    'redis_cache' in report.metrics and 
                    report.metrics['redis_cache'].status == HealthStatus.UNHEALTHY and
                    'redis_configured' in report.metrics['redis_cache'].details and
                    report.metrics['redis_cache'].details['redis_configured'] is not False
                ),
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=10
            ),
            
            # System resource alerts
            AlertRule(
                name="system_resources_critical",
                condition=lambda report: (
                    'system_performance' in report.metrics and 
                    report.metrics['system_performance'].status == HealthStatus.CRITICAL
                ),
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=5
            ),
            
            # Multiple components degraded
            AlertRule(
                name="multiple_components_degraded",
                condition=lambda report: sum(
                    1 for metric in report.metrics.values() 
                    if metric.status in [HealthStatus.DEGRADED, HealthStatus.CRITICAL, HealthStatus.UNHEALTHY]
                ) >= 3,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
                cooldown_minutes=10
            ),
            
            # Performance trend alerts
            AlertRule(
                name="performance_degradation_trend",
                condition=self._check_performance_trend,
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.EMAIL],
                cooldown_minutes=30
            )
        ]
    
    def _check_performance_trend(self, report: MiddlewareHealthReport) -> bool:
        """Check for performance degradation trend over time"""
        # This would require access to historical data
        # For now, return False - could be enhanced with trend analysis
        return False
    
    def _setup_notification_channels(self) -> Dict[AlertChannel, Dict[str, Any]]:
        """Setup notification channel configurations"""
        channels = {}
        
        # Email configuration
        if hasattr(settings, 'ALERT_EMAIL_SMTP_HOST'):
            channels[AlertChannel.EMAIL] = {
                'smtp_host': getattr(settings, 'ALERT_EMAIL_SMTP_HOST', 'localhost'),
                'smtp_port': getattr(settings, 'ALERT_EMAIL_SMTP_PORT', 587),
                'username': getattr(settings, 'ALERT_EMAIL_USERNAME', ''),
                'password': getattr(settings, 'ALERT_EMAIL_PASSWORD', ''),
                'from_email': getattr(settings, 'ALERT_EMAIL_FROM', 'alerts@mita.finance'),
                'to_emails': getattr(settings, 'ALERT_EMAIL_TO', 'ops@mita.finance').split(','),
                'use_tls': getattr(settings, 'ALERT_EMAIL_USE_TLS', True)
            }
        
        # Webhook configuration
        if hasattr(settings, 'ALERT_WEBHOOK_URL'):
            channels[AlertChannel.WEBHOOK] = {
                'url': settings.ALERT_WEBHOOK_URL,
                'headers': json.loads(getattr(settings, 'ALERT_WEBHOOK_HEADERS', '{}')),
                'timeout': getattr(settings, 'ALERT_WEBHOOK_TIMEOUT', 10)
            }
        
        # Slack configuration
        if hasattr(settings, 'ALERT_SLACK_WEBHOOK_URL'):
            channels[AlertChannel.SLACK] = {
                'webhook_url': settings.ALERT_SLACK_WEBHOOK_URL,
                'channel': getattr(settings, 'ALERT_SLACK_CHANNEL', '#ops-alerts'),
                'username': getattr(settings, 'ALERT_SLACK_USERNAME', 'MITA Health Monitor')
            }
        
        # PagerDuty configuration
        if hasattr(settings, 'ALERT_PAGERDUTY_ROUTING_KEY'):
            channels[AlertChannel.PAGERDUTY] = {
                'routing_key': settings.ALERT_PAGERDUTY_ROUTING_KEY,
                'api_url': 'https://events.pagerduty.com/v2/enqueue'
            }
        
        return channels
    
    async def process_health_report(self, health_report: MiddlewareHealthReport) -> List[Alert]:
        """Process health report and generate alerts based on rules"""
        triggered_alerts = []
        
        with self.lock:
            for rule in self.alert_rules:
                try:
                    # Check if rule condition is met
                    if rule.condition(health_report):
                        alert_id = f"{rule.name}_{int(time.time())}"
                        
                        # Check cooldown period
                        if self._is_in_cooldown(rule.name):
                            continue
                        
                        # Create alert
                        alert = Alert(
                            id=alert_id,
                            title=f"MITA Health Alert: {rule.name.replace('_', ' ').title()}",
                            message=self._generate_alert_message(rule, health_report),
                            severity=rule.severity,
                            component=self._extract_component_from_rule(rule.name),
                            timestamp=health_report.timestamp,
                            metadata={
                                'rule_name': rule.name,
                                'health_report_timestamp': health_report.timestamp.isoformat(),
                                'overall_status': health_report.overall_status.value,
                                'response_time_ms': health_report.response_time_ms,
                                'alerts_in_report': health_report.alerts,
                                'issues_detected': health_report.issues_detected
                            }
                        )
                        
                        # Store alert
                        self.active_alerts[alert_id] = alert
                        self.alert_history.append(alert)
                        triggered_alerts.append(alert)
                        
                        # Set cooldown
                        self.cooldown_tracker[rule.name] = datetime.utcnow() + timedelta(minutes=rule.cooldown_minutes)
                        
                        # Send notifications
                        await self._send_alert_notifications(alert, rule)
                        
                        logger.warning(f"Health alert triggered: {alert.title}")
                        
                except Exception as e:
                    logger.error(f"Error processing alert rule {rule.name}: {str(e)}")
            
            # Clean up old history
            if len(self.alert_history) > self.max_history_size:
                self.alert_history = self.alert_history[-self.max_history_size:]
        
        return triggered_alerts
    
    def _is_in_cooldown(self, rule_name: str) -> bool:
        """Check if alert rule is in cooldown period"""
        if rule_name not in self.cooldown_tracker:
            return False
        return datetime.utcnow() < self.cooldown_tracker[rule_name]
    
    def _generate_alert_message(self, rule: AlertRule, health_report: MiddlewareHealthReport) -> str:
        """Generate detailed alert message"""
        message_parts = [
            f"Alert: {rule.name.replace('_', ' ').title()}",
            f"Severity: {rule.severity.value.upper()}",
            f"Timestamp: {health_report.timestamp.isoformat()}",
            f"Overall System Status: {health_report.overall_status.value.upper()}",
            f"Health Check Duration: {health_report.response_time_ms:.1f}ms",
            ""
        ]
        
        # Add component-specific details
        if rule.name.startswith('database'):
            if 'database_session' in health_report.metrics:
                metric = health_report.metrics['database_session']
                message_parts.extend([
                    "Database Health Details:",
                    f"- Status: {metric.status.value}",
                    f"- Response Time: {metric.response_time_ms:.1f}ms",
                    f"- Message: {metric.message}"
                ])
        elif rule.name.startswith('rate_limiter'):
            if 'rate_limiter' in health_report.metrics:
                metric = health_report.metrics['rate_limiter']
                message_parts.extend([
                    "Rate Limiter Health Details:",
                    f"- Status: {metric.status.value}",
                    f"- Response Time: {metric.response_time_ms:.1f}ms",
                    f"- Message: {metric.message}"
                ])
        
        # Add general issues and recommendations
        if health_report.issues_detected:
            message_parts.extend([
                "",
                "Issues Detected:",
                *[f"- {issue}" for issue in health_report.issues_detected[:5]]
            ])
        
        if health_report.recommendations:
            message_parts.extend([
                "",
                "Recommendations:",
                *[f"- {rec}" for rec in health_report.recommendations[:3]]
            ])
        
        # Add alert-specific details
        if health_report.alerts:
            message_parts.extend([
                "",
                "System Alerts:",
                *[f"- {alert}" for alert in health_report.alerts[:5]]
            ])
        
        return "\n".join(message_parts)
    
    def _extract_component_from_rule(self, rule_name: str) -> str:
        """Extract component name from rule name"""
        if 'database' in rule_name:
            return 'database'
        elif 'rate_limiter' in rule_name:
            return 'rate_limiter'
        elif 'jwt' in rule_name:
            return 'jwt_service'
        elif 'redis' in rule_name:
            return 'redis_cache'
        elif 'system' in rule_name:
            return 'system_performance'
        else:
            return 'general'
    
    async def _send_alert_notifications(self, alert: Alert, rule: AlertRule):
        """Send alert notifications through configured channels"""
        for channel in rule.channels:
            try:
                if channel == AlertChannel.EMAIL:
                    await self._send_email_alert(alert)
                elif channel == AlertChannel.WEBHOOK:
                    await self._send_webhook_alert(alert)
                elif channel == AlertChannel.SLACK:
                    await self._send_slack_alert(alert)
                elif channel == AlertChannel.PAGERDUTY:
                    await self._send_pagerduty_alert(alert)
                elif channel == AlertChannel.LOG:
                    self._log_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send alert via {channel.value}: {str(e)}")
    
    async def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        if AlertChannel.EMAIL not in self.notification_channels:
            return
        
        config = self.notification_channels[AlertChannel.EMAIL]
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = config['from_email']
        msg['To'] = ', '.join(config['to_emails'])
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
        
        # Email body
        body = f"""
MITA Finance - Health Monitoring Alert

{alert.message}

Alert Details:
- ID: {alert.id}
- Component: {alert.component}
- Severity: {alert.severity.value.upper()}
- Timestamp: {alert.timestamp.isoformat()}

This is an automated alert from the MITA Health Monitoring System.
Please investigate and resolve the issue promptly.

Dashboard: https://mita.finance/admin/health
Support: support@mita.finance
        """

        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        try:
            server = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
            if config['use_tls']:
                server.starttls()
            if config['username']:
                server.login(config['username'], config['password'])
            server.send_message(msg)
            server.quit()
            logger.info(f"Email alert sent for {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
    
    async def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook"""
        if AlertChannel.WEBHOOK not in self.notification_channels:
            return
        
        config = self.notification_channels[AlertChannel.WEBHOOK]
        
        payload = {
            'alert_id': alert.id,
            'title': alert.title,
            'message': alert.message,
            'severity': alert.severity.value,
            'component': alert.component,
            'timestamp': alert.timestamp.isoformat(),
            'metadata': alert.metadata
        }
        
        try:
            response = requests.post(
                config['url'],
                json=payload,
                headers=config['headers'],
                timeout=config['timeout']
            )
            response.raise_for_status()
            logger.info(f"Webhook alert sent for {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {str(e)}")
    
    async def _send_slack_alert(self, alert: Alert):
        """Send alert via Slack"""
        if AlertChannel.SLACK not in self.notification_channels:
            return
        
        config = self.notification_channels[AlertChannel.SLACK]
        
        # Color coding based on severity
        color_map = {
            AlertSeverity.LOW: 'good',
            AlertSeverity.MEDIUM: 'warning',
            AlertSeverity.HIGH: 'danger',
            AlertSeverity.CRITICAL: 'danger'
        }
        
        payload = {
            'channel': config['channel'],
            'username': config['username'],
            'attachments': [{
                'color': color_map[alert.severity],
                'title': alert.title,
                'text': alert.message,
                'fields': [
                    {
                        'title': 'Severity',
                        'value': alert.severity.value.upper(),
                        'short': True
                    },
                    {
                        'title': 'Component',
                        'value': alert.component,
                        'short': True
                    },
                    {
                        'title': 'Alert ID',
                        'value': alert.id,
                        'short': True
                    }
                ],
                'ts': int(alert.timestamp.timestamp())
            }]
        }
        
        try:
            response = requests.post(config['webhook_url'], json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Slack alert sent for {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {str(e)}")
    
    async def _send_pagerduty_alert(self, alert: Alert):
        """Send alert via PagerDuty"""
        if AlertChannel.PAGERDUTY not in self.notification_channels:
            return
        
        config = self.notification_channels[AlertChannel.PAGERDUTY]
        
        payload = {
            'routing_key': config['routing_key'],
            'event_action': 'trigger',
            'dedup_key': f"mita-health-{alert.component}",
            'payload': {
                'summary': alert.title,
                'source': 'MITA Health Monitor',
                'severity': 'critical' if alert.severity == AlertSeverity.CRITICAL else 'error',
                'component': alert.component,
                'custom_details': {
                    'alert_id': alert.id,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat(),
                    'metadata': alert.metadata
                }
            }
        }
        
        try:
            response = requests.post(config['api_url'], json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"PagerDuty alert sent for {alert.id}")
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {str(e)}")
    
    def _log_alert(self, alert: Alert):
        """Log alert to application logs"""
        log_message = f"HEALTH ALERT [{alert.severity.value.upper()}] {alert.title}: {alert.message}"
        
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(log_message)
        elif alert.severity == AlertSeverity.HIGH:
            logger.error(log_message)
        elif alert.severity == AlertSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        with self.lock:
            return [alert for alert in self.active_alerts.values() if not alert.resolved]
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history"""
        with self.lock:
            return self.alert_history[-limit:] if limit else self.alert_history.copy()
    
    def acknowledge_alert(self, alert_id: str, acknowledger: str) -> bool:
        """Acknowledge an alert"""
        with self.lock:
            if alert_id in self.active_alerts:
                self.active_alerts[alert_id].acknowledgements.append(f"{acknowledger} at {datetime.utcnow().isoformat()}")
                logger.info(f"Alert {alert_id} acknowledged by {acknowledger}")
                return True
            return False
    
    def resolve_alert(self, alert_id: str, resolver: str) -> bool:
        """Resolve an alert"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                alert.acknowledgements.append(f"Resolved by {resolver} at {alert.resolved_at.isoformat()}")
                logger.info(f"Alert {alert_id} resolved by {resolver}")
                return True
            return False


# Global alert manager instance
health_alert_manager = HealthAlertManager()