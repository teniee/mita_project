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
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth / JWT - MUST be provided via environment variables for security
    JWT_SECRET: str
    JWT_PREVIOUS_SECRET: str = ""
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenAI - MUST be provided via environment variable
    OPENAI_API_KEY: str
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

    # CORS - Allow configuration via environment
    ALLOWED_ORIGINS: list[str] = ["https://app.mita.finance"]
    
    # Environment settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    if ConfigDict:
        model_config = ConfigDict(env_file=".env")
    else:  # pragma: no cover - pydantic v1 fallback

        class Config:
            env_file = ".env"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()

# Legacy support - maintain backward compatibility
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

# Validation function to ensure critical settings are provided
def validate_required_settings():
    """Validate that all required environment variables are set"""
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
            f"Please check your .env file or environment configuration."
        )

# Validate settings on import
try:
    validate_required_settings()
except ValueError as e:
    print(f"Configuration Error: {e}")
    # In development, we can continue with warnings
    if settings.ENVIRONMENT == "production":
        raise
