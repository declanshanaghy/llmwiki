from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    DATABASE_URL: str
    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""
    VOYAGE_API_KEY: str = ""
    TURBOPUFFER_API_KEY: str = ""
    EMBEDDING_MODEL: str = "voyage-4-lite"
    EMBEDDING_DIM: int = 512
    LOGFIRE_TOKEN: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "supavault-documents"
    MISTRAL_API_KEY: str = ""
    PDF_BACKEND: str = "pdf_oxide"  # "pdf_oxide" or "mistral"
    STAGE: str = "dev"
    APP_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    QUOTA_MAX_PAGES: int = 999_999_999  # per-user page limit (effectively unlimited)
    QUOTA_MAX_PAGES_PER_DOC: int = 999_999_999  # max pages per single document (effectively unlimited)
    QUOTA_MAX_STORAGE_BYTES: int = 999_999_999_999  # ~1 TB per user (effectively unlimited)

    CONVERTER_URL: str = ""
    CONVERTER_SECRET: str = ""

    GLOBAL_OCR_ENABLED: bool = True
    GLOBAL_MAX_PAGES: int = 999_999_999  # effectively unlimited
    GLOBAL_MAX_USERS: int = 999_999_999  # effectively unlimited

    SENTRY_DSN: str = ""

    CONFLUENCE_BASE_URL: str = ""
    CONFLUENCE_EMAIL: str = ""
    CONFLUENCE_API_TOKEN: str = ""
    CONFLUENCE_SYNC_ENABLED: bool = True
    CONFLUENCE_SYNC_INTERVAL: int = 300          # seconds between sync polls
    CONFLUENCE_SYNC_BATCH_SIZE: int = 20         # pages checked per cycle

    WORKER_POLL_INTERVAL: int = 5                # seconds between queue polls
    WORKER_MAX_CONCURRENT: int = 3               # max parallel document processing
    WORKER_STALE_TIMEOUT: int = 900              # 15 min — reset processing jobs older than this


settings = Settings()
