"""TelegramOllama API Configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields from .env
    )
    
    DB_PATH: str = "/app/db/shifts.db"  # FIXED: Aligned with Alembic migrations path (was /app/data/workledger.db)
    AGENT_URL: str = "http://127.0.0.1:8080"
    TZ: str = "Asia/Jerusalem"
    
    # TD-B2: Shift duration threshold
    MIN_SHIFT_DURATION_S: int = 60
    
    # TD-A2: Admin auth
    INTERNAL_ADMIN_SECRET: str | None = None
    ADMIN_USER_HEADER: str = "X-Admin-User"  # I1: Optional user tracking header
    
    # Test mode (E2E/CI)
    IS_TEST_MODE: bool = False  # Enable test-only endpoints (CI-24)
    
    # OCR settings (Phase 13 Task 4)
    OCR_ENABLED: bool = False
    OCR_TESSERACT_PATH: str | None = None
    OCR_LANGS: str = "eng+rus"
    OCR_MIN_CONF: int = 55
    REQUIRE_PHOTO_OVER: float = 1000.0


settings = Settings()
