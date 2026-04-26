from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    DATABASE_URL: str = "postgresql://one01:one01_secret@postgres:5432/one01_db"
    REDIS_URL: str = "redis://redis:6379"
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    APP_ENV: str = "development"
    CORS_ORIGINS: str = '["http://localhost:3000"]'
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    HF_TOKEN: str = ""

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }


settings = Settings()