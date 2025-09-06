"""
MITA Finance Email Service - Enterprise-grade Email Management
Comprehensive email service with SendGrid integration, templates, and monitoring
"""

import os
import json
import logging
import asyncio
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

import httpx
import jinja2
import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.config import settings
from app.core.external_services import SendGridService
# Removed problematic import - using sentry_sdk.capture_exception directly
from app.core.audit_logging import log_security_event_async
from app.db.models.user import User
from app.db.models.notification_log import NotificationLog

logger = logging.getLogger(__name__)


class EmailType(Enum):
    """Email types for template selection and tracking"""
    WELCOME = "welcome"
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    SECURITY_ALERT = "security_alert"
    TRANSACTION_CONFIRMATION = "transaction_confirmation"
    BUDGET_ALERT = "budget_alert"
    ACCOUNT_LOCKED = "account_locked"
    PAYMENT_SUCCESS = "payment_success"
    SUBSCRIPTION_EXPIRY = "subscription_expiry"
    COMPLIANCE_UPDATE = "compliance_update"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_EXPORT = "data_export"
    ACCOUNT_DELETION = "account_deletion"
    TWO_FACTOR_CODE = "two_factor_code"


class EmailPriority(Enum):
    """Email priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EmailStatus(Enum):
    """Email delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"
    OPENED = "opened"
    CLICKED = "clicked"


@dataclass
class EmailTemplate:
    """Email template configuration"""
    name: str
    subject: str
    template_path: str
    template_type: str = "html"
    required_vars: List[str] = None
    optional_vars: List[str] = None
    sender_name: str = "MITA Finance"
    sender_email: str = "noreply@mita.finance"


@dataclass
class EmailDeliveryResult:
    """Email delivery result"""
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    provider: str = "sendgrid"
    sent_at: Optional[datetime] = None
    status: EmailStatus = EmailStatus.PENDING


@dataclass
class EmailMetrics:
    """Email service metrics"""
    total_sent: int = 0
    total_delivered: int = 0
    total_bounced: int = 0
    total_failed: int = 0
    success_rate: float = 0.0
    bounce_rate: float = 0.0
    last_updated: Optional[datetime] = None


class PasswordResetTokenManager:
    """Secure password reset token management"""
    
    TOKEN_EXPIRY_HOURS = 2  # Security best practice: short expiry
    MAX_ATTEMPTS = 3
    
    @staticmethod
    def generate_reset_token(user_id: str) -> Tuple[str, str]:
        """Generate secure password reset token and hash"""
        # Generate cryptographically secure token
        token = secrets.token_urlsafe(32)
        
        # Create token hash for database storage
        token_data = f"{user_id}:{token}:{datetime.now(timezone.utc).timestamp()}"
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()
        
        return token, token_hash
    
    @staticmethod
    def verify_reset_token(token: str, token_hash: str, user_id: str) -> bool:
        """Verify password reset token"""
        try:
            # Reconstruct expected hash
            token_data = f"{user_id}:{token}:{datetime.now(timezone.utc).timestamp()}"
            expected_hash = hashlib.sha256(token_data.encode()).hexdigest()
            
            # Use constant-time comparison for security
            return secrets.compare_digest(token_hash, expected_hash)
        except Exception:
            return False


