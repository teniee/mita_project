"""
MITA Finance - Clean Environment Configuration
Separated configuration system to prevent emergency/production mixing
"""
import os
from functools import lru_cache
from typing import Dict, Any, Optional

try:
    from pydantic_settings import BaseSettings
except ModuleNotFoundError:  # pragma: no cover - fallback for older pydantic
    from pydantic import BaseSettings

try:
    from pydantic import ConfigDict, field_validator
except ImportError:  # pragma: no cover - pydantic v1 compatibility
    ConfigDict = None
    from pydantic.class_validators import validator as field_validator


class EnvironmentConfig:
    """Environment-specific configuration loader"""
    
    ENVIRONMENTS = ['development', 'staging', 'production']
    
    @classmethod
    def get_environment(cls) -> str:
        """Get current environment with validation"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env not in cls.ENVIRONMENTS:
            raise ValueError(f"Invalid environment: {env}. Must be one of {cls.ENVIRONMENTS}")
        return env
    
    @classmethod
    def get_env_file_path(cls) -> str:
        """Get the appropriate .env file path for current environment"""
        env = cls.get_environment()
        env_file = f".env.{env}"
        
        # Check if clean version exists first
        clean_env_file = f".env.{env}.clean"
        if os.path.exists(clean_env_file):
            return clean_env_file
        elif os.path.exists(env_file):
            return env_file
        elif os.path.exists(".env"):
            return ".env"
        else:
            return f".env.{env}"  # Will be created if needed


class BaseEnvironmentSettings(BaseSettings):
    """Base settings class with environment-specific loading"""
    
    # Environment identification
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Database configuration - REQUIRED
    DATABASE_URL: str = ""
    
    # Redis configuration
    REDIS_URL: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_TIMEOUT: int = 30
    REDIS_RETRY_ON_TIMEOUT: bool = True
    
    # Security configuration - CRITICAL
    JWT_SECRET: str = ""
    JWT_PREVIOUS_SECRET: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # External services
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    APPSTORE_SHARED_SECRET: str = ""
    SENTRY_DSN: str = ""
    
    # SMTP configuration
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@mita.finance"
    
    # APNs configuration
    APNS_KEY: str = ""
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_TOPIC: str = "com.mita.finance"
    APNS_USE_SANDBOX: bool = True
    
    # CORS configuration
    ALLOWED_ORIGINS: list[str] = []
    
    # Infrastructure
    BACKEND_PORT: int = 8000
    
    # Task queue configuration
    WORKER_MAX_JOBS: int = 100
    WORKER_JOB_TIMEOUT: int = 600
    WORKER_HEARTBEAT_INTERVAL: int = 30
    ENABLE_WORKER_AUTOSCALING: bool = True
    ENABLE_TASK_METRICS: bool = True
    
    # Feature flags
    FEATURE_FLAGS_DEBUG_LOGGING: bool = False
    FEATURE_FLAGS_ENHANCED_RATE_LIMITING: bool = True
    FEATURE_FLAGS_CIRCUIT_BREAKER: bool = True
    FEATURE_FLAGS_ADMIN_ENDPOINTS: bool = False
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Get DATABASE_URL with asyncpg driver for async connections"""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            # Handle empty string
            if not v.strip():
                return []
            return [o.strip() for o in v.split(",") if o.strip()]
        elif isinstance(v, list):
            return v
        return []
    
    @field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
    @classmethod
    def validate_secrets(cls, v, info):
        """Ensure JWT secrets meet security requirements"""
        field_name = info.field_name
        env = EnvironmentConfig.get_environment()
        
        if not v:
            if env == "production":
                raise ValueError(f"{field_name} is REQUIRED in production environment")
            elif env == "development":
                # Generate secure fallback for development
                import secrets
                return secrets.token_urlsafe(32)
        
        if len(v) < 32:
            raise ValueError(f"{field_name} must be at least 32 characters long")
        
        return v
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration and return status"""
        errors = []
        warnings = []
        
        # Critical validations for production
        if self.ENVIRONMENT == "production":
            if not self.DATABASE_URL or "REPLACE_WITH" in self.DATABASE_URL:
                errors.append("DATABASE_URL must be set with real production credentials")
            
            if not self.JWT_SECRET or "REPLACE_WITH" in self.JWT_SECRET:
                errors.append("JWT_SECRET must be set with real production secret")
            
            if not self.SECRET_KEY or "REPLACE_WITH" in self.SECRET_KEY:
                errors.append("SECRET_KEY must be set with real production secret")
            
            if self.DEBUG:
                errors.append("DEBUG must be False in production")
            
            if self.FEATURE_FLAGS_DEBUG_LOGGING:
                errors.append("Debug logging must be disabled in production")
        
        # Security validations
        if self.JWT_SECRET and len(self.JWT_SECRET) < 32:
            errors.append("JWT_SECRET must be at least 32 characters")
        
        if self.SECRET_KEY and len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")
        
        # Environment-specific warnings
        if self.ENVIRONMENT == "development":
            if not self.OPENAI_API_KEY:
                warnings.append("OPENAI_API_KEY not set - AI features will be disabled")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "environment": self.ENVIRONMENT
        }
    
    if ConfigDict:
        model_config = ConfigDict(
            env_file=EnvironmentConfig.get_env_file_path(),
            validate_assignment=True,
            extra="ignore"
        )
    else:  # pragma: no cover - pydantic v1 fallback
        class Config:
            env_file = EnvironmentConfig.get_env_file_path()
            validate_assignment = True
            extra = "ignore"


class DevelopmentSettings(BaseEnvironmentSettings):
    """Development-specific settings with safe defaults"""
    
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Development-specific defaults
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080", 
        "http://127.0.0.1:3000",
        "http://localhost:5173"
    ]
    
    # Relaxed settings for development
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    APNS_USE_SANDBOX: bool = True
    FEATURE_FLAGS_DEBUG_LOGGING: bool = True
    FEATURE_FLAGS_ADMIN_ENDPOINTS: bool = True
    
    # Development task queue
    WORKER_MAX_JOBS: int = 10
    WORKER_JOB_TIMEOUT: int = 60
    ENABLE_WORKER_AUTOSCALING: bool = False


class StagingSettings(BaseEnvironmentSettings):
    """Staging-specific settings mimicking production"""
    
    ENVIRONMENT: str = "staging"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Staging-specific defaults
    ALLOWED_ORIGINS: list[str] = [
        "https://staging.mita.finance",
        "https://staging-admin.mita.finance"
    ]
    
    # Production-like settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    APNS_USE_SANDBOX: bool = True
    FEATURE_FLAGS_DEBUG_LOGGING: bool = False
    FEATURE_FLAGS_ADMIN_ENDPOINTS: bool = True
    
    # Staging task queue
    WORKER_MAX_JOBS: int = 50
    WORKER_JOB_TIMEOUT: int = 300
    ENABLE_WORKER_AUTOSCALING: bool = True


class ProductionSettings(BaseEnvironmentSettings):
    """Production-specific settings with maximum security"""
    
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Production-specific defaults
    ALLOWED_ORIGINS: list[str] = [
        "https://app.mita.finance",
        "https://admin.mita.finance"
    ]
    
    # Maximum security settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    APNS_USE_SANDBOX: bool = False
    FEATURE_FLAGS_DEBUG_LOGGING: bool = False
    FEATURE_FLAGS_ADMIN_ENDPOINTS: bool = True
    
    # Production task queue
    WORKER_MAX_JOBS: int = 100
    WORKER_JOB_TIMEOUT: int = 600
    ENABLE_WORKER_AUTOSCALING: bool = False  # Handled by K8s


def get_settings_class():
    """Get the appropriate settings class for current environment"""
    env = EnvironmentConfig.get_environment()
    
    settings_map = {
        "development": DevelopmentSettings,
        "staging": StagingSettings,
        "production": ProductionSettings
    }
    
    return settings_map[env]


@lru_cache
def get_settings():
    """Get cached settings instance for current environment"""
    settings_class = get_settings_class()
    return settings_class()


# Global settings instance
try:
    settings = get_settings()
    
    # Validate configuration on startup
    validation_result = settings.validate_configuration()
    if not validation_result["valid"]:
        import logging
        logging.error(f"Configuration validation failed: {validation_result['errors']}")
        if settings.ENVIRONMENT == "production":
            raise ValueError("Production configuration validation failed - cannot start")
    
    if validation_result["warnings"]:
        import logging
        for warning in validation_result["warnings"]:
            logging.warning(f"Configuration warning: {warning}")

except Exception as e:
    import logging
    logging.error(f"Failed to load settings: {e}")
    
    # Emergency fallback for development only
    if EnvironmentConfig.get_environment() == "development":
        settings = DevelopmentSettings()
    else:
        raise


# Legacy compatibility
SECRET_KEY = getattr(settings, 'SECRET_KEY', '')
ALGORITHM = getattr(settings, 'ALGORITHM', 'HS256')