from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Proveedor IA: "groq" (gratis) | "gemini" (gratis) | "openai" (de pago)
    AI_PROVIDER: str = "groq"

    # Claves API — solo necesitas la del proveedor que uses
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # App
    SECRET_KEY: str = "cambia-esto-en-produccion"
    DATABASE_URL: str = "sqlite+aiosqlite:///./fiscalia.db"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()
