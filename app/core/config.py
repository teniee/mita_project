from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ModuleNotFoundError:  # pragma: no cover - fallback for older pydantic
    from pydantic import BaseSettings

try:
    from pydantic import ConfigDict
except ImportError:  # pragma: no cover - pydantic v1 compatibility
    ConfigDict = None


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/mita"

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # Auth / JWT
    JWT_SECRET: str = "test_secret"
    SECRET_KEY: str = "default_dev_secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # OpenAI
    openai_api_key: str = "test"
    openai_model: str = "gpt-4o-mini"

    # Firebase
    google_application_credentials: str = ""

    # App Store (не используется, но нужно чтобы не падало)
    appstore_shared_secret: str = ""

    # Sentry (опционально)
    sentry_dsn: str = ""

    if ConfigDict:
        model_config = ConfigDict(env_file=".env")
    else:  # pragma: no cover - pydantic v1 fallback
        class Config:
            env_file = ".env"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()

# Для старого кода
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