class EmailTemplateManager:
    """Email template management with Jinja2"""
    
    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "templates" / "emails"
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure Jinja2 environment
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.template_dir)),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Initialize templates
        self.templates = self._initialize_templates()
        logger.info(f"Email template manager initialized with {len(self.templates)} templates")
    
    def _initialize_templates(self) -> Dict[EmailType, EmailTemplate]:
        """Initialize email templates configuration"""
        return {
            EmailType.WELCOME: EmailTemplate(
                name="Welcome to MITA Finance",
                subject="Welcome to MITA Finance - Your Financial Journey Starts Here",
                template_path="welcome.html",
                required_vars=["user_name", "email"],
                optional_vars=["onboarding_link", "support_email"]
            ),
            EmailType.EMAIL_VERIFICATION: EmailTemplate(
                name="Verify Your Email Address",
                subject="Verify Your MITA Finance Account",
                template_path="email_verification.html",
                required_vars=["user_name", "verification_link", "verification_code"],
                optional_vars=["expires_at"]
            ),
            EmailType.PASSWORD_RESET: EmailTemplate(
                name="Password Reset",
                subject="Reset Your MITA Finance Password",
                template_path="password_reset.html",
                required_vars=["user_name", "reset_link", "expires_at"],
                optional_vars=["support_email", "security_tips"]
            ),
            EmailType.SECURITY_ALERT: EmailTemplate(
                name="Security Alert",
                subject="URGENT: Security Alert for Your MITA Finance Account",
                template_path="security_alert.html",
                required_vars=["user_name", "alert_type", "alert_details", "timestamp"],
                optional_vars=["action_taken", "recommended_actions"]
            ),
            EmailType.TRANSACTION_CONFIRMATION: EmailTemplate(
                name="Transaction Confirmation",
                subject="Transaction Confirmation - MITA Finance",
                template_path="transaction_confirmation.html",
                required_vars=["user_name", "transaction_amount", "transaction_date", "description"],
                optional_vars=["transaction_id", "balance", "category"]
            ),
            EmailType.BUDGET_ALERT: EmailTemplate(
                name="Budget Alert",
                subject="Budget Alert - MITA Finance",
                template_path="budget_alert.html",
                required_vars=["user_name", "budget_category", "spent_amount", "budget_limit"],
                optional_vars=["percentage_used", "recommendations"]
            ),
            EmailType.SUSPICIOUS_ACTIVITY: EmailTemplate(
                name="Suspicious Activity Detected",
                subject="URGENT: Suspicious Activity Detected",
                template_path="suspicious_activity.html",
                required_vars=["user_name", "activity_description", "timestamp", "location"],
                optional_vars=["ip_address", "device_info"]
            ),
        }
    
    def get_template(self, email_type: EmailType) -> Optional[EmailTemplate]:
        """Get email template by type"""
        return self.templates.get(email_type)
    
    def render_template(self, email_type: EmailType, variables: Dict[str, Any]) -> Tuple[str, str]:
        """Render email template with variables"""
        template_config = self.get_template(email_type)
        if not template_config:
            raise ValueError(f"Template not found for email type: {email_type}")
        
        # Validate required variables
        missing_vars = []
        if template_config.required_vars:
            missing_vars = [var for var in template_config.required_vars if var not in variables]
        
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")
        
        try:
            # Add common variables
            variables.update({
                'current_year': datetime.now().year,
                'company_name': 'MITA Finance',
                'support_email': 'support@mita.finance',
                'unsubscribe_link': variables.get('unsubscribe_link', '#'),
                'privacy_policy_link': 'https://mita.finance/privacy',
                'terms_of_service_link': 'https://mita.finance/terms'
            })
            
            # Render template
            template = self.env.get_template(template_config.template_path)
            html_content = template.render(**variables)
            
            return template_config.subject, html_content
            
        except Exception as e:
            logger.error(f"Template rendering failed for {email_type}: {str(e)}")
            raise


