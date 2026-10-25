from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # SQLite locally; docker-compose sets a postgresql:// URL
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    APP_ENV: str = "development"
    CORS_ORIGINS: str = '["http://localhost:3000"]'
    GEMINI_API_KEY: str = ""
    HF_TOKEN: str = ""

    # Max AI requests (lessons, doubts, quizzes, uploads, library search) per user per minute; 0 = off
    AI_RATE_LIMIT_PER_MINUTE: int = 30

    # Gemini models (see https://ai.google.dev/gemini-api/docs/models)
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"       # teaching, quizzes, notes (3.8-flash took ~90s per reply)
    GEMINI_FAST_MODEL: str = "gemini-3.5-flash-lite"  # query rewriting, small tasks
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBED_DIM: int = 768

    # RAG pipeline
    RAG_CHUNK_SIZE: int = 1000       # characters per chunk
    RAG_CHUNK_OVERLAP: int = 150
    RAG_TOP_K: int = 5               # chunks injected into the prompt
    RAG_CANDIDATES: int = 20         # per-retriever candidates before fusion
    RAG_MAX_UPLOAD_MB: int = 20

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }


settings = Settings()