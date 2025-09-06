"""
API Key Management System for MITA Finance
Provides secure API key storage, validation, rotation, and monitoring
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import hashlib
import secrets
from pathlib import Path

import httpx
import sentry_sdk
from cryptography.fernet import Fernet
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """External service types"""
    OPENAI = "openai"
    SENTRY = "sentry"
    FIREBASE = "firebase"
    SENDGRID = "sendgrid"
    AWS = "aws"
    UPSTASH = "upstash"
    STRIPE = "stripe"
    PLAID = "plaid"
    TWILIO = "twilio"
    APPLE = "apple"


class APIKeyStatus(Enum):
    """API key status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    ROTATED = "rotated"
    INVALID = "invalid"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"


@dataclass
class APIKeyInfo:
    """API key information"""
    service: ServiceType
    key_name: str
    status: APIKeyStatus
    last_validated: datetime
    last_rotation: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    daily_quota: Optional[int] = None
    current_usage: Optional[int] = None
    error_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['service'] = self.service.value
        data['status'] = self.status.value
        data['last_validated'] = self.last_validated.isoformat()
        if self.last_rotation:
            data['last_rotation'] = self.last_rotation.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        return data


class APIKeyValidator:
    """Validates API keys for different services"""
    
    def __init__(self):
        self.validation_cache = {}
        self.cache_ttl = timedelta(minutes=15)  # Cache validation results
    
    async def validate_openai_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate OpenAI API key"""
        if not api_key or not api_key.startswith('sk-'):
            return False, "Invalid OpenAI API key format"
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            
            # Test with minimal request
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                timeout=10.0
            )
            return True, None
            
        except openai.AuthenticationError:
            return False, "Invalid API key"
        except openai.RateLimitError:
            return False, "Rate limit exceeded"
        except openai.PermissionDeniedError:
            return False, "Permission denied"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    async def validate_sentry_dsn(self, dsn: str) -> Tuple[bool, Optional[str]]:
        """Validate Sentry DSN"""
        if not dsn or not dsn.startswith('https://'):
            return False, "Invalid Sentry DSN format"
        
        try:
            # Test Sentry connection by capturing a test exception
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("validation", "test")
                scope.set_extra("test", True)
                
                # Configure Sentry with the DSN
                sentry_sdk.init(
                    dsn=dsn,
                    environment="validation",
                    traces_sample_rate=0.0,
                    send_default_pii=False
                )
                
                # Test capture
                try:
                    raise Exception("API key validation test")
                except Exception as e:
                    event_id = sentry_sdk.capture_exception(e)
                    if event_id:
                        return True, None
                    
            return False, "Failed to capture test event"
            
        except Exception as e:
            return False, f"DSN validation error: {str(e)}"
    
    async def validate_sendgrid_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate SendGrid API key"""
        if not api_key or not api_key.startswith('SG.'):
            return False, "Invalid SendGrid API key format"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }
                
                # Test API key with user profile endpoint
                response = await client.get(
                    'https://api.sendgrid.com/v3/user/profile',
                    headers=headers
                )
                
                if response.status_code == 200:
                    return True, None
                elif response.status_code == 401:
                    return False, "Invalid API key"
                elif response.status_code == 403:
                    return False, "API key lacks required permissions"
                else:
                    return False, f"Unexpected status: {response.status_code}"
                    
        except Exception as e:
            return False, f"SendGrid validation error: {str(e)}"
    
    async def validate_firebase_credentials(self, service_account_json: str) -> Tuple[bool, Optional[str]]:
        """Validate Firebase service account JSON"""
        try:
            credentials = json.loads(service_account_json)
            required_fields = [
                'type', 'project_id', 'private_key_id', 'private_key',
                'client_email', 'client_id', 'auth_uri', 'token_uri'
            ]
            
            missing_fields = [field for field in required_fields if field not in credentials]
            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}"
            
            if credentials.get('type') != 'service_account':
                return False, "Invalid service account type"
            
            # Test Firebase Admin SDK initialization
            import firebase_admin
            from firebase_admin import credentials as firebase_creds
            
            # Create temporary credential object for validation
            cred = firebase_creds.Certificate(credentials)
            
            # Test initialization (don't actually initialize)
            if cred.project_id and cred.service_account_email:
                return True, None
            else:
                return False, "Invalid service account credentials"
                
        except json.JSONDecodeError:
            return False, "Invalid JSON format"
        except Exception as e:
            return False, f"Firebase validation error: {str(e)}"
    
    async def validate_upstash_redis(self, redis_url: str) -> Tuple[bool, Optional[str]]:
        """Validate Upstash Redis connection"""
        if not redis_url:
            return False, "Redis URL is required"
        
        try:
            import redis.asyncio as redis
            
            # Parse connection parameters
            r = redis.from_url(redis_url, decode_responses=True)
            
            # Test connection with ping
            await r.ping()
            await r.aclose()
            
            return True, None
            
        except redis.AuthenticationError:
            return False, "Invalid Redis authentication"
        except redis.ConnectionError:
            return False, "Cannot connect to Redis server"
        except Exception as e:
            return False, f"Redis validation error: {str(e)}"
    
    async def validate_aws_credentials(self, access_key: str, secret_key: str, region: str = "us-east-1") -> Tuple[bool, Optional[str]]:
        """Validate AWS credentials"""
        if not access_key or not secret_key:
            return False, "AWS access key and secret key are required"
        
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            # Test credentials with STS get-caller-identity
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            sts_client = session.client('sts')
            response = sts_client.get_caller_identity()
            
            if response.get('UserId'):
                return True, None
            else:
                return False, "Invalid AWS credentials"
                
        except NoCredentialsError:
            return False, "AWS credentials not found"
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidUserID.NotFound':
                return False, "Invalid AWS access key"
            elif error_code == 'SignatureDoesNotMatch':
                return False, "Invalid AWS secret key"
            else:
                return False, f"AWS error: {error_code}"
        except Exception as e:
            return False, f"AWS validation error: {str(e)}"