class EmailService:
    """Enterprise email service with SendGrid integration"""
    
    def __init__(self):
        self.sendgrid = SendGridService()
        self.template_manager = EmailTemplateManager()
        self.metrics = EmailMetrics()
        
        # Email queue for retry mechanism
        self.email_queue = asyncio.Queue()
        self.retry_queue = asyncio.Queue()
        
        # Configuration
        self.max_retries = int(os.getenv('EMAIL_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('EMAIL_RETRY_DELAY', '300'))  # 5 minutes
        self.batch_size = int(os.getenv('EMAIL_BATCH_SIZE', '100'))
        
        logger.info("Email service initialized")
    
    async def send_email(
        self,
        to_email: str,
        email_type: EmailType,
        variables: Dict[str, Any],
        priority: EmailPriority = EmailPriority.NORMAL,
        user_id: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> EmailDeliveryResult:
        """Send email with template rendering and delivery tracking"""
        
        try:
            # Validate email address
            if not self._validate_email(to_email):
                return EmailDeliveryResult(
                    success=False,
                    error_message="Invalid email address format",
                    status=EmailStatus.FAILED
                )
            
            # Render template
            subject, html_content = self.template_manager.render_template(email_type, variables)
            
            # Send via SendGrid
            result = await self._send_via_sendgrid(to_email, subject, html_content)
            
            # Log email delivery
            if db and user_id:
                await self._log_email_delivery(
                    db, user_id, to_email, email_type, result
                )
            
            # Update metrics
            self._update_metrics(result.success)
            
            # Log security events for sensitive email types
            if email_type in [EmailType.PASSWORD_RESET, EmailType.SECURITY_ALERT, EmailType.SUSPICIOUS_ACTIVITY]:
                try:
                    await log_security_event_async(
                        event_type=f"email_sent_{email_type.value}",
                        user_id=user_id,
                        request=None,
                        details={
                            "email_type": email_type.value,
                            "to_email_hash": hashlib.sha256(to_email.encode()).hexdigest()[:12],
                            "success": result.success
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to log security event: {e}")
            
            return result
            
        except Exception as e:
            error_msg = f"Email sending failed: {str(e)}"
            logger.error(error_msg)
            
            # Capture exception to Sentry
            try:
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
            
            return EmailDeliveryResult(
                success=False,
                error_message=error_msg,
                status=EmailStatus.FAILED
            )
    
    async def _send_via_sendgrid(self, to_email: str, subject: str, html_content: str) -> EmailDeliveryResult:
        """Send email via SendGrid API"""
        
        if not self.sendgrid.enabled:
            return EmailDeliveryResult(
                success=False,
                error_message="SendGrid not configured",
                status=EmailStatus.FAILED
            )
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.sendgrid.api_key}',
                    'Content-Type': 'application/json'
                }
                
                # Generate plain text version
                plain_text = self._html_to_text(html_content)
                
                data = {
                    "personalizations": [{
                        "to": [{"email": to_email}],
                        "subject": subject
                    }],
                    "from": {
                        "email": self.sendgrid.from_email,
                        "name": self.sendgrid.from_name
                    },
                    "content": [
                        {
                            "type": "text/plain",
                            "value": plain_text
                        },
                        {
                            "type": "text/html",
                            "value": html_content
                        }
                    ],
                    "tracking_settings": {
                        "click_tracking": {"enable": True},
                        "open_tracking": {"enable": True},
                        "subscription_tracking": {"enable": True}
                    },
                    "reply_to": {
                        "email": "support@mita.finance",
                        "name": "MITA Finance Support"
                    }
                }
                
                response = await client.post(
                    'https://api.sendgrid.com/v3/mail/send',
                    headers=headers,
                    json=data
                )
                
                if response.status_code == 202:
                    message_id = response.headers.get('X-Message-Id', 'unknown')
                    return EmailDeliveryResult(
                        success=True,
                        message_id=message_id,
                        provider="sendgrid",
                        sent_at=datetime.now(timezone.utc),
                        status=EmailStatus.SENT
                    )
                else:
                    error_details = response.text
                    return EmailDeliveryResult(
                        success=False,
                        error_message=f"SendGrid API error: {response.status_code} - {error_details}",
                        status=EmailStatus.FAILED
                    )
                    
        except Exception as e:
            return EmailDeliveryResult(
                success=False,
                error_message=f"SendGrid request failed: {str(e)}",
                status=EmailStatus.FAILED
            )
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text(separator='\n', strip=True)
        except ImportError:
            # Fallback: simple HTML tag removal
            import re
            text = re.sub(r'<[^>]+>', '', html_content)
            return text.strip()
    
    def _validate_email(self, email: str) -> bool:
        """Validate email address format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    async def _log_email_delivery(
        self,
        db: AsyncSession,
        user_id: str,
        to_email: str,
        email_type: EmailType,
        result: EmailDeliveryResult
    ):
        """Log email delivery to database"""
        try:
            notification_log = NotificationLog(
                user_id=user_id,
                channel="email",
                message=f"{email_type.value} email",
                success=result.success,
                details={
                    "email_type": email_type.value,
                    "to_email": to_email,
                    "message_id": result.message_id,
                    "provider": result.provider,
                    "error": result.error_message
                }
            )
            
            db.add(notification_log)
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log email delivery: {e}")
    
    def _update_metrics(self, success: bool):
        """Update email service metrics"""
        if success:
            self.metrics.total_sent += 1
            self.metrics.total_delivered += 1
        else:
            self.metrics.total_failed += 1
        
        total_attempts = self.metrics.total_sent + self.metrics.total_failed
        if total_attempts > 0:
            self.metrics.success_rate = self.metrics.total_delivered / total_attempts
        
        self.metrics.last_updated = datetime.now(timezone.utc)
    
    async def send_welcome_email(self, user: User, db: AsyncSession) -> EmailDeliveryResult:
        """Send welcome email to new user"""
        variables = {
            'user_name': user.email.split('@')[0].title(),
            'email': user.email,
            'onboarding_link': f"https://app.mita.finance/onboarding",
            'support_email': 'support@mita.finance'
        }
        
        return await self.send_email(
            to_email=user.email,
            email_type=EmailType.WELCOME,
            variables=variables,
            priority=EmailPriority.NORMAL,
            user_id=str(user.id),
            db=db
        )
    
    async def send_password_reset_email(
        self,
        user: User,
        reset_token: str,
        db: AsyncSession
    ) -> EmailDeliveryResult:
        """Send password reset email"""
        
        # Create secure reset link
        reset_link = f"https://app.mita.finance/reset-password?token={reset_token}&email={user.email}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=PasswordResetTokenManager.TOKEN_EXPIRY_HOURS)
        
        variables = {
            'user_name': user.email.split('@')[0].title(),
            'reset_link': reset_link,
            'expires_at': expires_at.strftime('%B %d, %Y at %I:%M %p UTC'),
            'support_email': 'support@mita.finance',
            'security_tips': [
                'Never share your password with anyone',
                'Use a unique password for your MITA Finance account',
                'Enable two-factor authentication if available'
            ]
        }
        
        return await self.send_email(
            to_email=user.email,
            email_type=EmailType.PASSWORD_RESET,
            variables=variables,
            priority=EmailPriority.HIGH,
            user_id=str(user.id),
            db=db
        )
    
    async def send_security_alert(
        self,
        user: User,
        alert_type: str,
        alert_details: str,
        db: AsyncSession,
        additional_context: Dict[str, Any] = None
    ) -> EmailDeliveryResult:
        """Send security alert email"""
        
        variables = {
            'user_name': user.email.split('@')[0].title(),
            'alert_type': alert_type,
            'alert_details': alert_details,
            'timestamp': datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p UTC'),
            'action_taken': additional_context.get('action_taken') if additional_context else None,
            'recommended_actions': additional_context.get('recommended_actions') if additional_context else [
                'Change your password immediately',
                'Review recent account activity',
                'Contact support if you did not initiate this action'
            ]
        }
        
        return await self.send_email(
            to_email=user.email,
            email_type=EmailType.SECURITY_ALERT,
            variables=variables,
            priority=EmailPriority.URGENT,
            user_id=str(user.id),
            db=db
        )
    
    async def send_transaction_confirmation(
        self,
        user: User,
        transaction_details: Dict[str, Any],
        db: AsyncSession
    ) -> EmailDeliveryResult:
        """Send transaction confirmation email"""
        
        variables = {
            'user_name': user.email.split('@')[0].title(),
            'transaction_amount': f"${transaction_details['amount']:,.2f}",
            'transaction_date': transaction_details['date'],
            'description': transaction_details['description'],
            'transaction_id': transaction_details.get('id'),
            'balance': transaction_details.get('balance'),
            'category': transaction_details.get('category')
        }
        
        return await self.send_email(
            to_email=user.email,
            email_type=EmailType.TRANSACTION_CONFIRMATION,
            variables=variables,
            priority=EmailPriority.NORMAL,
            user_id=str(user.id),
            db=db
        )
    
    async def send_budget_alert(
        self,
        user: User,
        budget_details: Dict[str, Any],
        db: AsyncSession
    ) -> EmailDeliveryResult:
        """Send budget alert email"""
        
        percentage_used = (budget_details['spent_amount'] / budget_details['budget_limit']) * 100
        
        variables = {
            'user_name': user.email.split('@')[0].title(),
            'budget_category': budget_details['category'],
            'spent_amount': f"${budget_details['spent_amount']:,.2f}",
            'budget_limit': f"${budget_details['budget_limit']:,.2f}",
            'percentage_used': f"{percentage_used:.1f}%",
            'recommendations': budget_details.get('recommendations', [
                'Review your spending in this category',
                'Consider adjusting your budget if needed',
                'Look for ways to reduce expenses'
            ])
        }
        
        return await self.send_email(
            to_email=user.email,
            email_type=EmailType.BUDGET_ALERT,
            variables=variables,
            priority=EmailPriority.HIGH,
            user_id=str(user.id),
            db=db
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get email service metrics"""
        return asdict(self.metrics)
    
    async def validate_service_health(self) -> Dict[str, Any]:
        """Validate email service health"""
        health_status = {
            'service': 'email',
            'status': 'unknown',
            'checks': {},
            'metrics': self.get_metrics()
        }
        
        # Check SendGrid connectivity
        sendgrid_healthy = await self.sendgrid.validate_connection()
        health_status['checks']['sendgrid'] = {
            'status': 'healthy' if sendgrid_healthy else 'unhealthy',
            'enabled': self.sendgrid.enabled
        }
        
        # Check template availability
        templates_available = len(self.template_manager.templates) > 0
        health_status['checks']['templates'] = {
            'status': 'healthy' if templates_available else 'unhealthy',
            'count': len(self.template_manager.templates)
        }
        
        # Determine overall health
        all_checks_healthy = all(
            check['status'] == 'healthy'
            for check in health_status['checks'].values()
        )
        health_status['status'] = 'healthy' if all_checks_healthy else 'degraded'
        
        return health_status


# Global email service instance
email_service = EmailService()


async def get_email_service() -> EmailService:
    """Get email service instance"""
    return email_service


# Convenience functions for common email operations
async def send_welcome_email(user: User, db: AsyncSession) -> EmailDeliveryResult:
    """Send welcome email"""
    return await email_service.send_welcome_email(user, db)


async def send_password_reset_email(user: User, reset_token: str, db: AsyncSession) -> EmailDeliveryResult:
    """Send password reset email"""
    return await email_service.send_password_reset_email(user, reset_token, db)


async def send_security_alert_email(
    user: User,
    alert_type: str,
    alert_details: str,
    db: AsyncSession,
    additional_context: Dict[str, Any] = None
) -> EmailDeliveryResult:
    """Send security alert email"""
    return await email_service.send_security_alert(user, alert_type, alert_details, db, additional_context)