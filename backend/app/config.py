import sys

from pydantic_settings import BaseSettings

_UNSAFE_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    APP_NAME: str = "AI Job Matcher"
    DEBUG: bool = False

    DATABASE_URL: str = ""

    SECRET_KEY: str = _UNSAFE_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Comma-separated list of allowed CORS origins, e.g. "http://localhost:5173,https://myapp.com"

    # Comma-separated list of admin emails that can access /cortex/ingest and /cortex/jobs/cleanup
    # Leave empty to allow ALL authenticated users (only safe in dev/local setups)
    ADMIN_EMAILS: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5-nano"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    CORTEX_DATABASE_URL: str = ""  # postgresql+asyncpg://user:pass@host:5432/postgres
    REDIS_URL: str = "redis://localhost:6379/0"

    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_COUNTRY: str = "fr"

    FRANCE_TRAVAIL_CLIENT_ID: str = ""
    FRANCE_TRAVAIL_CLIENT_SECRET: str = ""

    # SMTP — leave SMTP_HOST empty for dev mode (links printed to console)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = "AILFJ"

    # Frontend base URL — used to build links in emails
    APP_URL: str = "http://localhost:5173"

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = ""  # empty = console only; set to e.g. "logs/app.log" for file output

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10

    # AWS S3 — optional, falls back to local disk when not set
    AWS_REGION: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()

if settings.SECRET_KEY == _UNSAFE_SECRET and not settings.DEBUG:
    print(
        "FATAL: SECRET_KEY is set to the default placeholder value. "
        "Set a strong random SECRET_KEY in your .env file before running in production.",
        file=sys.stderr,
    )
    sys.exit(1)