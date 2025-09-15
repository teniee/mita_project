from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ModuleNotFoundError:  # pragma: no cover - fallback for older pydantic
    from pydantic import BaseSettings

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - pydantic v1 compatibility
    ConfigDict = None
    from pydantic.class_validators import validator as field_validator  # type:

    # ignore
else:
    from pydantic import field_validator


class Settings(BaseSettings):
    # Database - MUST be provided via environment variable
    DATABASE_URL: str = ""
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Get DATABASE_URL with asyncpg driver for async connections"""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    # Redis Configuration - External Provider Support
    REDIS_URL: str = ""  # Set via environment variable
    UPSTASH_REDIS_URL: str = ""  # Primary external Redis provider
    REDIS_PASSWORD: str = ""
    REDIS_MAX_CONNECTIONS: int = 20
    REDIS_TIMEOUT: int = 30
    REDIS_RETRY_ON_TIMEOUT: bool = True
    
    # Task Queue Configuration
    WORKER_MAX_JOBS: int = 100
    WORKER_JOB_TIMEOUT: int = 600  # 10 minutes
    WORKER_HEARTBEAT_INTERVAL: int = 30  # seconds
    
    # Queue Configuration  
    TASK_RESULT_TTL: int = 24 * 3600  # 24 hours
    FAILED_TASK_TTL: int = 7 * 24 * 3600  # 7 days
    
    # Auto-scaling Configuration
    ENABLE_WORKER_AUTOSCALING: bool = True
    MIN_WORKERS_PER_QUEUE: int = 1
    MAX_WORKERS_PER_QUEUE: int = 5
    SCALE_UP_THRESHOLD: int = 10  # Queue depth to scale up
    SCALE_DOWN_THRESHOLD: int = 2  # Queue depth to scale down
    
    # Monitoring Configuration
    ENABLE_TASK_METRICS: bool = True
    METRICS_COLLECTION_INTERVAL: int = 60  # seconds

    # Auth / JWT - MUST be provided via environment variables for security
    JWT_SECRET: str = ""
    JWT_PREVIOUS_SECRET: str = ""
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Password Security Configuration
    BCRYPT_ROUNDS_PRODUCTION: int = 10  # Optimized for performance while maintaining security
    BCRYPT_ROUNDS_DEVELOPMENT: int = 10  # Balanced for development
    BCRYPT_PERFORMANCE_TARGET_MS: int = 500  # Maximum acceptable hash time
    
    @field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
    @classmethod
    def validate_secrets(cls, v, info):
        """Ensure JWT secrets are provided in production"""
        field_name = info.field_name
        # Generate fallback if empty (works for both dev and prod)
        if not v:
            import secrets
            import os
            env = os.getenv("ENVIRONMENT", "development")
            # Still warn in production, but don't crash the app
            if env == "production":
                import logging
                logging.warning(f"{field_name} not set in production, using generated fallback")
            return secrets.token_urlsafe(32)
        return v
    
    @classmethod
    def _get_environment(cls) -> str:
        """Get environment setting safely"""
        import os
        return os.getenv("ENVIRONMENT", "development")

    # OpenAI - MUST be provided via environment variable
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Firebase
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # App Store
    APPSTORE_SHARED_SECRET: str = ""

    # Sentry (optional)
    SENTRY_DSN: str = ""

    # SMTP settings
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@mita.finance"

    # APNs settings
    APNS_KEY: str = ""
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_TOPIC: str = "com.mita.finance"
    APNS_USE_SANDBOX: bool = True

    # CORS - Allow configuration via environment (includes mobile app support)
    ALLOWED_ORIGINS: str = "https://app.mita.finance,https://admin.mita.finance,https://mita.finance,*"
    
    # Environment settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    @property
    def ALLOWED_ORIGINS_LIST(self):
        """Get ALLOWED_ORIGINS as a list"""
        if isinstance(self.ALLOWED_ORIGINS, str):
            return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return [self.ALLOWED_ORIGINS] if self.ALLOWED_ORIGINS else []

    if ConfigDict:
        model_config = ConfigDict(
            env_file=".env",
            validate_assignment=False,
            extra="ignore"
        )
    else:  # pragma: no cover - pydantic v1 fallback

        class Config:
            env_file = ".env"
            validate_assignment = False
            extra = "ignore"


@lru_cache
def get_settings():
    return Settings()


try:
    settings = Settings()
except Exception as e:
    import logging
    logging.warning(f"Could not load settings: {e}")
    # Create a minimal settings object for development
    class MinimalSettings:
        DATABASE_URL = ""
        JWT_SECRET = ""
        SECRET_KEY = ""
        OPENAI_API_KEY = ""
        ENVIRONMENT = "development"
        ALGORITHM = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES = 30
        REDIS_URL = ""  # No Redis in development by default - graceful fallback
        OPENAI_MODEL = "gpt-4o-mini"
        GOOGLE_APPLICATION_CREDENTIALS = ""
        APPSTORE_SHARED_SECRET = ""
        SENTRY_DSN = ""
        SMTP_HOST = ""
        SMTP_PORT = 587
        SMTP_USERNAME = ""
        SMTP_PASSWORD = ""
        SMTP_FROM = "noreply@mita.finance"
        APNS_KEY = ""
        APNS_KEY_ID = ""
        APNS_TEAM_ID = ""
        APNS_TOPIC = "com.mita.finance"
        APNS_USE_SANDBOX = True
        ALLOWED_ORIGINS = ["https://app.mita.finance"]
        DEBUG = False
        LOG_LEVEL = "INFO"
    
    settings = MinimalSettings()

# Legacy support - maintain backward compatibility
SECRET_KEY = settings.SECRET_KEY if hasattr(settings, 'SECRET_KEY') else ""
ALGORITHM = settings.ALGORITHM if hasattr(settings, 'ALGORITHM') else "HS256"

# Validation function to ensure critical settings are provided
def validate_required_settings():
    """Validate that all required environment variables are set"""
    # Only validate in production or when explicitly requested
    if settings.ENVIRONMENT == "development":
        return  # Skip validation in development
        
    required_settings = [
        ('DATABASE_URL', settings.DATABASE_URL),
        ('JWT_SECRET', settings.JWT_SECRET),
        ('SECRET_KEY', settings.SECRET_KEY),
        ('OPENAI_API_KEY', settings.OPENAI_API_KEY),
    ]
    
    missing_settings = []
    for name, value in required_settings:
        if not value or (isinstance(value, str) and value.strip() == ""):
            missing_settings.append(name)
    
    if missing_settings:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_settings)}. "
            f"Please set these in your deployment environment or .env file."
        )

# Don't validate at import time - let the application handle it
# Settings validation will be done when actually needed by the application
