from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str = "your-groq-api-key"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    DATABASE_URL: str = "sqlite+aiosqlite:///./fiscalia.db"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()
