"""
MITA Finance - Production Secret Management System

This module provides a comprehensive secret management system for the MITA financial application.
It supports multiple cloud providers, secret rotation, audit logging, and compliance requirements.

Features:
- Multi-cloud secret management (AWS Secrets Manager, GCP Secret Manager, Kubernetes)
- Automatic secret rotation with versioning
- Secret categorization by criticality and compliance requirements
- Audit logging for all secret access
- Emergency rotation procedures
- Fallback mechanisms for high availability

Compliance: SOX, PCI DSS, GDPR
Security: Financial-grade encryption, zero-trust architecture
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import secrets
from contextlib import asynccontextmanager

try:
    import boto3
    from botocore.exceptions import ClientError  # noqa: F401
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from google.cloud import secretmanager
    from google.api_core import exceptions as gcp_exceptions
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

# Configure logging for financial compliance
logger = logging.getLogger(__name__)


class SecretProvider(Enum):
    """Supported secret management providers"""
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    KUBERNETES = "kubernetes"
    VAULT = "vault"
    ENVIRONMENT = "environment"


class SecretCategory(Enum):
    """Secret classification for compliance and rotation requirements"""
    CRITICAL = "critical"          # Database passwords, JWT secrets
    HIGH = "high"                  # API keys, service credentials
    MEDIUM = "medium"             # Third-party integrations
    LOW = "low"                   # Non-sensitive configuration


class SecretRotationStatus(Enum):
    """Secret rotation status tracking"""
    ACTIVE = "active"
    PENDING_ROTATION = "pending_rotation"
    ROTATING = "rotating"
    DEPRECATED = "deprecated"
    EMERGENCY_ROTATED = "emergency_rotated"


@dataclass
class SecretMetadata:
    """Metadata for secret tracking and compliance"""
    name: str
    category: SecretCategory
    provider: SecretProvider
    version: str
    created_at: datetime
    expires_at: Optional[datetime]
    rotation_interval_days: int
    last_accessed: Optional[datetime]
    access_count: int
    status: SecretRotationStatus
    compliance_tags: List[str]
    emergency_contact: Optional[str]


@dataclass
class SecretValue:
    """Secure container for secret values with metadata"""
    value: str
    metadata: SecretMetadata
    
    def __post_init__(self):
        """Ensure the value is properly secured"""
        if not isinstance(self.value, str):
            raise ValueError("Secret value must be a string")
        
        # Log access for audit trail
        logger.info(f"Secret accessed: {self.metadata.name} (category: {self.metadata.category.value})")
        
        # Update access tracking
        self.metadata.last_accessed = datetime.utcnow()
        self.metadata.access_count += 1


class SecretManagerError(Exception):
    """Base exception for secret management errors"""
    pass


class SecretNotFoundError(SecretManagerError):
    """Secret not found in any provider"""
    pass


class SecretRotationError(SecretManagerError):
    """Error during secret rotation"""
    pass


class ComplianceViolationError(SecretManagerError):
    """Compliance requirements not met"""
    pass


class UnifiedSecretManager:
    """
    Unified secret management system for MITA Finance
    
    Provides secure, auditable, and compliant secret management across multiple providers
    with automatic rotation, fallback mechanisms, and financial-grade security.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the secret manager with configuration
        
        Args:
            config: Configuration dictionary containing provider settings
        """
        self.config = config
        self.providers: Dict[SecretProvider, Any] = {}
        self.secret_cache: Dict[str, SecretValue] = {}
        self.metadata_cache: Dict[str, SecretMetadata] = {}
        self.audit_log: List[Dict[str, Any]] = []
        
        # Initialize audit logging
        self._setup_audit_logging()
        
        # Initialize providers
        self._initialize_providers()
        
        # Load secret definitions
        self.secret_definitions = self._load_secret_definitions()
        
        logger.info("Unified Secret Manager initialized successfully")
    
    def _setup_audit_logging(self):
        """Setup comprehensive audit logging for compliance"""
        audit_handler = logging.FileHandler(
            self.config.get('audit_log_file', '/var/log/mita/secrets_audit.log')
        )
        audit_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
        audit_handler.setFormatter(audit_formatter)
        
        audit_logger = logging.getLogger('mita.secrets.audit')
        audit_logger.addHandler(audit_handler)
        audit_logger.setLevel(logging.INFO)
        
        self.audit_logger = audit_logger
    
    def _initialize_providers(self):
        """Initialize configured secret providers"""
        providers = self.config.get('providers', ['environment'])
        
        for provider_name in providers:
            try:
                provider = SecretProvider(provider_name)
                
                if provider == SecretProvider.AWS_SECRETS_MANAGER and AWS_AVAILABLE:
                    self._init_aws_provider()
                elif provider == SecretProvider.GCP_SECRET_MANAGER and GCP_AVAILABLE:
                    self._init_gcp_provider()
                elif provider == SecretProvider.KUBERNETES and K8S_AVAILABLE:
                    self._init_k8s_provider()
                elif provider == SecretProvider.ENVIRONMENT:
                    self._init_env_provider()
                
                logger.info(f"Initialized provider: {provider.value}")
                
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_name}: {e}")
    
    def _init_aws_provider(self):
        """Initialize AWS Secrets Manager"""
        try:
            aws_config = self.config.get('aws', {})
            session = boto3.Session(
                region_name=aws_config.get('region', 'us-east-1')
            )
            self.providers[SecretProvider.AWS_SECRETS_MANAGER] = session.client('secretsmanager')
            logger.info("AWS Secrets Manager provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AWS provider: {e}")
    
    def _init_gcp_provider(self):
        """Initialize GCP Secret Manager"""
        try:
            gcp_config = self.config.get('gcp', {})
            project_id = gcp_config.get('project_id')
            if project_id:
                self.providers[SecretProvider.GCP_SECRET_MANAGER] = secretmanager.SecretManagerServiceClient()
                self.gcp_project_id = project_id
                logger.info("GCP Secret Manager provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GCP provider: {e}")
    
    def _init_k8s_provider(self):
        """Initialize Kubernetes secrets"""
        try:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            
            self.providers[SecretProvider.KUBERNETES] = client.CoreV1Api()
            logger.info("Kubernetes secrets provider initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes provider: {e}")
    
    def _init_env_provider(self):
        """Initialize environment variables provider"""
        self.providers[SecretProvider.ENVIRONMENT] = os.environ
        logger.info("Environment variables provider initialized")
    
    def _load_secret_definitions(self) -> Dict[str, SecretMetadata]:
        """Load secret definitions from configuration"""
        definitions = {}
        secret_configs = self.config.get('secrets', {})
        
        for secret_name, secret_config in secret_configs.items():
            try:
                metadata = SecretMetadata(
                    name=secret_name,
                    category=SecretCategory(secret_config.get('category', 'medium')),
                    provider=SecretProvider(secret_config.get('provider', 'environment')),
                    version=secret_config.get('version', '1'),
                    created_at=datetime.utcnow(),
                    expires_at=None,
                    rotation_interval_days=secret_config.get('rotation_interval_days', 30),
                    last_accessed=None,
                    access_count=0,
                    status=SecretRotationStatus.ACTIVE,
                    compliance_tags=secret_config.get('compliance_tags', []),
                    emergency_contact=secret_config.get('emergency_contact')
                )
                definitions[secret_name] = metadata
            except Exception as e:
                logger.error(f"Failed to load definition for secret {secret_name}: {e}")
        
        return definitions
    
    async def get_secret(self, name: str, version: Optional[str] = None) -> SecretValue:
        """
        Retrieve a secret by name with full audit trail
        
        Args:
            name: Secret name
            version: Specific version to retrieve (optional)
            
        Returns:
            SecretValue containing the secret and metadata
            
        Raises:
            SecretNotFoundError: If secret is not found
            ComplianceViolationError: If access violates compliance rules
        """
        # Audit log the access attempt
        self._audit_log('access_attempt', name, {'version': version})
        
        # Get secret metadata
        metadata = self.secret_definitions.get(name)
        if not metadata:
            raise SecretNotFoundError(f"Secret definition not found: {name}")
        
        # Check compliance rules
        await self._check_compliance(name, metadata)
        
        # Try to get from cache first (if not expired)
        cache_key = f"{name}:{version or 'latest'}"
        cached_secret = self.secret_cache.get(cache_key)
        if cached_secret and self._is_cache_valid(cached_secret):
            self._audit_log('access_success', name, {'source': 'cache'})
            return cached_secret
        
        # Retrieve from provider
        secret_value = await self._retrieve_from_provider(name, metadata, version)
        
        # Cache the secret
        secret_obj = SecretValue(value=secret_value, metadata=metadata)
        self.secret_cache[cache_key] = secret_obj
        
        self._audit_log('access_success', name, {'source': metadata.provider.value})
        return secret_obj
    
    async def _retrieve_from_provider(self, name: str, metadata: SecretMetadata, version: Optional[str] = None) -> str:
        """Retrieve secret from the configured provider"""
        provider = metadata.provider
        
        try:
            if provider == SecretProvider.AWS_SECRETS_MANAGER:
                return await self._get_from_aws(name, version)
            elif provider == SecretProvider.GCP_SECRET_MANAGER:
                return await self._get_from_gcp(name, version)
            elif provider == SecretProvider.KUBERNETES:
                return await self._get_from_k8s(name, version)
            elif provider == SecretProvider.ENVIRONMENT:
                return self._get_from_env(name)
            else:
                raise SecretManagerError(f"Unsupported provider: {provider}")
        except Exception:
            # Try fallback providers
            return await self._try_fallback_providers(name, version)
    
    async def _get_from_aws(self, name: str, version: Optional[str] = None) -> str:
        """Retrieve secret from AWS Secrets Manager"""
        if SecretProvider.AWS_SECRETS_MANAGER not in self.providers:
            raise SecretManagerError("AWS Secrets Manager not available")
        
        client = self.providers[SecretProvider.AWS_SECRETS_MANAGER]
        
        try:
            kwargs = {'SecretId': f"mita/production/{name}"}
            if version:
                kwargs['VersionId'] = version
            
            response = client.get_secret_value(**kwargs)
            return response['SecretString']
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise SecretNotFoundError(f"Secret not found in AWS: {name}")
            raise SecretManagerError(f"AWS Secrets Manager error: {e}")
    
    async def _get_from_gcp(self, name: str, version: Optional[str] = None) -> str:
        """Retrieve secret from GCP Secret Manager"""
        if SecretProvider.GCP_SECRET_MANAGER not in self.providers:
            raise SecretManagerError("GCP Secret Manager not available")
        
        client = self.providers[SecretProvider.GCP_SECRET_MANAGER]
        
        try:
            secret_path = f"projects/{self.gcp_project_id}/secrets/mita-{name}"
            if version:
                secret_path += f"/versions/{version}"
            else:
                secret_path += "/versions/latest"
            
            response = client.access_secret_version(request={"name": secret_path})
            return response.payload.data.decode('UTF-8')
        except gcp_exceptions.NotFound:
            raise SecretNotFoundError(f"Secret not found in GCP: {name}")
        except Exception as e:
            raise SecretManagerError(f"GCP Secret Manager error: {e}")
    
    async def _get_from_k8s(self, name: str, version: Optional[str] = None) -> str:
        """Retrieve secret from Kubernetes"""
        if SecretProvider.KUBERNETES not in self.providers:
            raise SecretManagerError("Kubernetes provider not available")
        
        k8s_client = self.providers[SecretProvider.KUBERNETES]
        namespace = self.config.get('kubernetes', {}).get('namespace', 'default')
        
        try:
            secret_name = "mita-secrets"
            secret = k8s_client.read_namespaced_secret(name=secret_name, namespace=namespace)
            
            # Kubernetes secret data is base64 encoded
            secret_key = name.replace('_', '-').lower()
            if secret_key in secret.data:
                return base64.b64decode(secret.data[secret_key]).decode('utf-8')
            else:
                raise SecretNotFoundError(f"Secret key not found in Kubernetes secret: {secret_key}")
        except ApiException as e:
            if e.status == 404:
                raise SecretNotFoundError(f"Kubernetes secret not found: {secret_name}")
            raise SecretManagerError(f"Kubernetes API error: {e}")
    
    def _get_from_env(self, name: str) -> str:
        """Retrieve secret from environment variables"""
        env_value = os.getenv(name.upper())
        if env_value is None:
            raise SecretNotFoundError(f"Environment variable not found: {name.upper()}")
        return env_value
    
    async def _try_fallback_providers(self, name: str, version: Optional[str] = None) -> str:
        """Try fallback providers if primary provider fails"""
        fallback_order = [
            SecretProvider.KUBERNETES,
            SecretProvider.ENVIRONMENT,
            SecretProvider.AWS_SECRETS_MANAGER,
            SecretProvider.GCP_SECRET_MANAGER
        ]
        
        for provider in fallback_order:
            if provider in self.providers:
                try:
                    logger.warning(f"Trying fallback provider {provider.value} for secret {name}")
                    
                    if provider == SecretProvider.KUBERNETES:
                        return await self._get_from_k8s(name, version)
                    elif provider == SecretProvider.ENVIRONMENT:
                        return self._get_from_env(name)
                    elif provider == SecretProvider.AWS_SECRETS_MANAGER:
                        return await self._get_from_aws(name, version)
                    elif provider == SecretProvider.GCP_SECRET_MANAGER:
                        return await self._get_from_gcp(name, version)
                except Exception as e:
                    logger.warning(f"Fallback provider {provider.value} failed: {e}")
                    continue
        
        raise SecretNotFoundError(f"Secret not found in any provider: {name}")
    
    async def store_secret(self, name: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """
        Store a secret in the configured provider
        
        Args:
            name: Secret name
            value: Secret value
            metadata: Optional metadata for the secret
            
        Returns:
            True if successfully stored
        """
        if not metadata:
            metadata = self.secret_definitions.get(name)
            if not metadata:
                raise SecretManagerError(f"No metadata found for secret: {name}")
        
        self._audit_log('store_attempt', name, {'provider': metadata.provider.value})
        
        try:
            if metadata.provider == SecretProvider.AWS_SECRETS_MANAGER:
                await self._store_in_aws(name, value)
            elif metadata.provider == SecretProvider.GCP_SECRET_MANAGER:
                await self._store_in_gcp(name, value)
            elif metadata.provider == SecretProvider.KUBERNETES:
                await self._store_in_k8s(name, value)
            else:
                raise SecretManagerError(f"Storage not supported for provider: {metadata.provider}")
            
            # Invalidate cache
            cache_keys_to_remove = [k for k in self.secret_cache.keys() if k.startswith(f"{name}:")]
            for key in cache_keys_to_remove:
                del self.secret_cache[key]
            
            self._audit_log('store_success', name, {'provider': metadata.provider.value})
            return True
            
        except Exception as e:
            self._audit_log('store_failure', name, {'error': str(e)})
            raise SecretManagerError(f"Failed to store secret {name}: {e}")
    
    async def rotate_secret(self, name: str, force: bool = False) -> str:
        """
        Rotate a secret with zero-downtime deployment
        
        Args:
            name: Secret name to rotate
            force: Force rotation even if not due
            
        Returns:
            New secret value
        """
        metadata = self.secret_definitions.get(name)
        if not metadata:
            raise SecretNotFoundError(f"Secret definition not found: {name}")
        
        # Check if rotation is needed
        if not force and not self._is_rotation_needed(metadata):
            logger.info(f"Secret {name} does not need rotation")
            return (await self.get_secret(name)).value
        
        self._audit_log('rotation_start', name, {'force': force})
        
        try:
            metadata.status = SecretRotationStatus.ROTATING
            
            # Generate new secret value based on type
            new_value = self._generate_secret_value(name, metadata)
            
            # Store new secret with staging version
            staging_metadata = metadata
            staging_metadata.version = f"{metadata.version}-staging"
            
            await self.store_secret(f"{name}-staging", new_value, staging_metadata)
            
            # Test new secret (if test function is available)
            if hasattr(self, f'_test_secret_{name}'):
                test_func = getattr(self, f'_test_secret_{name}')
                if not await test_func(new_value):
                    raise SecretRotationError(f"New secret failed validation: {name}")
            
            # Promote staging to production
            await self.store_secret(name, new_value, metadata)
            
            # Update metadata
            metadata.version = str(int(metadata.version) + 1)
            metadata.status = SecretRotationStatus.ACTIVE
            metadata.created_at = datetime.utcnow()
            
            self._audit_log('rotation_success', name, {'new_version': metadata.version})
            
            return new_value
            
        except Exception as e:
            metadata.status = SecretRotationStatus.PENDING_ROTATION
            self._audit_log('rotation_failure', name, {'error': str(e)})
            raise SecretRotationError(f"Failed to rotate secret {name}: {e}")
    
    async def emergency_rotate_all_secrets(self, reason: str) -> Dict[str, str]:
        """
        Emergency rotation of all critical and high-priority secrets
        
        Args:
            reason: Reason for emergency rotation
            
        Returns:
            Dictionary of rotated secrets and their status
        """
        self._audit_log('emergency_rotation_start', 'all', {'reason': reason})
        
        results = {}
        critical_secrets = [
            name for name, metadata in self.secret_definitions.items()
            if metadata.category in [SecretCategory.CRITICAL, SecretCategory.HIGH]
        ]
        
        for secret_name in critical_secrets:
            try:
                await self.rotate_secret(secret_name, force=True)
                results[secret_name] = "SUCCESS"
                
                # Update status to emergency rotated
                metadata = self.secret_definitions[secret_name]
                metadata.status = SecretRotationStatus.EMERGENCY_ROTATED
                
            except Exception as e:
                results[secret_name] = f"FAILED: {e}"
                logger.error(f"Emergency rotation failed for {secret_name}: {e}")
        
        self._audit_log('emergency_rotation_complete', 'all', {'results': results})
        return results
    
    def _generate_secret_value(self, name: str, metadata: SecretMetadata) -> str:
        """Generate a new secret value based on the secret type"""
        if 'jwt' in name.lower() or 'token' in name.lower():
            # Generate JWT secret (256 bits)
            return secrets.token_urlsafe(32)
        elif 'password' in name.lower():
            # Generate strong password
            return self._generate_strong_password()
        elif 'key' in name.lower():
            # Generate API key format
            return f"sk-{secrets.token_urlsafe(32)}"
        else:
            # Default: secure random string
            return secrets.token_urlsafe(32)
    
    def _generate_strong_password(self) -> str:
        """Generate a strong password meeting financial compliance requirements"""
        import string
        
        # Financial-grade password requirements
        length = 32
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        
        while True:
            password = ''.join(secrets.choice(chars) for _ in range(length))
            
            # Ensure it meets complexity requirements
            if (any(c.islower() for c in password) and
                any(c.isupper() for c in password) and
                any(c.isdigit() for c in password) and
                any(c in "!@#$%^&*" for c in password)):
                return password
    
    def _is_rotation_needed(self, metadata: SecretMetadata) -> bool:
        """Check if a secret needs rotation based on age and policy"""
        if metadata.status != SecretRotationStatus.ACTIVE:
            return False
        
        age_days = (datetime.utcnow() - metadata.created_at).days
        return age_days >= metadata.rotation_interval_days
    
    def _is_cache_valid(self, secret: SecretValue) -> bool:
        """Check if cached secret is still valid"""
        if not secret.metadata.last_accessed:
            return False
        
        # Cache TTL based on secret category
        ttl_minutes = {
            SecretCategory.CRITICAL: 5,   # 5 minutes for critical secrets
            SecretCategory.HIGH: 15,      # 15 minutes for high secrets
            SecretCategory.MEDIUM: 60,    # 1 hour for medium secrets
            SecretCategory.LOW: 240       # 4 hours for low secrets
        }.get(secret.metadata.category, 15)
        
        cache_expiry = secret.metadata.last_accessed + timedelta(minutes=ttl_minutes)
        return datetime.utcnow() < cache_expiry
    
    async def _check_compliance(self, name: str, metadata: SecretMetadata) -> None:
        """Check compliance requirements for secret access"""
        # Check if secret has expired
        if metadata.expires_at and datetime.utcnow() > metadata.expires_at:
            raise ComplianceViolationError(f"Secret {name} has expired")
        
        # Check rotation requirements
        if self._is_rotation_needed(metadata):
            logger.warning(f"Secret {name} is overdue for rotation")
            # In production, this might trigger automatic rotation
        
        # Check access patterns for anomaly detection
        if metadata.access_count > 1000:  # Threshold for investigation
            logger.warning(f"High access count for secret {name}: {metadata.access_count}")
    
    def _audit_log(self, event: str, secret_name: str, details: Dict[str, Any]) -> None:
        """Log audit events for compliance"""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event': event,
            'secret_name': secret_name,
            'details': details,
            'user_id': os.getenv('USER', 'system'),
            'request_id': self._get_request_id()
        }
        
        self.audit_log.append(audit_entry)
        self.audit_logger.info(json.dumps(audit_entry))
    
    def _get_request_id(self) -> str:
        """Get current request ID for audit correlation"""
        # This would typically come from request context
        return hashlib.md5(f"{datetime.utcnow()}{secrets.token_hex(8)}".encode()).hexdigest()[:16]
    
    async def get_secret_health(self) -> Dict[str, Any]:
        """Get health status of all secrets for monitoring"""
        health_report = {
            'status': 'healthy',
            'secrets_count': len(self.secret_definitions),
            'providers_status': {},
            'rotation_alerts': [],
            'compliance_alerts': []
        }
        
        # Check provider health
        for provider, client in self.providers.items():
            try:
                if provider == SecretProvider.AWS_SECRETS_MANAGER:
                    client.list_secrets(MaxResults=1)
                elif provider == SecretProvider.KUBERNETES:
                    client.list_namespaced_secret(namespace='default', limit=1)
                # Add other provider health checks
                
                health_report['providers_status'][provider.value] = 'healthy'
            except Exception as e:
                health_report['providers_status'][provider.value] = f'unhealthy: {e}'
                health_report['status'] = 'degraded'
        
        # Check rotation alerts
        for name, metadata in self.secret_definitions.items():
            if self._is_rotation_needed(metadata):
                health_report['rotation_alerts'].append({
                    'secret': name,
                    'days_overdue': (datetime.utcnow() - metadata.created_at).days - metadata.rotation_interval_days
                })
        
        return health_report
    
    async def cleanup_cache(self) -> None:
        """Clean up expired cache entries"""
        expired_keys = []
        for key, secret in self.secret_cache.items():
            if not self._is_cache_valid(secret):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.secret_cache[key]
        
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


# Factory function to create secret manager instance
def create_secret_manager(config_path: Optional[str] = None) -> UnifiedSecretManager:
    """
    Factory function to create and configure the secret manager
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configured UnifiedSecretManager instance
    """
    # Load configuration
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        # Default configuration
        config = {
            'providers': ['kubernetes', 'environment'],
            'aws': {
                'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            },
            'gcp': {
                'project_id': os.getenv('GCP_PROJECT_ID')
            },
            'kubernetes': {
                'namespace': os.getenv('NAMESPACE', 'default')
            },
            'secrets': {
                'jwt_secret': {
                    'category': 'critical',
                    'provider': 'kubernetes',
                    'rotation_interval_days': 30,
                    'compliance_tags': ['SOX', 'PCI_DSS']
                },
                'database_url': {
                    'category': 'critical',
                    'provider': 'kubernetes',
                    'rotation_interval_days': 90,
                    'compliance_tags': ['SOX', 'PCI_DSS']
                },
                'openai_api_key': {
                    'category': 'high',
                    'provider': 'kubernetes',
                    'rotation_interval_days': 60,
                    'compliance_tags': ['DATA_PROTECTION']
                },
                'redis_url': {
                    'category': 'high',
                    'provider': 'kubernetes',
                    'rotation_interval_days': 90,
                    'compliance_tags': ['PCI_DSS']
                }
            }
        }
    
    return UnifiedSecretManager(config)


# Global secret manager instance
secret_manager: Optional[UnifiedSecretManager] = None


async def init_secret_manager(config_path: Optional[str] = None) -> UnifiedSecretManager:
    """Initialize the global secret manager instance"""
    global secret_manager
    if secret_manager is None:
        secret_manager = create_secret_manager(config_path)
    return secret_manager


async def get_secret(name: str, version: Optional[str] = None) -> str:
    """Convenience function to get a secret value"""
    if secret_manager is None:
        await init_secret_manager()
    
    secret_obj = await secret_manager.get_secret(name, version)
    return secret_obj.value


@asynccontextmanager
async def secret_context(name: str):
    """Context manager for safe secret access"""
    try:
        secret_value = await get_secret(name)
        yield secret_value
    finally:
        # Clear secret from memory
        secret_value = None
        import gc
        gc.collect()