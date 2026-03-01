"""
External Services Configuration and Management
Centralized configuration for all external service integrations
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import httpx
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration


logger = logging.getLogger(__name__)


class ServiceHealth(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ExternalServiceConfig:
    """External service configuration"""
    name: str
    enabled: bool
    health_status: ServiceHealth
    last_check: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    config: Dict[str, Any] = None


class OpenAIService:
    """OpenAI API service configuration"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.timeout = int(os.getenv('OPENAI_TIMEOUT', '30'))
        self.max_retries = int(os.getenv('OPENAI_MAX_RETRIES', '3'))
        self.enabled = bool(self.api_key and self.api_key.startswith('sk-'))
        
        # Rate limiting configuration
        self.rate_limit_requests = int(os.getenv('OPENAI_RATE_LIMIT_REQUESTS', '1000'))
        self.rate_limit_tokens = int(os.getenv('OPENAI_RATE_LIMIT_TOKENS', '100000'))
        
        logger.info(f"OpenAI service configured: enabled={self.enabled}, model={self.model}")
    
    async def validate_connection(self) -> bool:
        """Validate OpenAI API connection"""
        if not self.enabled:
            return False
        
        try:
            import openai
            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                timeout=self.timeout
            )
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=1
            )
            
            return bool(response.choices)
            
        except Exception as e:
            logger.error(f"OpenAI connection validation failed: {str(e)}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get OpenAI configuration"""
        return {
            'enabled': self.enabled,
            'model': self.model,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'rate_limits': {
                'requests': self.rate_limit_requests,
                'tokens': self.rate_limit_tokens
            },
            'api_key_configured': bool(self.api_key)
        }


class SentryService:
    """Sentry error monitoring service"""
    
    def __init__(self):
        self.dsn = os.getenv('SENTRY_DSN')
        self.environment = os.getenv('SENTRY_ENVIRONMENT', 'production')
        self.traces_sample_rate = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1'))
        self.profiles_sample_rate = float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.1'))
        self.release = os.getenv('SENTRY_RELEASE')
        
        self.enabled = bool(self.dsn and self.dsn.startswith('https://'))
        
        if self.enabled:
            self._initialize_sentry()
        
        logger.info(f"Sentry service configured: enabled={self.enabled}")
    
    def _initialize_sentry(self):
        """Initialize Sentry SDK"""
        try:
            sentry_sdk.init(
                dsn=self.dsn,
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    RedisIntegration(),
                ],
                environment=self.environment,
                traces_sample_rate=self.traces_sample_rate,
                profiles_sample_rate=self.profiles_sample_rate,
                release=self.release,
                send_default_pii=False,
                attach_stacktrace=True,
                max_breadcrumbs=50,
            )
            logger.info("Sentry monitoring initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {str(e)}")
            self.enabled = False
    
    def capture_exception(self, exception: Exception, **kwargs):
        """Capture exception to Sentry"""
        if not self.enabled:
            return None
        
        return sentry_sdk.capture_exception(exception, **kwargs)
    
    def capture_message(self, message: str, level: str = "info", **kwargs):
        """Capture message to Sentry"""
        if not self.enabled:
            return None
        
        return sentry_sdk.capture_message(message, level=level, **kwargs)
    
    def get_config(self) -> Dict[str, Any]:
        """Get Sentry configuration"""
        return {
            'enabled': self.enabled,
            'environment': self.environment,
            'traces_sample_rate': self.traces_sample_rate,
            'profiles_sample_rate': self.profiles_sample_rate,
            'release': self.release,
            'dsn_configured': bool(self.dsn)
        }