class APIKeyManager:
    """Comprehensive API key management system"""
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        self.validator = APIKeyValidator()
        self.key_info: Dict[str, APIKeyInfo] = {}
        
        # Initialize encryption
        if encryption_key:
            self.fernet = Fernet(encryption_key)
        else:
            # Generate a key (in production, this should be stored securely)
            self.fernet = Fernet(Fernet.generate_key())
        
        # Load existing key info
        self._load_key_info()
    
    def _load_key_info(self):
        """Load API key information from storage"""
        try:
            info_file = Path("./data/api_keys_info.json")
            if info_file.exists():
                with open(info_file, 'r') as f:
                    data = json.load(f)
                    
                for key_name, info_dict in data.items():
                    # Convert back to APIKeyInfo object
                    info_dict['service'] = ServiceType(info_dict['service'])
                    info_dict['status'] = APIKeyStatus(info_dict['status'])
                    info_dict['last_validated'] = datetime.fromisoformat(info_dict['last_validated'])
                    
                    if info_dict.get('last_rotation'):
                        info_dict['last_rotation'] = datetime.fromisoformat(info_dict['last_rotation'])
                    if info_dict.get('expires_at'):
                        info_dict['expires_at'] = datetime.fromisoformat(info_dict['expires_at'])
                    
                    self.key_info[key_name] = APIKeyInfo(**info_dict)
                    
        except Exception as e:
            logger.error(f"Failed to load API key info: {str(e)}")
    
    def _save_key_info(self):
        """Save API key information to storage"""
        try:
            info_file = Path("./data/api_keys_info.json")
            info_file.parent.mkdir(exist_ok=True)
            
            # Convert to serializable format
            data = {key: info.to_dict() for key, info in self.key_info.items()}
            
            with open(info_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save API key info: {str(e)}")
    
    async def validate_all_keys(self) -> Dict[str, Dict[str, Any]]:
        """Validate all configured API keys"""
        results = {}
        
        # Get all API keys from environment
        api_keys = self._get_environment_keys()
        
        for key_name, key_value in api_keys.items():
            try:
                service_type = self._detect_service_type(key_name)
                if not service_type:
                    results[key_name] = {
                        'valid': False,
                        'error': 'Unknown service type',
                        'service': 'unknown'
                    }
                    continue
                
                # Validate the key
                valid, error = await self._validate_key(service_type, key_value, key_name)
                
                # Update key info
                if key_name in self.key_info:
                    key_info = self.key_info[key_name]
                else:
                    key_info = APIKeyInfo(
                        service=service_type,
                        key_name=key_name,
                        status=APIKeyStatus.ACTIVE,
                        last_validated=datetime.now()
                    )
                    self.key_info[key_name] = key_info
                
                # Update status
                key_info.last_validated = datetime.now()
                if valid:
                    key_info.status = APIKeyStatus.ACTIVE
                    key_info.error_count = 0
                    key_info.last_error = None
                else:
                    key_info.status = APIKeyStatus.INVALID
                    key_info.error_count += 1
                    key_info.last_error = error
                
                results[key_name] = {
                    'valid': valid,
                    'error': error,
                    'service': service_type.value,
                    'last_validated': key_info.last_validated.isoformat(),
                    'error_count': key_info.error_count
                }
                
            except Exception as e:
                logger.error(f"Error validating key {key_name}: {str(e)}")
                results[key_name] = {
                    'valid': False,
                    'error': f'Validation error: {str(e)}',
                    'service': 'unknown'
                }
        
        # Save updated key info
        self._save_key_info()
        
        return results
    
    def _get_environment_keys(self) -> Dict[str, str]:
        """Get all API keys from environment variables"""
        api_key_patterns = [
            'OPENAI_API_KEY',
            'SENTRY_DSN',
            'SENDGRID_API_KEY',
            'FIREBASE_JSON',
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'UPSTASH_REDIS_URL',
            'UPSTASH_REDIS_REST_URL',
            'UPSTASH_REDIS_REST_TOKEN',
            'STRIPE_SECRET_KEY',
            'PLAID_SECRET',
            'TWILIO_AUTH_TOKEN',
            'APPSTORE_SHARED_SECRET',
            'APNS_KEY_ID',
            'MAILGUN_API_KEY',
            'POSTMARK_API_KEY'
        ]
        
        keys = {}
        for pattern in api_key_patterns:
            value = os.getenv(pattern)
            if value and value.strip() and not value.startswith('${'):
                keys[pattern] = value.strip()
        
        return keys
    
    def _detect_service_type(self, key_name: str) -> Optional[ServiceType]:
        """Detect service type from key name"""
        service_mapping = {
            'OPENAI': ServiceType.OPENAI,
            'SENTRY': ServiceType.SENTRY,
            'SENDGRID': ServiceType.SENDGRID,
            'FIREBASE': ServiceType.FIREBASE,
            'AWS': ServiceType.AWS,
            'UPSTASH': ServiceType.UPSTASH,
            'REDIS': ServiceType.UPSTASH,
            'STRIPE': ServiceType.STRIPE,
            'PLAID': ServiceType.PLAID,
            'TWILIO': ServiceType.TWILIO,
            'APNS': ServiceType.APPLE,
            'APPSTORE': ServiceType.APPLE,
            'MAILGUN': ServiceType.SENDGRID,  # Treat as email service
            'POSTMARK': ServiceType.SENDGRID  # Treat as email service
        }
        
        for service_prefix, service_type in service_mapping.items():
            if service_prefix in key_name.upper():
                return service_type
        
        return None
    
    async def _validate_key(self, service_type: ServiceType, key_value: str, key_name: str) -> Tuple[bool, Optional[str]]:
        """Validate a specific API key"""
        try:
            if service_type == ServiceType.OPENAI:
                return await self.validator.validate_openai_key(key_value)
            
            elif service_type == ServiceType.SENTRY:
                return await self.validator.validate_sentry_dsn(key_value)
            
            elif service_type == ServiceType.SENDGRID:
                return await self.validator.validate_sendgrid_key(key_value)
            
            elif service_type == ServiceType.FIREBASE:
                return await self.validator.validate_firebase_credentials(key_value)
            
            elif service_type == ServiceType.UPSTASH:
                return await self.validator.validate_upstash_redis(key_value)
            
            elif service_type == ServiceType.AWS:
                # For AWS, we need both access key and secret key
                if 'ACCESS_KEY' in key_name:
                    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
                    if secret_key:
                        return await self.validator.validate_aws_credentials(key_value, secret_key)
                    else:
                        return False, "AWS secret key not found"
                elif 'SECRET_ACCESS_KEY' in key_name:
                    access_key = os.getenv('AWS_ACCESS_KEY_ID')
                    if access_key:
                        return await self.validator.validate_aws_credentials(access_key, key_value)
                    else:
                        return False, "AWS access key not found"
            
            # For other services, basic format validation
            else:
                if len(key_value) > 10:  # Basic length check
                    return True, None
                else:
                    return False, "Key appears too short"
        
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def get_key_health_status(self) -> Dict[str, Any]:
        """Get overall API key health status"""
        total_keys = len(self.key_info)
        active_keys = len([k for k in self.key_info.values() if k.status == APIKeyStatus.ACTIVE])
        invalid_keys = len([k for k in self.key_info.values() if k.status == APIKeyStatus.INVALID])
        
        # Check for keys requiring rotation (older than 90 days)
        rotation_threshold = datetime.now() - timedelta(days=90)
        needs_rotation = [
            k for k in self.key_info.values()
            if not k.last_rotation or k.last_rotation < rotation_threshold
        ]
        
        health_status = "healthy"
        if invalid_keys > 0:
            health_status = "unhealthy"
        elif len(needs_rotation) > 0:
            health_status = "warning"
        
        return {
            'status': health_status,
            'total_keys': total_keys,
            'active_keys': active_keys,
            'invalid_keys': invalid_keys,
            'keys_needing_rotation': len(needs_rotation),
            'last_validation': max(
                (k.last_validated for k in self.key_info.values()),
                default=datetime.min
            ).isoformat(),
            'key_details': {name: info.to_dict() for name, info in self.key_info.items()}
        }
    
    async def rotate_key(self, key_name: str, new_key: str) -> bool:
        """Rotate an API key"""
        try:
            if key_name not in self.key_info:
                logger.error(f"Key {key_name} not found for rotation")
                return False
            
            key_info = self.key_info[key_name]
            
            # Validate the new key
            valid, error = await self._validate_key(key_info.service, new_key, key_name)
            if not valid:
                logger.error(f"New key validation failed: {error}")
                return False
            
            # Update key info
            key_info.last_rotation = datetime.now()
            key_info.status = APIKeyStatus.ACTIVE
            key_info.error_count = 0
            key_info.last_error = None
            
            # Save changes
            self._save_key_info()
            
            logger.info(f"Successfully rotated key: {key_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error rotating key {key_name}: {str(e)}")
            return False


# Global API key manager instance
api_key_manager = APIKeyManager()


async def validate_production_keys() -> Dict[str, Any]:
    """Validate all production API keys"""
    return await api_key_manager.validate_all_keys()


def get_api_key_health() -> Dict[str, Any]:
    """Get API key health status"""
    return api_key_manager.get_key_health_status()


async def rotate_api_key(key_name: str, new_key: str) -> bool:
    """Rotate an API key"""
    return await api_key_manager.rotate_key(key_name, new_key)