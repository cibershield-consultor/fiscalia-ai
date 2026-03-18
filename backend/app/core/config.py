from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # IA
    GROQ_API_KEY: str = "your-groq-api-key"

    # Seguridad
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    # Admin (para dar/quitar Premium manualmente)
    ADMIN_SECRET_KEY: str = "cambia-esta-clave-admin-secreta"

    # Base de datos
    DATABASE_URL: str = "sqlite+aiosqlite:///./fiscalia.db"

    # Stripe (opcional — solo si activas pagos)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID: Optional[str] = None

    # Trial gratuito al registrarse
    FREE_TRIAL_DAYS: int = 7

    class Config:
        env_file = ".env"


settings = Settings()
