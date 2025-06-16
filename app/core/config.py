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
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/mita"

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # Auth / JWT
    JWT_SECRET: str = "test_secret"
    # Default should be overwritten via environment variable
    SECRET_KEY: str = "change_me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenAI
    openai_api_key: str = "test"
    openai_model: str = "gpt-4o-mini"

    # Firebase
    google_application_credentials: str = ""

    # App Store (unused but required so the app doesn't crash)
    appstore_shared_secret: str = ""

    # Sentry (optional)
    sentry_dsn: str = ""

    # SMTP settings
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@example.com"

    # CORS
    # Restrict to production front-end domain(s) by default
    allowed_origins: list[str] = ["https://app.mita.finance"]

    @field_validator("allowed_origins", mode="before")
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

# Legacy support
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
