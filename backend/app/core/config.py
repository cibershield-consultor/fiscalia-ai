"""
FiscalIA — Configuration with validation
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    # AI
    GROQ_API_KEY: str = "your-groq-api-key"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Admin
    ADMIN_SECRET_KEY: str = "cambia-esta-clave-admin-secreta"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./fiscalia.db"

    # Stripe (optional)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID: Optional[str] = None

    # Trial
    FREE_TRIAL_DAYS: int = 7

    # Environment
    ENVIRONMENT: str = "production"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        if v in ("your-secret-key-change-in-production", "", "secret", "changeme"):
            # Allow in development but warn
            import warnings
            warnings.warn(
                "⚠️  SECRET_KEY is using default value. Set a strong random key in production!",
                UserWarning, stacklevel=2
            )
        if len(v) < 16:
            raise ValueError("SECRET_KEY must be at least 16 characters")
        return v

    @field_validator("GROQ_API_KEY")
    @classmethod
    def groq_key_must_be_set(cls, v: str) -> str:
        if v in ("your-groq-api-key", "", "none"):
            import warnings
            warnings.warn("⚠️  GROQ_API_KEY not set — AI features will not work!", UserWarning, stacklevel=2)
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
