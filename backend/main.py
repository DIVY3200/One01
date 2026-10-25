from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json

from agents import fallback
from api.routes import auth, subjects, topics, quiz, notes, progress, feedback, chat, rag
from db.database import init_db
from llm import gemini
from rag import embeddings as rag_embeddings
from utils.config import settings


import logging

# We will load sentence-transformers in the lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Loading SentenceTransformer model...")
    try:
        from sentence_transformers import SentenceTransformer
        app.state.st_model = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        logging.error(f"Failed to load sentence-transformers: {e}")
        app.state.st_model = None
    # Local fallback for RAG embeddings when no Gemini key is set
    rag_embeddings.set_local_model(app.state.st_model)
    if gemini.is_configured():
        print(f"[AI] Gemini enabled: {settings.GEMINI_MODEL} · embeddings {settings.GEMINI_EMBED_MODEL}")
    else:
        print("[AI] GEMINI_API_KEY not set — agents use mock fallbacks, RAG uses keyword search")
    if settings.SECRET_KEY in ("", "changeme"):
        print("[SECURITY] SECRET_KEY is not set — login tokens can be forged. Set SECRET_KEY in backend/.env")
    await init_db()
    yield


app = FastAPI(
    title="One01.ai API",
    description="Agentic AI Teaching Platform",
    version="1.0.0",
    lifespan=lifespan,
)


def _cors_origins() -> list:
    """CORS_ORIGINS as a JSON list or comma-separated string."""
    raw = settings.CORS_ORIGINS.strip()
    try:
        origins = json.loads(raw)
    except json.JSONDecodeError:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
    if isinstance(origins, str):
        origins = [origins]
    # The same dev server is often opened as 127.0.0.1 instead of localhost
    origins += [o.replace("://localhost", "://127.0.0.1") for o in origins if "://localhost" in o]
    return sorted(set(origins))


app.add_middleware(fallback.FallbackHeaderMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[fallback.HEADER],  # so the frontend can show the "sample content" warning
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["Subjects"])
app.include_router(topics.router, prefix="/api/topics", tags=["Topics"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["Quiz"])
app.include_router(notes.router, prefix="/api/notes", tags=["Notes"])
app.include_router(progress.router, prefix="/api/progress", tags=["Progress"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "one01-backend", "ai": gemini.describe()}
