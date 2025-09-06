"""
Mobile App Email Integration Service
Handles email-triggered actions, deep links, and mobile-specific email features
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from app.services.email_service import EmailType, EmailPriority
from app.services.email_queue_service import queue_email

logger = logging.getLogger(__name__)


class DeepLinkAction(Enum):
    """Mobile app deep link actions"""
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    TRANSACTION_REVIEW = "transaction_review"
    BUDGET_ALERT = "budget_alert"
    SECURITY_ALERT = "security_alert"
    ACCOUNT_SETUP = "account_setup"
    GOAL_PROGRESS = "goal_progress"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    SUPPORT_TICKET = "support_ticket"


@dataclass
class DeepLinkConfig:
    """Deep link configuration"""
    scheme: str = "mita"
    host: str = "app.mita.finance"
    web_fallback: str = "https://app.mita.finance"


class MobileEmailIntegration:
    """Mobile app email integration service"""
    
    def __init__(self):
        self.deep_link_config = DeepLinkConfig()
        
        # Mobile app configuration
        self.ios_app_id = os.getenv('IOS_APP_ID', '12345678')
        self.android_package_name = os.getenv('ANDROID_PACKAGE_NAME', 'com.mita.finance')
        
        # Universal link configuration
        self.universal_link_domain = os.getenv('UNIVERSAL_LINK_DOMAIN', 'links.mita.finance')
        
        logger.info("Mobile email integration service initialized")
    
    def generate_deep_link(
        self,
        action: DeepLinkAction,
        parameters: Dict[str, str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate deep links for mobile app integration"""
        
        params = parameters or {}
        if user_id:
            params['user_id'] = user_id
        
        # Add timestamp for tracking
        params['timestamp'] = str(int(datetime.now(timezone.utc).timestamp()))
        
        # Build parameter string
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        
        # Generate different link formats for cross-platform support
        deep_link = f"{self.deep_link_config.scheme}://{action.value}?{param_string}"
        universal_link = f"https://{self.universal_link_domain}/{action.value}?{param_string}"
        web_fallback = f"{self.deep_link_config.web_fallback}/{action.value}?{param_string}"
        
        # iOS App Store link
        ios_app_store = f"https://apps.apple.com/app/id{self.ios_app_id}"
        
        # Android Play Store link
        android_play_store = f"https://play.google.com/store/apps/details?id={self.android_package_name}"
        
        return {
            'deep_link': deep_link,
            'universal_link': universal_link,
            'web_fallback': web_fallback,
            'ios_app_store': ios_app_store,
            'android_play_store': android_play_store,
            'smart_app_banner': self._generate_smart_app_banner_link(action, params)
        }
    
    def _generate_smart_app_banner_link(self, action: DeepLinkAction, params: Dict[str, str]) -> str:
        """Generate smart app banner compatible link"""
        param_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://{self.deep_link_config.host}/{action.value}?{param_string}"
    
    async def send_password_reset_email_with_mobile(
        self,
        user_email: str,
        user_name: str,
        reset_token: str,
        user_id: str
    ) -> str:
        """Send password reset email with mobile app integration"""
        
        # Generate mobile-friendly links
        links = self.generate_deep_link(
            action=DeepLinkAction.PASSWORD_RESET,
            parameters={
                'token': reset_token,
                'email': user_email
            },
            user_id=user_id
        )
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        
        variables = {
            'user_name': user_name,
            'email': user_email,
            'reset_link': links['web_fallback'],  # Primary link for email
            'mobile_deep_link': links['deep_link'],
            'universal_link': links['universal_link'],
            'expires_at': expires_at.strftime('%B %d, %Y at %I:%M %p UTC'),
            'mobile_instructions': self._get_mobile_instructions(),
            'app_download_links': {
                'ios': links['ios_app_store'],
                'android': links['android_play_store']
            }
        }
        
        return await queue_email(
            to_email=user_email,
            email_type=EmailType.PASSWORD_RESET,
            variables=variables,
            priority=EmailPriority.URGENT,
            user_id=user_id
        )
    
    async def send_email_verification_with_mobile(
        self,
        user_email: str,
        user_name: str,
        verification_token: str,
        user_id: str
    ) -> str:
        """Send email verification with mobile app integration"""
        
        # Generate mobile-friendly links
        links = self.generate_deep_link(
            action=DeepLinkAction.EMAIL_VERIFICATION,
            parameters={
                'token': verification_token,
                'email': user_email
            },
            user_id=user_id
        )
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        
        variables = {
            'user_name': user_name,
            'email': user_email,
            'verification_link': links['web_fallback'],
            'verification_code': verification_token[-6:].upper(),  # Last 6 chars as code
            'mobile_deep_link': links['deep_link'],
            'universal_link': links['universal_link'],
            'expires_at': expires_at.strftime('%B %d, %Y at %I:%M %p UTC'),
            'mobile_instructions': self._get_mobile_instructions(),
            'app_download_links': {
                'ios': links['ios_app_store'],
                'android': links['android_play_store']
            }
        }
        
        return await queue_email(
            to_email=user_email,
            email_type=EmailType.EMAIL_VERIFICATION,
            variables=variables,
            priority=EmailPriority.HIGH,
            user_id=user_id
        )
    
    async def send_transaction_notification_with_mobile(
        self,
        user_email: str,
        user_name: str,
        transaction_details: Dict[str, Any],
        user_id: str
    ) -> str:
        """Send transaction notification with mobile app integration"""
        
        # Generate mobile-friendly links
        links = self.generate_deep_link(
            action=DeepLinkAction.TRANSACTION_REVIEW,
            parameters={
                'transaction_id': str(transaction_details.get('id', '')),
                'amount': str(transaction_details.get('amount', ''))
            },
            user_id=user_id
        )
        
        variables = {
            'user_name': user_name,
            'email': user_email,
            'transaction_amount': f"${transaction_details['amount']:,.2f}",
            'transaction_date': transaction_details.get('date', datetime.now().strftime('%B %d, %Y')),
            'description': transaction_details.get('description', 'Transaction'),
            'transaction_id': transaction_details.get('id'),
            'balance': transaction_details.get('balance'),
            'category': transaction_details.get('category'),
            'mobile_deep_link': links['deep_link'],
            'universal_link': links['universal_link'],
            'view_in_app_link': links['web_fallback'],
            'app_download_links': {
                'ios': links['ios_app_store'],
                'android': links['android_play_store']
            }
        }
        
        return await queue_email(
            to_email=user_email,
            email_type=EmailType.TRANSACTION_CONFIRMATION,
            variables=variables,
            priority=EmailPriority.NORMAL,
            user_id=user_id
        )
    
    async def send_budget_alert_with_mobile(
        self,
        user_email: str,
        user_name: str,
        budget_details: Dict[str, Any],
        user_id: str
    ) -> str:
        """Send budget alert with mobile app integration"""
        
        # Generate mobile-friendly links
        links = self.generate_deep_link(
            action=DeepLinkAction.BUDGET_ALERT,
            parameters={
                'category': budget_details.get('category', ''),
                'percentage': str(int((budget_details['spent_amount'] / budget_details['budget_limit']) * 100))
            },
            user_id=user_id
        )
        
        percentage_used = f"{(budget_details['spent_amount'] / budget_details['budget_limit']) * 100:.1f}%"
        
        variables = {
            'user_name': user_name,
            'email': user_email,
            'budget_category': budget_details['category'],
            'spent_amount': f"${budget_details['spent_amount']:,.2f}",
            'budget_limit': f"${budget_details['budget_limit']:,.2f}",
            'percentage_used': percentage_used,
            'recommendations': budget_details.get('recommendations', []),
            'mobile_deep_link': links['deep_link'],
            'universal_link': links['universal_link'],
            'manage_budget_link': links['web_fallback'],
            'app_download_links': {
                'ios': links['ios_app_store'],
                'android': links['android_play_store']
            }
        }
        
        return await queue_email(
            to_email=user_email,
            email_type=EmailType.BUDGET_ALERT,
            variables=variables,
            priority=EmailPriority.HIGH,
            user_id=user_id
        )
    
    async def send_security_alert_with_mobile(
        self,
        user_email: str,
        user_name: str,
        alert_type: str,
        alert_details: str,
        user_id: str,
        additional_context: Dict[str, Any] = None
    ) -> str:
        """Send security alert with mobile app integration"""
        
        # Generate mobile-friendly links
        links = self.generate_deep_link(
            action=DeepLinkAction.SECURITY_ALERT,
            parameters={
                'alert_type': alert_type.lower().replace(' ', '_')
            },
            user_id=user_id
        )
        
        variables = {
            'user_name': user_name,
            'email': user_email,
            'alert_type': alert_type,
            'alert_details': alert_details,
            'timestamp': datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p UTC'),
            'action_taken': additional_context.get('action_taken') if additional_context else None,
            'recommended_actions': additional_context.get('recommended_actions') if additional_context else [
                'Open the MITA app and change your password',
                'Review recent account activity',
                'Enable two-factor authentication if not already active'
            ],
            'mobile_deep_link': links['deep_link'],
            'universal_link': links['universal_link'],
            'security_settings_link': links['web_fallback'],
            'app_download_links': {
                'ios': links['ios_app_store'],
                'android': links['android_play_store']
            }
        }
        
        return await queue_email(
            to_email=user_email,
            email_type=EmailType.SECURITY_ALERT,
            variables=variables,
            priority=EmailPriority.URGENT,
            user_id=user_id
        )
    
    def _get_mobile_instructions(self) -> Dict[str, str]:
        """Get mobile-specific instructions for different platforms"""
        return {
            'ios': 'If you have the MITA Finance app installed, tap the link to open directly in the app.',
            'android': 'If you have the MITA Finance app installed, tap the link to open directly in the app.',
            'general': 'For the best experience, download the MITA Finance mobile app from your device\'s app store.'
        }
    
    def generate_universal_link_metadata(self) -> Dict[str, Any]:
        """Generate Apple Universal Links metadata"""
        return {
            "applinks": {
                "apps": [],
                "details": [
                    {
                        "appID": f"TEAMID.{self.ios_app_id}",
                        "paths": [
                            "/password_reset",
                            "/email_verification", 
                            "/transaction_review",
                            "/budget_alert",
                            "/security_alert",
                            "/account_setup",
                            "/goal_progress",
                            "/payment_confirmation"
                        ]
                    }
                ]
            }
        }
    
    def generate_android_app_links_metadata(self) -> Dict[str, Any]:
        """Generate Android App Links metadata"""
        return {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": self.android_package_name,
                "sha256_cert_fingerprints": [
                    # Add your app's SHA256 fingerprint here
                    os.getenv('ANDROID_SHA256_FINGERPRINT', '')
                ]
            }
        }
    
    async def handle_email_delivery_tracking(
        self,
        email_job_id: str,
        delivery_status: str,
        user_id: str,
        email_type: EmailType
    ):
        """Handle email delivery tracking for mobile integration"""
        
        # Track email delivery for mobile app analytics
        tracking_data = {
            'job_id': email_job_id,
            'delivery_status': delivery_status,
            'user_id': user_id,
            'email_type': email_type.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'platform': 'email_to_mobile'
        }
        
        # You could send this to your mobile analytics service
        logger.info(f"Email delivery tracked: {tracking_data}")
        
        # If email delivery failed, you might want to trigger a push notification
        if delivery_status == 'failed':
            await self._handle_failed_email_delivery(user_id, email_type)
    
    async def _handle_failed_email_delivery(self, user_id: str, email_type: EmailType):
        """Handle failed email delivery with mobile fallback"""
        
        # This could trigger a push notification as a fallback
        # Implementation would depend on your push notification service
        
        logger.warning(f"Email delivery failed for user {user_id}, email type {email_type.value}")
        
        # You could queue a push notification here as a fallback
        # await self.push_notification_service.send_notification(...)


# Global mobile email integration service
mobile_email_integration = MobileEmailIntegration()


async def get_mobile_email_integration() -> MobileEmailIntegration:
    """Get mobile email integration service instance"""
    return mobile_email_integration


# Convenience functions for mobile-integrated emails
async def send_mobile_password_reset_email(
    user_email: str,
    user_name: str,
    reset_token: str,
    user_id: str
) -> str:
    """Send password reset email with mobile integration"""
    return await mobile_email_integration.send_password_reset_email_with_mobile(
        user_email, user_name, reset_token, user_id
    )


async def send_mobile_email_verification(
    user_email: str,
    user_name: str,
    verification_token: str,
    user_id: str
) -> str:
    """Send email verification with mobile integration"""
    return await mobile_email_integration.send_email_verification_with_mobile(
        user_email, user_name, verification_token, user_id
    )