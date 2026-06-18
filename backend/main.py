from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json

from api.routes import auth, subjects, quiz, notes, chat
from api.routes._combined import progress_router, feedback_router, topics_router
from db.database import init_db
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
    await init_db()
    yield


app = FastAPI(
    title="One01.ai API",
    description="Agentic AI Teaching Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = json.loads(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, str) else settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["Subjects"])
app.include_router(topics_router, prefix="/api/topics", tags=["Topics"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["Quiz"])
app.include_router(notes.router, prefix="/api/notes", tags=["Notes"])
app.include_router(progress_router, prefix="/api/progress", tags=["Progress"])
app.include_router(feedback_router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "one01-backend"}