"""
MITA Finance - Automated Secret Rotation System

This module provides automated secret rotation capabilities for the MITA financial application.
It ensures secrets are rotated according to compliance requirements and business policies.

Features:
- Scheduled rotation based on secret categories and policies
- Zero-downtime rotation with validation
- Emergency rotation procedures
- Rollback capabilities
- Integration with monitoring and alerting
- Compliance audit trails

Compliance: SOX, PCI DSS, GDPR
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.secret_manager import UnifiedSecretManager, SecretCategory, SecretRotationStatus

logger = logging.getLogger(__name__)


class RotationResult(Enum):
    """Result status for rotation operations"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLBACK_SUCCESS = "rollback_success"
    ROLLBACK_FAILED = "rollback_failed"


@dataclass
class RotationTask:
    """Task for secret rotation"""
    secret_name: str
    category: SecretCategory
    scheduled_time: datetime
    max_retries: int = 3
    retry_count: int = 0
    last_attempt: Optional[datetime] = None
    result: Optional[RotationResult] = None
    error_message: Optional[str] = None
    old_version: Optional[str] = None
    new_version: Optional[str] = None


@dataclass
class RotationPolicy:
    """Policy for secret rotation"""
    category: SecretCategory
    rotation_interval_days: int
    max_retries: int
    validation_timeout_seconds: int
    notification_recipients: List[str]
    requires_approval: bool
    emergency_contacts: List[str]


