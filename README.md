# 🚀 One01 — Adaptive AI Teaching Platform

> Your personal AI-powered learning companion powered by a multi-agent system.

---

## 📌 Overview

One01 is a full-stack AI learning platform that uses a **multi-agent architecture** to deliver personalized education. It dynamically generates curriculum, explains concepts, creates quizzes, and tracks progress — all powered by modern AI models.

---

## 🧠 Key Features

- 📚 **Dynamic Curriculum Generation**
  - Automatically generates structured learning paths

- 🧑‍🏫 **AI Tutor**
  - Explains concepts with examples, analogies, and step-by-step reasoning

- 📝 **Quiz & Evaluation**
  - Generates MCQs, theory, and numerical questions
  - Identifies weak concepts

- 📓 **Smart Notes**
  - Auto-generated notes with key concepts and formulas

- 📊 **Progress Tracking**
  - Tracks learning progress and performance

- 💬 **Real-time AI Chat**
  - Interactive learning with token-by-token streaming from Gemini

- 🔎 **RAG Study Library**
  - Upload PDFs, Markdown or text; the tutor retrieves from them and cites the exact passage `[1]`
  - Hybrid retrieval (semantic vectors + BM25 keywords) fused with Reciprocal Rank Fusion
  - Lesson memory: every finished lesson is indexed, so later answers build on what you were taught
  - "Ask your library" mode answers strictly from your documents

---

## 🧩 Multi-Agent Architecture

| Agent | Role |
|------|------|
| **Professor** | Generates curriculum and topic structure |
| **Tutor** | Explains concepts and resolves doubts |
| **Examiner** | Creates quizzes and analyzes performance |
| **Scribe** | Generates notes and processes feedback |

---

## 🔎 RAG Pipeline

```
Upload (PDF / MD / TXT)            Finished lesson (auto)
        │                                   │
        ▼                                   ▼
  Extract text per page / heading  ──►  Recursive chunking (1000 chars, 150 overlap)
                                            │
                                            ▼
                     Gemini embeddings (gemini-embedding-001, 768-d, normalized)
                                            │
                                            ▼
                        documents + document_chunks tables (SQLite / Postgres)

Student question ─► query rewrite (Gemini Flash-Lite, uses chat history)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      Dense: cosine similarity      Sparse: BM25 keywords
              └─────────────┬─────────────┘
                            ▼
              Reciprocal Rank Fusion → top-k chunks
                            │
                            ▼
      Grounded prompt with numbered sources → Gemini streams answer with [n] citations
```

| Piece | File |
|------|------|
| Gemini client (generate, stream, embed) | `llm/gemini.py` |
| Loading + chunking | `rag/ingest.py` |
| Embeddings (Gemini → local MiniLM → none) | `rag/embeddings.py` |
| Hybrid retriever (BM25 + vectors + RRF) | `rag/retriever.py` |
| Ingestion, lesson memory, grounding prompts | `rag/service.py` |
| REST + SSE endpoints (`/api/rag/...`) | `api/routes/rag.py` |

Without a `GEMINI_API_KEY` everything still runs: the agents use mock content and retrieval falls back to BM25 keyword search.

---

## ⚙️ Tech Stack

### Frontend
- Next.js 14
- TypeScript
- Tailwind CSS
- Zustand

### Backend
- FastAPI
- Python 3.10–3.11 (pinned SQLAlchemy 2.0.30 does not support 3.13+)
- SQLAlchemy (Async) + Alembic migrations
- pytest test suite + GitHub Actions CI

### AI
- Google Gemini via the `google-genai` SDK (`gemini-3.5-flash-lite` for teaching and query rewriting)
- Gemini embeddings (`gemini-embedding-001`) + NumPy vector search
- BM25 keyword search + Reciprocal Rank Fusion (hybrid retrieval)
- pypdf for document ingestion
- Hugging Face `bart-large-mnli` for chat intent detection (optional)

### Database
- SQLite (local setup) / PostgreSQL (Docker), chosen by `DATABASE_URL`
- Schema managed by Alembic (`backend/migrations`), applied automatically at startup

### Others
- JWT Authentication, per-user data isolation on every route
- Per-user AI rate limiting
- Server-Sent Events (SSE)
- Docker (optional)

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/One01.git
cd One01
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Create .env file:
```bash
copy .env.example .env   # Windows (cp on macOS/Linux), then fill in:
GEMINI_API_KEY=your_api_key        # https://aistudio.google.com/apikey
SECRET_KEY=your_secret_key         # python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Run backend:
```bash
python -m uvicorn main:app --reload --port 8000
```
Database migrations run automatically on startup. After changing `db/models.py`, create a migration with
`alembic revision --autogenerate -m "describe the change"` (run inside `backend`).

### Run tests:
```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```
The tests use a temporary database and a fake Gemini, so they need no API key. GitHub Actions runs them,
plus the frontend type check and lint, on every push (`.github/workflows/ci.yml`).

### Run with Docker (Postgres):
```bash
docker-compose up --build
```
Docker uses PostgreSQL instead of the local SQLite file, so it starts with an empty database.

### Deploy online
Free hosting with Neon (database), Render (backend) and Vercel (frontend): see [DEPLOY.md](DEPLOY.md).

### 3. Frontend Setup
```bash
cd frontend
npm install
```

### Create .env.local:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Run frontend:
```bash
npm run dev
```

### 4. Open Application
```bash
 - Frontend → http://localhost:3000
 - Backend Docs → http://localhost:8000/docs
```
# 🔐 Environment Variables
| Variable | Description |
|------|------|
| **GEMINI_API_KEY** | Google AI Studio key for Gemini |
| **GEMINI_MODEL** | Main model (default `gemini-3.5-flash-lite`) |
| **GEMINI_FAST_MODEL** | Query-rewrite model (default `gemini-3.5-flash-lite`) |
| **GEMINI_EMBED_MODEL** / **GEMINI_EMBED_DIM** | Embeddings (default `gemini-embedding-001`, `768`) |
| **RAG_CHUNK_SIZE** / **RAG_CHUNK_OVERLAP** / **RAG_TOP_K** | Chunking and retrieval (default `1000` / `150` / `5`) |
| **RAG_MAX_UPLOAD_MB** | Upload size limit (default `20`) |
| **AI_RATE_LIMIT_PER_MINUTE** | AI requests per user per minute (default `30`, `0` = off) |
| **HF_TOKEN** | Optional Hugging Face token for the intent classifier |
| **DATABASE_URL** | `sqlite+aiosqlite:///./test.db` locally, `postgresql://…` in Docker |
| **SECRET_KEY** | JWT secret (the backend warns at startup if it is missing) |
| **CORS_ORIGINS** | Allowed frontend URLs (JSON list) |


<img width="1196" height="540" alt="WhatsApp Image 2026-04-26 at 11 15 08 PM" src="https://github.com/user-attachments/assets/31d6ff97-38e5-4665-aa45-4106a7c6d8cf" />

# 💡 Future Improvements
- pgvector / dedicated vector DB for very large libraries
- OCR for scanned PDFs
- Multi-model support (Groq)
- Shared rate-limit store (Redis) when running several backend workers
- Deployment on cloud platforms
- Advanced analytics dashboard

# 👨‍💻 Author
Divyansh Kaushal

# ⭐ Contribution
Feel free to fork, improve, and contribute!
