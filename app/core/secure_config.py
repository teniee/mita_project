"""
MITA Finance - Secure Configuration Management

This module provides a secure configuration system that integrates with the unified secret manager
and ensures all sensitive data is properly handled according to financial compliance requirements.

Features:
- Integration with UnifiedSecretManager for secure secret retrieval
- Environment-specific configuration loading
- Validation and compliance checking
- Fallback mechanisms for high availability
- Audit logging for all configuration access
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional, Union

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field, field_validator
except ImportError:
    from pydantic import BaseSettings, Field
    from pydantic.class_validators import validator as field_validator

from app.core.secret_manager import UnifiedSecretManager, init_secret_manager

logger = logging.getLogger(__name__)


class SecureSettings(BaseSettings):
    """
    Secure settings class that retrieves sensitive values from the secret manager
    while maintaining backward compatibility with environment variables.
    """
    
    # Environment and deployment settings
    ENVIRONMENT: str = Field(default="development", description="Deployment environment")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    # Database configuration
    DATABASE_URL: str = Field(default="", description="Database connection string")
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Get DATABASE_URL with asyncpg driver for async connections"""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    # Redis configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection string")
    REDIS_PASSWORD: str = Field(default="", description="Redis password")
    
    # Authentication and security
    JWT_SECRET: str = Field(default="", description="JWT signing secret")
    JWT_PREVIOUS_SECRET: str = Field(default="", description="Previous JWT secret for rotation")
    SECRET_KEY: str = Field(default="", description="Application secret key")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT expiration time")
    
    # External services
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model")
    
    # Firebase/Google Cloud
    GOOGLE_APPLICATION_CREDENTIALS: str = Field(default="", description="Firebase service account path")
    
    # Apple services
    APPSTORE_SHARED_SECRET: str = Field(default="", description="App Store shared secret")
    APNS_KEY: str = Field(default="", description="Apple Push Notification key")
    APNS_KEY_ID: str = Field(default="", description="Apple Push Notification key ID")
    APNS_TEAM_ID: str = Field(default="", description="Apple team ID")
    APNS_TOPIC: str = Field(default="com.mita.finance", description="Apple Push Notification topic")
    APNS_USE_SANDBOX: bool = Field(default=True, description="Use Apple sandbox environment")
    
    # Email configuration
    SMTP_HOST: str = Field(default="", description="SMTP server host")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USERNAME: str = Field(default="", description="SMTP username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password")
    SMTP_FROM: str = Field(default="noreply@mita.finance", description="Email from address")
    
    # Monitoring and error tracking
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")
    
    # AWS configuration
    AWS_ACCESS_KEY_ID: str = Field(default="", description="AWS access key")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", description="AWS secret key")
    AWS_DEFAULT_REGION: str = Field(default="us-east-1", description="AWS default region")
    
    # Security settings
    ALLOWED_ORIGINS: list[str] = Field(default=["https://app.mita.finance"], description="CORS allowed origins")
    
    # Task queue configuration
    WORKER_MAX_JOBS: int = Field(default=100, description="Maximum jobs per worker")
    WORKER_JOB_TIMEOUT: int = Field(default=600, description="Job timeout in seconds")
    WORKER_HEARTBEAT_INTERVAL: int = Field(default=30, description="Worker heartbeat interval")
    TASK_RESULT_TTL: int = Field(default=86400, description="Task result TTL in seconds")
    FAILED_TASK_TTL: int = Field(default=604800, description="Failed task TTL in seconds")
    
    # Auto-scaling
    ENABLE_WORKER_AUTOSCALING: bool = Field(default=True, description="Enable worker auto-scaling")
    MIN_WORKERS_PER_QUEUE: int = Field(default=1, description="Minimum workers per queue")
    MAX_WORKERS_PER_QUEUE: int = Field(default=5, description="Maximum workers per queue")
    SCALE_UP_THRESHOLD: int = Field(default=10, description="Queue depth to scale up")
    SCALE_DOWN_THRESHOLD: int = Field(default=2, description="Queue depth to scale down")
    
    # Monitoring
    ENABLE_TASK_METRICS: bool = Field(default=True, description="Enable task metrics collection")
    METRICS_COLLECTION_INTERVAL: int = Field(default=60, description="Metrics collection interval")
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v
    
    @field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
    @classmethod
    def validate_secrets(cls, v, info):
        """Ensure critical secrets are provided in production"""
        field_name = info.field_name
        env = os.getenv("ENVIRONMENT", "development")
        
        if not v and env == "production":
            raise ValueError(f"{field_name} is required in production environment")
        
        # Generate fallback for development only
        if not v and env == "development":
            import secrets
            return secrets.token_urlsafe(32)
        return v
    
    class Config:
        env_file = ".env"
        validate_assignment = False
        extra = "ignore"