class SecretRotationManager:
    """
    Manages automated rotation of secrets according to policies and compliance requirements
    """
    
    def __init__(self, secret_manager: UnifiedSecretManager, config: Dict[str, Any]):
        """
        Initialize the rotation manager
        
        Args:
            secret_manager: UnifiedSecretManager instance
            config: Configuration for rotation policies and notifications
        """
        self.secret_manager = secret_manager
        self.config = config
        self.rotation_policies = self._load_rotation_policies()
        self.pending_tasks: List[RotationTask] = []
        self.completed_tasks: List[RotationTask] = []
        self.validation_functions: Dict[str, Callable] = {}
        
        # Notification settings
        self.smtp_config = config.get('smtp', {})
        self.slack_config = config.get('slack', {})
        self.pagerduty_config = config.get('pagerduty', {})
        
        logger.info("Secret rotation manager initialized")
    
    def _load_rotation_policies(self) -> Dict[SecretCategory, RotationPolicy]:
        """Load rotation policies from configuration"""
        policies = {}
        
        policy_configs = self.config.get('rotation_policies', {})
        
        # Default policies for each category
        default_policies = {
            SecretCategory.CRITICAL: RotationPolicy(
                category=SecretCategory.CRITICAL,
                rotation_interval_days=30,
                max_retries=3,
                validation_timeout_seconds=300,
                notification_recipients=['security@mita.finance', 'devops@mita.finance'],
                requires_approval=True,
                emergency_contacts=['cto@mita.finance', 'security@mita.finance']
            ),
            SecretCategory.HIGH: RotationPolicy(
                category=SecretCategory.HIGH,
                rotation_interval_days=60,
                max_retries=2,
                validation_timeout_seconds=180,
                notification_recipients=['devops@mita.finance'],
                requires_approval=False,
                emergency_contacts=['devops@mita.finance']
            ),
            SecretCategory.MEDIUM: RotationPolicy(
                category=SecretCategory.MEDIUM,
                rotation_interval_days=120,
                max_retries=2,
                validation_timeout_seconds=120,
                notification_recipients=['devops@mita.finance'],
                requires_approval=False,
                emergency_contacts=['devops@mita.finance']
            ),
            SecretCategory.LOW: RotationPolicy(
                category=SecretCategory.LOW,
                rotation_interval_days=180,
                max_retries=1,
                validation_timeout_seconds=60,
                notification_recipients=['devops@mita.finance'],
                requires_approval=False,
                emergency_contacts=['devops@mita.finance']
            )
        }
        
        # Override with config values
        for category, default_policy in default_policies.items():
            category_config = policy_configs.get(category.value, {})
            
            policies[category] = RotationPolicy(
                category=category,
                rotation_interval_days=category_config.get('rotation_interval_days', default_policy.rotation_interval_days),
                max_retries=category_config.get('max_retries', default_policy.max_retries),
                validation_timeout_seconds=category_config.get('validation_timeout_seconds', default_policy.validation_timeout_seconds),
                notification_recipients=category_config.get('notification_recipients', default_policy.notification_recipients),
                requires_approval=category_config.get('requires_approval', default_policy.requires_approval),
                emergency_contacts=category_config.get('emergency_contacts', default_policy.emergency_contacts)
            )
        
        return policies
    
    def register_validation_function(self, secret_name: str, validation_func: Callable[[str], bool]):
        """
        Register a validation function for a specific secret
        
        Args:
            secret_name: Name of the secret
            validation_func: Function that validates the new secret value
        """
        self.validation_functions[secret_name] = validation_func
        logger.info(f"Registered validation function for secret: {secret_name}")
    
    async def schedule_rotation(self, secret_name: str, force: bool = False) -> RotationTask:
        """
        Schedule a secret for rotation
        
        Args:
            secret_name: Name of the secret to rotate
            force: Force immediate rotation regardless of schedule
            
        Returns:
            RotationTask object
        """
        # Get secret metadata
        secret_metadata = self.secret_manager.secret_definitions.get(secret_name)
        if not secret_metadata:
            raise ValueError(f"Secret not found: {secret_name}")
        
        policy = self.rotation_policies.get(secret_metadata.category)
        if not policy:
            raise ValueError(f"No rotation policy found for category: {secret_metadata.category}")
        
        # Calculate scheduled time
        if force:
            scheduled_time = datetime.utcnow()
        else:
            last_rotation = secret_metadata.created_at
            scheduled_time = last_rotation + timedelta(days=policy.rotation_interval_days)
        
        # Create rotation task
        task = RotationTask(
            secret_name=secret_name,
            category=secret_metadata.category,
            scheduled_time=scheduled_time,
            max_retries=policy.max_retries
        )
        
        self.pending_tasks.append(task)
        
        logger.info(f"Scheduled rotation for {secret_name} at {scheduled_time}")
        return task
    
    async def execute_rotation(self, task: RotationTask) -> RotationResult:
        """
        Execute a rotation task
        
        Args:
            task: RotationTask to execute
            
        Returns:
            RotationResult indicating success or failure
        """
        logger.info(f"Starting rotation for secret: {task.secret_name}")
        
        try:
            # Update task status
            task.last_attempt = datetime.utcnow()
            task.retry_count += 1
            
            # Get current secret value for rollback
            current_secret = await self.secret_manager.get_secret(task.secret_name)
            task.old_version = current_secret.metadata.version
            
            # Check if approval is required
            policy = self.rotation_policies[task.category]
            if policy.requires_approval and not await self._check_approval(task):
                logger.info(f"Rotation approval pending for {task.secret_name}")
                task.result = RotationResult.SKIPPED
                return RotationResult.SKIPPED
            
            # Send pre-rotation notification
            await self._send_notification(
                'rotation_start',
                f"Starting rotation for {task.secret_name}",
                policy.notification_recipients,
                {'task': asdict(task)}
            )
            
            # Perform the rotation
            new_secret_value = await self.secret_manager.rotate_secret(task.secret_name, force=True)
            
            # Get new version
            updated_secret = await self.secret_manager.get_secret(task.secret_name)
            task.new_version = updated_secret.metadata.version
            
            # Validate the new secret
            if await self._validate_secret(task.secret_name, new_secret_value, policy.validation_timeout_seconds):
                task.result = RotationResult.SUCCESS
                
                # Send success notification
                await self._send_notification(
                    'rotation_success',
                    f"Successfully rotated {task.secret_name}",
                    policy.notification_recipients,
                    {
                        'task': asdict(task),
                        'old_version': task.old_version,
                        'new_version': task.new_version
                    }
                )
                
                logger.info(f"Successfully rotated secret: {task.secret_name}")
                return RotationResult.SUCCESS
            else:
                # Validation failed, attempt rollback
                logger.error(f"Validation failed for rotated secret: {task.secret_name}")
                rollback_result = await self._rollback_secret(task)
                
                if rollback_result:
                    task.result = RotationResult.ROLLBACK_SUCCESS
                    return RotationResult.ROLLBACK_SUCCESS
                else:
                    task.result = RotationResult.ROLLBACK_FAILED
                    return RotationResult.ROLLBACK_FAILED
            
        except Exception as e:
            error_message = f"Rotation failed for {task.secret_name}: {e}"
            logger.error(error_message)
            task.error_message = str(e)
            task.result = RotationResult.FAILED
            
            # Send failure notification
            policy = self.rotation_policies[task.category]
            await self._send_notification(
                'rotation_failure',
                error_message,
                policy.emergency_contacts,
                {'task': asdict(task), 'error': str(e)}
            )
            
            return RotationResult.FAILED
    
    async def _validate_secret(self, secret_name: str, secret_value: str, timeout_seconds: int) -> bool:
        """
        Validate a newly rotated secret
        
        Args:
            secret_name: Name of the secret
            secret_value: New secret value
            timeout_seconds: Validation timeout
            
        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Check if custom validation function exists
            if secret_name in self.validation_functions:
                validation_func = self.validation_functions[secret_name]
                
                # Run validation with timeout
                result = await asyncio.wait_for(
                    asyncio.create_task(self._run_validation(validation_func, secret_value)),
                    timeout=timeout_seconds
                )
                
                return result
            else:
                # Default validation - basic format checks
                return await self._default_validation(secret_name, secret_value)
                
        except asyncio.TimeoutError:
            logger.error(f"Validation timeout for secret: {secret_name}")
            return False
        except Exception as e:
            logger.error(f"Validation error for secret {secret_name}: {e}")
            return False
    
    async def _run_validation(self, validation_func: Callable, secret_value: str) -> bool:
        """Run validation function in a separate task"""
        try:
            if asyncio.iscoroutinefunction(validation_func):
                return await validation_func(secret_value)
            else:
                return validation_func(secret_value)
        except Exception as e:
            logger.error(f"Validation function failed: {e}")
            return False
    
    async def _default_validation(self, secret_name: str, secret_value: str) -> bool:
        """
        Default validation for secrets
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value to validate
            
        Returns:
            True if validation passes
        """
        # Basic validation rules
        if not secret_value or len(secret_value) < 8:
            return False
        
        # Secret-specific validation
        if 'jwt' in secret_name.lower() or 'token' in secret_name.lower():
            # JWT secrets should be at least 32 characters
            return len(secret_value) >= 32
        
        elif 'password' in secret_name.lower():
            # Passwords should meet complexity requirements
            return (len(secret_value) >= 12 and
                    any(c.isupper() for c in secret_value) and
                    any(c.islower() for c in secret_value) and
                    any(c.isdigit() for c in secret_value))
        
        elif 'key' in secret_name.lower():
            # API keys should have specific format or length
            return len(secret_value) >= 16
        
        elif secret_name.lower() == 'database_url':
            # Database URLs should have proper format
            return any(secret_value.startswith(proto) for proto in ['postgresql://', 'postgres://'])
        
        elif secret_name.lower() == 'redis_url':
            # Redis URLs should have proper format
            return secret_value.startswith('redis://')
        
        # Default: just check minimum length
        return len(secret_value) >= 16
    
    async def _rollback_secret(self, task: RotationTask) -> bool:
        """
        Rollback a secret to its previous version
        
        Args:
            task: RotationTask to rollback
            
        Returns:
            True if rollback successful
        """
        try:
            logger.info(f"Attempting rollback for secret: {task.secret_name}")
            
            if not task.old_version:
                logger.error(f"No previous version available for rollback: {task.secret_name}")
                return False
            
            # Attempt to retrieve and restore the previous version
            # This would need to be implemented based on the specific provider
            # For now, we'll mark it as a manual intervention required
            
            await self._send_notification(
                'rollback_required',
                f"Manual rollback required for {task.secret_name}",
                self.rotation_policies[task.category].emergency_contacts,
                {
                    'task': asdict(task),
                    'old_version': task.old_version,
                    'new_version': task.new_version
                }
            )
            
            return False  # Indicate manual intervention required
            
        except Exception as e:
            logger.error(f"Rollback failed for {task.secret_name}: {e}")
            return False
    
    async def _check_approval(self, task: RotationTask) -> bool:
        """
        Check if rotation has been approved
        
        Args:
            task: RotationTask to check approval for
            
        Returns:
            True if approved or no approval required
        """
        # For now, assume approval is always granted
        # In a real implementation, this would check an approval system
        return True
    
    async def _send_notification(self, event_type: str, message: str, recipients: List[str], context: Dict[str, Any]):
        """
        Send notification about rotation events
        
        Args:
            event_type: Type of event (rotation_start, rotation_success, etc.)
            message: Notification message
            recipients: List of email recipients
            context: Additional context data
        """
        try:
            # Email notification
            if self.smtp_config and recipients:
                await self._send_email_notification(event_type, message, recipients, context)
            
            # Slack notification (if configured)
            if self.slack_config:
                await self._send_slack_notification(event_type, message, context)
            
            # PagerDuty alert (for critical events)
            if (self.pagerduty_config and 
                event_type in ['rotation_failure', 'rollback_required'] and 
                context.get('task', {}).get('category') == 'critical'):
                await self._send_pagerduty_alert(event_type, message, context)
                
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    async def _send_email_notification(self, event_type: str, message: str, recipients: List[str], context: Dict[str, Any]):
        """Send email notification"""
        try:
            smtp_host = self.smtp_config.get('host', 'localhost')
            smtp_port = self.smtp_config.get('port', 587)
            smtp_username = self.smtp_config.get('username')
            smtp_password = self.smtp_config.get('password')
            from_address = self.smtp_config.get('from', 'noreply@mita.finance')
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_address
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"MITA Secret Rotation: {event_type.title()}"
            
            # Email body
            body = f"""