class SendGridService:
    """SendGrid email service"""
    
    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY') or os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('SMTP_FROM', 'noreply@mita.finance')
        self.from_name = os.getenv('SMTP_FROM_NAME', 'MITA Finance')
        
        self.enabled = bool(self.api_key and self.api_key.startswith('SG.'))
        
        # Alternative email providers
        self.mailgun_key = os.getenv('MAILGUN_API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        self.postmark_key = os.getenv('POSTMARK_API_KEY')
        
        logger.info(f"SendGrid service configured: enabled={self.enabled}")
    
    async def validate_connection(self) -> bool:
        """Validate SendGrid API connection"""
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                response = await client.get(
                    'https://api.sendgrid.com/v3/user/profile',
                    headers=headers,
                    timeout=10.0
                )
                
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"SendGrid connection validation failed: {str(e)}")
            return False
    
    async def send_email(self, to_email: str, subject: str, content: str, content_type: str = "text/html") -> bool:
        """Send email via SendGrid"""
        if not self.enabled:
            logger.warning("SendGrid not enabled, email not sent")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                data = {
                    "personalizations": [{
                        "to": [{"email": to_email}]
                    }],
                    "from": {
                        "email": self.from_email,
                        "name": self.from_name
                    },
                    "subject": subject,
                    "content": [{
                        "type": content_type,
                        "value": content
                    }]
                }
                
                response = await client.post(
                    'https://api.sendgrid.com/v3/mail/send',
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                
                return response.status_code == 202
                
        except Exception as e:
            logger.error(f"Failed to send email via SendGrid: {str(e)}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get SendGrid configuration"""
        return {
            'enabled': self.enabled,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'api_key_configured': bool(self.api_key),
            'alternatives': {
                'mailgun': bool(self.mailgun_key),
                'postmark': bool(self.postmark_key)
            }
        }


class RedisService:
    """Redis/Upstash caching service"""
    
    def __init__(self):
        self.upstash_url = os.getenv('UPSTASH_REDIS_URL')
        self.upstash_rest_url = os.getenv('UPSTASH_REDIS_REST_URL')
        self.upstash_rest_token = os.getenv('UPSTASH_REDIS_REST_TOKEN')
        
        self.redis_url = os.getenv('REDIS_URL') or self.upstash_url
        
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', '20'))
        self.timeout = int(os.getenv('REDIS_TIMEOUT', '30'))
        self.retry_on_timeout = os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true'
        
        self.enabled = bool(self.redis_url)
        
        logger.info(f"Redis service configured: enabled={self.enabled}, using_upstash={bool(self.upstash_url)}")
    
    async def validate_connection(self) -> bool:
        """Validate Redis connection"""
        if not self.enabled:
            return False
        
        try:
            import redis.asyncio as redis
            
            r = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=self.timeout,
                retry_on_timeout=self.retry_on_timeout
            )
            
            await r.ping()
            await r.aclose()
            
            return True
            
        except Exception as e:
            logger.error(f"Redis connection validation failed: {str(e)}")
            return False
    
    async def get_client(self):
        """Get Redis client"""
        if not self.enabled:
            return None
        
        import redis.asyncio as redis
        
        return redis.from_url(
            self.redis_url,
            decode_responses=True,
            max_connections=self.max_connections,
            socket_timeout=self.timeout,
            retry_on_timeout=self.retry_on_timeout
        )
    
    def get_config(self) -> Dict[str, Any]:
        """Get Redis configuration"""
        return {
            'enabled': self.enabled,
            'using_upstash': bool(self.upstash_url),
            'max_connections': self.max_connections,
            'timeout': self.timeout,
            'retry_on_timeout': self.retry_on_timeout,
            'rest_api_available': bool(self.upstash_rest_url and self.upstash_rest_token)
        }


class FirebaseService:
    """Firebase push notification service"""
    
    def __init__(self):
        self.service_account_json = os.getenv('FIREBASE_JSON')
        self.project_id = os.getenv('FIREBASE_PROJECT_ID')
        
        self.enabled = bool(self.service_account_json)
        self.initialized = False
        
        if self.enabled:
            self._initialize_firebase()
        
        logger.info(f"Firebase service configured: enabled={self.enabled}")
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            if not firebase_admin._apps:
                # Parse service account JSON
                if self.service_account_json.startswith('{'):
                    # JSON string
                    creds_dict = json.loads(self.service_account_json)
                else:
                    # File path
                    with open(self.service_account_json, 'r') as f:
                        creds_dict = json.load(f)
                
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred)
                
                self.project_id = creds_dict.get('project_id', self.project_id)
                self.initialized = True
                
                logger.info("Firebase Admin SDK initialized successfully")
            else:
                self.initialized = True
                
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self.enabled = False
            self.initialized = False
    
    async def send_push_notification(self, token: str, title: str, body: str, data: Dict[str, str] = None) -> bool:
        """Send push notification"""
        if not self.enabled or not self.initialized:
            logger.warning("Firebase not available, push notification not sent")
            return False
        
        try:
            from firebase_admin import messaging
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=token,
                data=data or {}
            )
            
            response = messaging.send(message)
            return bool(response)
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get Firebase configuration"""
        return {
            'enabled': self.enabled,
            'initialized': self.initialized,
            'project_id': self.project_id,
            'service_account_configured': bool(self.service_account_json)
        }


class AWSService:
    """AWS S3 storage service"""
    
    def __init__(self):
        self.access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self.bucket = os.getenv('AWS_S3_BUCKET', 'mita-production-storage')
        self.backup_bucket = os.getenv('BACKUP_BUCKET', 'mita-production-backups')
        
        self.enabled = bool(self.access_key and self.secret_key)
        
        # CloudFront configuration
        self.cloudfront_domain = os.getenv('CLOUDFRONT_DOMAIN')
        self.cloudfront_key_pair_id = os.getenv('CLOUDFRONT_KEY_PAIR_ID')
        
        logger.info(f"AWS service configured: enabled={self.enabled}, region={self.region}")
    
    async def validate_connection(self) -> bool:
        """Validate AWS S3 connection"""
        if not self.enabled:
            return False
        
        try:
            import boto3
            
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            # Test with list buckets
            response = s3_client.list_buckets()
            return 'Buckets' in response
            
        except Exception as e:
            logger.error(f"AWS connection validation failed: {str(e)}")
            return False
    
    def get_s3_client(self):
        """Get S3 client"""
        if not self.enabled:
            return None
        
        import boto3
        
        return boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )
    
    def get_config(self) -> Dict[str, Any]:
        """Get AWS configuration"""
        return {
            'enabled': self.enabled,
            'region': self.region,
            'bucket': self.bucket,
            'backup_bucket': self.backup_bucket,
            'cloudfront_enabled': bool(self.cloudfront_domain),
            'credentials_configured': bool(self.access_key and self.secret_key)
        }


class ExternalServicesManager:
    """Centralized external services manager"""
    
    def __init__(self):
        # Initialize all services
        self.openai = OpenAIService()
        self.sentry = SentryService()
        self.sendgrid = SendGridService()
        self.redis = RedisService()
        self.firebase = FirebaseService()
        self.aws = AWSService()
        
        self.services = {
            'openai': self.openai,
            'sentry': self.sentry,
            'sendgrid': self.sendgrid,
            'redis': self.redis,
            'firebase': self.firebase,
            'aws': self.aws
        }
        
        self.health_status = {}
        self.last_health_check = None
        
        logger.info("External services manager initialized")
    
    async def validate_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Validate all external services"""
        results = {}
        
        for service_name, service in self.services.items():
            try:
                if hasattr(service, 'validate_connection'):
                    connected = await service.validate_connection()
                else:
                    connected = service.enabled
                
                config = service.get_config()
                
                results[service_name] = {
                    'enabled': service.enabled,
                    'connected': connected,
                    'config': config,
                    'status': 'healthy' if connected else 'unhealthy' if service.enabled else 'disabled'
                }
                
            except Exception as e:
                results[service_name] = {
                    'enabled': service.enabled,
                    'connected': False,
                    'error': str(e),
                    'status': 'error'
                }
                logger.error(f"Service validation failed for {service_name}: {str(e)}")
        
        self.health_status = results
        self.last_health_check = datetime.now()
        
        return results
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get overall service health"""
        if not self.health_status:
            return {'status': 'unknown', 'services': {}}
        
        total_services = len(self.services)
        enabled_services = len([s for s in self.health_status.values() if s.get('enabled', False)])
        healthy_services = len([s for s in self.health_status.values() if s.get('status') == 'healthy'])
        
        overall_status = 'healthy'
        if healthy_services == 0:
            overall_status = 'critical'
        elif healthy_services < enabled_services * 0.8:
            overall_status = 'degraded'
        
        return {
            'status': overall_status,
            'total_services': total_services,
            'enabled_services': enabled_services,
            'healthy_services': healthy_services,
            'last_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'services': self.health_status
        }
    
    def get_critical_services_status(self) -> Dict[str, bool]:
        """Get status of critical services only"""
        critical_services = ['openai', 'sentry', 'redis', 'sendgrid']
        
        return {
            service: self.health_status.get(service, {}).get('status') == 'healthy'
            for service in critical_services
        }


# Global services manager
external_services = ExternalServicesManager()


async def validate_external_services() -> Dict[str, Any]:
    """Validate all external services"""
    return await external_services.validate_all_services()


def get_services_health() -> Dict[str, Any]:
    """Get services health status"""
    return external_services.get_service_health()


def get_critical_services_status() -> Dict[str, bool]:
    """Get critical services status"""
    return external_services.get_critical_services_status()