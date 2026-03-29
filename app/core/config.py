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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120  # Default 2 hours — required for onboarding completion flow
    
    # Password Security Configuration
    BCRYPT_ROUNDS_PRODUCTION: int = 10  # Optimized for performance while maintaining security
    BCRYPT_ROUNDS_DEVELOPMENT: int = 10  # Balanced for development
    BCRYPT_PERFORMANCE_TARGET_MS: int = 500  # Maximum acceptable hash time
    
    @field_validator("JWT_SECRET", "SECRET_KEY", mode="before")
    @classmethod
    def validate_secrets(cls, v, info):
        """Ensure JWT secrets are provided in production, auto-generate in development only"""
        field_name = info.field_name
        if not v:
            import os
            env = os.getenv("ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    f"{field_name} MUST be set in production. "
                    f"Generate with: openssl rand -base64 32"
                )
            # Auto-generate only in development/test for convenience
            import secrets
            return secrets.token_urlsafe(32)
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES", mode="before")
    @classmethod
    def validate_token_expiry(cls, v):
        """Validate token expiration is a positive integer.

        The configured value is respected as-is — no silent overrides.
        Default (120 min) is used only when the env var is empty or missing.
        If you need shorter tokens, set the value explicitly in your deployment config.
        """
        if v == "" or v is None:
            return 120
        expire_minutes = int(v)
        if expire_minutes <= 0:
            raise ValueError(f"ACCESS_TOKEN_EXPIRE_MINUTES must be positive, got {expire_minutes}")
        return expire_minutes

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

    @field_validator("SMTP_PORT", mode="before")
    @classmethod
    def validate_smtp_port(cls, v):
        """Handle empty SMTP_PORT from Railway"""
        if v == "" or v is None:
            return 587  # Default port
        return int(v)

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
    # SECURITY FIX: Removed wildcard (*) - only allow specific origins
    ALLOWED_ORIGINS: str = "https://app.mita.finance,https://admin.mita.finance,https://mita.finance,https://mitafinance.app,https://mitafinance.com,https://www.mitafinance.com"
    
    # Environment settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    @property
    def ALLOWED_ORIGINS_LIST(self):
        """Get ALLOWED_ORIGINS as a list. Localhost origins only in development."""
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

        # Production domains (always allowed, HTTPS only)
        always_allow = [
            "https://mitafinance.com",
            "https://www.mitafinance.com",
        ]

        # Localhost only in non-production environments
        if self.ENVIRONMENT != "production":
            always_allow.extend([
                "http://localhost:8080",
                "http://localhost:3000",
                "http://localhost:5173",
                "http://127.0.0.1:8080",
            ])

        for origin in always_allow:
            if origin not in origins:
                origins.append(origin)
        return origins

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


try:
    settings = Settings()
except Exception as e:
    import os as _os

    _is_production = (
        _os.getenv("ENVIRONMENT", "development") == "production"
        or _os.getenv("RAILWAY_ENVIRONMENT") is not None
    )
    if _is_production:
        # In production, configuration errors MUST crash the app — never fall back silently.
        # A running server with empty DATABASE_URL / JWT_SECRET is worse than a crashed one.
        # We also check RAILWAY_ENVIRONMENT because Railway always sets it on deployed
        # services — so even if someone forgets ENVIRONMENT=production, we still crash.
        raise

    # Development-only fallback: retry without .env file so pydantic defaults kick in.
    # Unlike the old MinimalSettings class, this preserves @property methods
    # (ASYNC_DATABASE_URL, ALLOWED_ORIGINS_LIST) and field validators.
    import logging as _logging

    _logging.error(
        "Settings failed to load: %s. "
        "Retrying without .env file (pydantic defaults only). "
        "Fix your .env file to silence this error.",
        e,
    )
    try:
        settings = Settings(_env_file=None)
    except Exception as e2:
        raise RuntimeError(
            f"Cannot initialize settings even with defaults: {e2}. "
            f"Original error: {e}"
        ) from e2


def get_settings():
    """Return the module-level settings singleton.

    Kept for backward compatibility with code that calls get_settings()
    (e.g. app.core.session). Always returns the same instance as the
    module-level ``settings`` — never creates a second Settings() that
    could bypass the production guard above.
    """
    return settings

# Module-level exports used by auth_jwt_service and others
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

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