MITA Finance - Secret Rotation Notification

Event: {event_type.title()}
Message: {message}
Timestamp: {datetime.utcnow().isoformat()}

Details:
{json.dumps(context, indent=2, default=str)}

This is an automated notification from the MITA secret rotation system.
Please do not reply to this email.

Best regards,
MITA DevOps Team
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            if smtp_username and smtp_password:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
                server.quit()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.send_message(msg)
                server.quit()
            
            logger.info(f"Email notification sent for {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    async def _send_slack_notification(self, event_type: str, message: str, context: Dict[str, Any]):
        """Send Slack notification"""
        # Implementation would depend on Slack API integration
        logger.info(f"Slack notification would be sent for {event_type}: {message}")
    
    async def _send_pagerduty_alert(self, event_type: str, message: str, context: Dict[str, Any]):
        """Send PagerDuty alert"""
        # Implementation would depend on PagerDuty API integration
        logger.info(f"PagerDuty alert would be sent for {event_type}: {message}")
    
    async def run_scheduled_rotations(self):
        """
        Run all scheduled rotations that are due
        """
        logger.info("Running scheduled secret rotations")
        
        current_time = datetime.utcnow()
        due_tasks = [task for task in self.pending_tasks if task.scheduled_time <= current_time]
        
        results = {
            RotationResult.SUCCESS: 0,
            RotationResult.FAILED: 0,
            RotationResult.SKIPPED: 0,
            RotationResult.ROLLBACK_SUCCESS: 0,
            RotationResult.ROLLBACK_FAILED: 0
        }
        
        for task in due_tasks:
            if task.retry_count >= task.max_retries:
                logger.warning(f"Max retries exceeded for {task.secret_name}")
                task.result = RotationResult.FAILED
                self.completed_tasks.append(task)
                self.pending_tasks.remove(task)
                continue
            
            result = await self.execute_rotation(task)
            results[result] += 1
            
            if result in [RotationResult.SUCCESS, RotationResult.ROLLBACK_SUCCESS]:
                self.completed_tasks.append(task)
                self.pending_tasks.remove(task)
            elif result == RotationResult.FAILED and task.retry_count >= task.max_retries:
                self.completed_tasks.append(task)
                self.pending_tasks.remove(task)
        
        # Log summary
        logger.info(f"Rotation summary: {dict(results)}")
        
        return results
    
    async def emergency_rotate_all(self, reason: str, categories: Optional[List[SecretCategory]] = None) -> Dict[str, RotationResult]:
        """
        Emergency rotation of secrets
        
        Args:
            reason: Reason for emergency rotation
            categories: Specific categories to rotate (default: CRITICAL and HIGH)
            
        Returns:
            Dictionary of secret names and their rotation results
        """
        if categories is None:
            categories = [SecretCategory.CRITICAL, SecretCategory.HIGH]
        
        logger.critical(f"Emergency rotation initiated: {reason}")
        
        results = {}
        
        # Get all secrets in the specified categories
        emergency_secrets = [
            name for name, metadata in self.secret_manager.secret_definitions.items()
            if metadata.category in categories
        ]
        
        for secret_name in emergency_secrets:
            try:
                task = await self.schedule_rotation(secret_name, force=True)
                result = await self.execute_rotation(task)
                results[secret_name] = result
                
                if result != RotationResult.SUCCESS:
                    logger.error(f"Emergency rotation failed for {secret_name}: {result}")
                
            except Exception as e:
                logger.error(f"Emergency rotation error for {secret_name}: {e}")
                results[secret_name] = RotationResult.FAILED
        
        # Send emergency notification
        await self._send_notification(
            'emergency_rotation_complete',
            f"Emergency rotation completed: {reason}",
            ['security@mita.finance', 'cto@mita.finance'],
            {'reason': reason, 'results': {k: v.value for k, v in results.items()}}
        )
        
        return results
    
    async def get_rotation_status(self) -> Dict[str, Any]:
        """
        Get status of all rotation tasks
        
        Returns:
            Status information
        """
        return {
            'pending_tasks': len(self.pending_tasks),
            'completed_tasks': len(self.completed_tasks),
            'next_rotation': min(
                [task.scheduled_time for task in self.pending_tasks],
                default=None
            ),
            'recent_failures': [
                task.secret_name for task in self.completed_tasks[-10:]
                if task.result == RotationResult.FAILED
            ],
            'policies': {
                category.value: {
                    'interval_days': policy.rotation_interval_days,
                    'max_retries': policy.max_retries
                }
                for category, policy in self.rotation_policies.items()
            }
        }


# Factory function
def create_rotation_manager(secret_manager: UnifiedSecretManager, config_path: Optional[str] = None) -> SecretRotationManager:
    """
    Create a secret rotation manager
    
    Args:
        secret_manager: UnifiedSecretManager instance
        config_path: Path to rotation configuration
        
    Returns:
        SecretRotationManager instance
    """
    # Load configuration
    if config_path:
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        # Default configuration
        config = {
            'smtp': {
                'host': 'smtp.sendgrid.net',
                'port': 587,
                'from': 'noreply@mita.finance'
            },
            'rotation_policies': {}
        }
    
    return SecretRotationManager(secret_manager, config)