class SecureConfigManager:
    """
    Configuration manager that integrates with the secret management system
    to provide secure access to configuration values.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the secure configuration manager
        
        Args:
            config_path: Path to secret configuration file
        """
        self.config_path = config_path
        self.secret_manager: Optional[UnifiedSecretManager] = None
        self._settings: Optional[SecureSettings] = None
        self._secrets_cache: Dict[str, Any] = {}
        
        logger.info("Secure configuration manager initialized")
    
    async def init_async(self):
        """Initialize async components"""
        if self.secret_manager is None:
            self.secret_manager = await init_secret_manager(self.config_path)
        
        if self._settings is None:
            self._settings = SecureSettings()
    
    async def get_secret_value(self, key: str, fallback_env: Optional[str] = None) -> Optional[str]:
        """
        Get a secret value from the secret manager with fallback to environment
        
        Args:
            key: Secret key name
            fallback_env: Environment variable name to fall back to
            
        Returns:
            Secret value or None if not found
        """
        # Try cache first
        if key in self._secrets_cache:
            return self._secrets_cache[key]
        
        # Try secret manager
        if self.secret_manager:
            try:
                secret_value = await self.secret_manager.get_secret(key)
                self._secrets_cache[key] = secret_value.value
                return secret_value.value
            except Exception as e:
                logger.warning(f"Failed to retrieve secret {key} from manager: {e}")
        
        # Fall back to environment variable
        if fallback_env:
            env_value = os.getenv(fallback_env)
            if env_value:
                self._secrets_cache[key] = env_value
                return env_value
        
        # Try direct environment lookup
        env_value = os.getenv(key.upper())
        if env_value:
            self._secrets_cache[key] = env_value
            return env_value
        
        logger.warning(f"Secret {key} not found in any source")
        return None
    
    async def get_config(self) -> SecureSettings:
        """
        Get configuration with secrets populated from the secret manager
        
        Returns:
            SecureSettings instance with secrets populated
        """
        await self.init_async()
        
        if not self._settings:
            raise RuntimeError("Settings not initialized")
        
        # Create a copy to avoid modifying the original
        config_dict = self._settings.dict()
        
        # Enhanced secret mappings with fallback and criticality information
        secret_mappings = {
            'DATABASE_URL': {
                'secret_name': 'database_url',
                'fallback_env': 'DATABASE_URL',
                'critical': True,
                'description': 'Primary database connection string'
            },
            'REDIS_URL': {
                'secret_name': 'redis_url',
                'fallback_env': 'REDIS_URL',
                'critical': True,
                'description': 'Redis cache connection string'
            },
            'JWT_SECRET': {
                'secret_name': 'jwt_secret',
                'fallback_env': 'JWT_SECRET',
                'critical': True,
                'description': 'JWT signing secret key'
            },
            'SECRET_KEY': {
                'secret_name': 'secret_key',
                'fallback_env': 'SECRET_KEY',
                'critical': True,
                'description': 'Application encryption secret key'
            },
            'JWT_PREVIOUS_SECRET': {
                'secret_name': 'jwt_previous_secret',
                'fallback_env': 'JWT_PREVIOUS_SECRET',
                'critical': False,
                'description': 'Previous JWT secret for token migration'
            },
            'REDIS_PASSWORD': {
                'secret_name': 'redis_password',
                'fallback_env': 'REDIS_PASSWORD',
                'critical': False,
                'description': 'Redis authentication password'
            },
            'OPENAI_API_KEY': {
                'secret_name': 'openai_api_key',
                'fallback_env': 'OPENAI_API_KEY',
                'critical': False,
                'description': 'OpenAI API key for AI features'
            },
            'SENTRY_DSN': {
                'secret_name': 'sentry_dsn',
                'fallback_env': 'SENTRY_DSN',
                'critical': False,
                'description': 'Sentry DSN for error monitoring'
            }
        }
        
        # Track secrets retrieval for audit and monitoring
        secret_retrieval_stats = {
            'total_secrets': len(secret_mappings),
            'retrieved_from_manager': 0,
            'retrieved_from_env': 0,
            'failed_retrievals': 0,
            'critical_failures': []
        }
        
        # Populate secrets from secret manager with enhanced error handling
        for config_key, secret_config in secret_mappings.items():
            secret_name = secret_config['secret_name']
            fallback_env = secret_config['fallback_env']
            is_critical = secret_config['critical']
            
            try:
                secret_value = await self.get_secret_value(secret_name, fallback_env)
                
                if secret_value:
                    config_dict[config_key] = secret_value
                    
                    # Track source without logging secret values
                    if secret_value == os.getenv(fallback_env):
                        logger.debug(f"Secret {secret_name} retrieved from environment variable")
                        secret_retrieval_stats['retrieved_from_env'] += 1
                    else:
                        logger.debug(f"Secret {secret_name} retrieved from secret manager")
                        secret_retrieval_stats['retrieved_from_manager'] += 1
                else:
                    secret_retrieval_stats['failed_retrievals'] += 1
                    
                    if is_critical and self._settings.ENVIRONMENT == "production":
                        secret_retrieval_stats['critical_failures'].append({
                            'secret_name': secret_name,
                            'config_key': config_key,
                            'description': secret_config['description']
                        })
                        logger.error(f"Critical secret {secret_name} not available in production")
                    else:
                        logger.warning(f"Non-critical secret {secret_name} not available")
                        
            except Exception as e:
                logger.error(f"Failed to retrieve secret {secret_name}: {e}")
                secret_retrieval_stats['failed_retrievals'] += 1
                
                if is_critical and self._settings.ENVIRONMENT == "production":
                    secret_retrieval_stats['critical_failures'].append({
                        'secret_name': secret_name,
                        'config_key': config_key,
                        'error': str(e),
                        'description': secret_config['description']
                    })
        
        # Log summary of secret retrieval (without exposing values)
        logger.info(f"Secret retrieval summary: {secret_retrieval_stats['retrieved_from_manager']} from manager, "
                   f"{secret_retrieval_stats['retrieved_from_env']} from environment, "
                   f"{secret_retrieval_stats['failed_retrievals']} failed")
        
        # Fail fast for critical secret failures in production
        if secret_retrieval_stats['critical_failures'] and self._settings.ENVIRONMENT == "production":
            critical_secret_names = [failure['secret_name'] for failure in secret_retrieval_stats['critical_failures']]
            raise RuntimeError(f"Critical secrets unavailable in production: {', '.join(critical_secret_names)}")
        
        # Store retrieval stats for health monitoring
        self._secret_retrieval_stats = secret_retrieval_stats
        
        # Create new settings instance with populated secrets
        populated_settings = SecureSettings(**config_dict)
        
        return populated_settings
    
    def _ensure_secret_file_paths(self, config_dict: Dict[str, Any]) -> None:
        """
        Ensure file-based secrets have proper file paths and exist
        
        Args:
            config_dict: Configuration dictionary to validate
        """
        file_based_secrets = {
            'GOOGLE_APPLICATION_CREDENTIALS': '/app/secrets/firebase-service-account.json',
            'APNS_KEY': '/app/secrets/apns-key.p8'
        }
        
        for config_key, default_path in file_based_secrets.items():
            if config_key in config_dict:
                file_path = config_dict[config_key]
                
                # If the value looks like file content (JSON or PEM), create the file
                if config_key == 'GOOGLE_APPLICATION_CREDENTIALS' and file_path.startswith('{'):
                    # This is JSON content, write to file
                    os.makedirs(os.path.dirname(default_path), exist_ok=True)
                    with open(default_path, 'w') as f:
                        f.write(file_path)
                    config_dict[config_key] = default_path
                    logger.info(f"Created Firebase service account file at {default_path}")
                
                elif config_key == 'APNS_KEY' and '-----BEGIN PRIVATE KEY-----' in file_path:
                    # This is PEM content, write to file
                    os.makedirs(os.path.dirname(default_path), exist_ok=True)
                    with open(default_path, 'w') as f:
                        f.write(file_path)
                    config_dict[config_key] = default_path
                    logger.info(f"Created APNS key file at {default_path}")
    
    def get_secret_retrieval_stats(self) -> Dict[str, Any]:
        """
        Get statistics about secret retrieval for monitoring
        
        Returns:
            Dictionary containing secret retrieval statistics
        """
        return getattr(self, '_secret_retrieval_stats', {
            'total_secrets': 0,
            'retrieved_from_manager': 0,
            'retrieved_from_env': 0,
            'failed_retrievals': 0,
            'critical_failures': []
        })
    
    async def validate_configuration(self) -> Dict[str, str]:
        """
        Validate the complete configuration and return any issues
        
        Returns:
            Dictionary of validation issues
        """
        issues = {}
        config = await self.get_config()
        
        # Critical secrets validation
        critical_secrets = {
            'DATABASE_URL': 'Database connection required',
            'JWT_SECRET': 'JWT secret required for authentication',
            'SECRET_KEY': 'Application secret key required'
        }
        
        for field, message in critical_secrets.items():
            value = getattr(config, field, "")
            if not value and config.ENVIRONMENT == "production":
                issues[field] = message
        
        # Connection validation
        try:
            # Validate database URL format
            if config.DATABASE_URL:
                if not any(config.DATABASE_URL.startswith(proto) for proto in ['postgresql://', 'postgres://']):
                    issues['DATABASE_URL'] = 'Invalid database URL format'
            
            # Validate Redis URL format
            if config.REDIS_URL and not config.REDIS_URL.startswith('redis://'):
                issues['REDIS_URL'] = 'Invalid Redis URL format'
            
        except Exception as e:
            issues['CONNECTION_VALIDATION'] = f'Connection validation failed: {e}'
        
        return issues
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the configuration system
        
        Returns:
            Health status information
        """
        status = {
            'status': 'healthy',
            'secret_manager_available': self.secret_manager is not None,
            'secrets_cache_size': len(self._secrets_cache),
            'configuration_valid': True,
            'issues': []
        }
        
        try:
            # Validate configuration
            issues = await self.validate_configuration()
            if issues:
                status['issues'] = issues
                status['configuration_valid'] = False
                if any(key in issues for key in ['DATABASE_URL', 'JWT_SECRET', 'SECRET_KEY']):
                    status['status'] = 'unhealthy'
                else:
                    status['status'] = 'degraded'
            
            # Check secret manager health
            if self.secret_manager:
                secret_health = await self.secret_manager.get_secret_health()
                status['secret_manager_health'] = secret_health
                if secret_health['status'] != 'healthy':
                    status['status'] = 'degraded'
            
        except Exception as e:
            status['status'] = 'unhealthy'
            status['error'] = str(e)
            logger.error(f"Configuration health check failed: {e}")
        
        return status
    
    def clear_cache(self):
        """Clear the secrets cache"""
        self._secrets_cache.clear()
        logger.info("Secrets cache cleared")


# Global configuration manager instance
_config_manager: Optional[SecureConfigManager] = None


async def get_config_manager(config_path: Optional[str] = None) -> SecureConfigManager:
    """
    Get or create the global configuration manager
    
    Args:
        config_path: Path to secret configuration file
        
    Returns:
        SecureConfigManager instance
    """
    global _config_manager
    
    if _config_manager is None:
        _config_manager = SecureConfigManager(config_path)
        await _config_manager.init_async()
    
    return _config_manager


async def get_secure_settings(config_path: Optional[str] = None) -> SecureSettings:
    """
    Get secure settings with all secrets populated
    
    Args:
        config_path: Path to secret configuration file
        
    Returns:
        SecureSettings instance with secrets
    """
    config_manager = await get_config_manager(config_path)
    return await config_manager.get_config()


# Cached settings instance
_cached_settings: Optional[SecureSettings] = None


@lru_cache(maxsize=1)
def get_cached_settings() -> SecureSettings:
    """
    Get cached settings (synchronous, for backward compatibility)
    
    Note: This returns settings without secret manager integration.
    For production use, prefer get_secure_settings() which is async.
    
    Returns:
        Basic SecureSettings instance
    """
    global _cached_settings
    
    if _cached_settings is None:
        _cached_settings = SecureSettings()
    
    return _cached_settings


# For backward compatibility
def get_settings() -> SecureSettings:
    """Backward compatibility function"""
    return get_cached_settings()


# Validation function for production deployment
async def validate_production_configuration(config_path: Optional[str] = None) -> None:
    """
    Validate configuration for production deployment
    
    Args:
        config_path: Path to secret configuration file
        
    Raises:
        RuntimeError: If critical configuration is missing or invalid
    """
    config_manager = await get_config_manager(config_path)
    issues = await config_manager.validate_configuration()
    
    if issues:
        critical_issues = [
            f"{field}: {message}" 
            for field, message in issues.items() 
            if field in ['DATABASE_URL', 'JWT_SECRET', 'SECRET_KEY']
        ]
        
        if critical_issues:
            raise RuntimeError(
                f"Critical configuration issues found:\n" + 
                "\n".join(f"- {issue}" for issue in critical_issues)
            )
        
        # Log non-critical issues as warnings
        for field, message in issues.items():
            if field not in ['DATABASE_URL', 'JWT_SECRET', 'SECRET_KEY']:
                logger.warning(f"Configuration issue - {field}: {message}")


# Legacy settings for backward compatibility
try:
    settings = get_cached_settings()
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = settings.ALGORITHM
except Exception as e:
    logger.error(f"Failed to load legacy settings: {e}")
    # Create minimal fallback
    SECRET_KEY = ""
    ALGORITHM = "HS256"