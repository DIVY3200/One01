# 🚀 One01 — Adaptive AI Teaching Platform

[![CI](https://github.com/DIVY3200/One01/actions/workflows/ci.yml/badge.svg)](https://github.com/DIVY3200/One01/actions/workflows/ci.yml)

> Your personal AI-powered learning companion powered by a multi-agent system.

**Live demo:** https://one01.vercel.app (free hosting: after about 15 idle minutes the first request can take up to a minute)

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
  - Tracks learning progress, quiz average and study time

- 💬 **Real-time AI Chat**
  - Interactive learning with token-by-token streaming from Gemini

- 🔎 **RAG Study Library**
  - Upload PDFs, Markdown or text; the tutor retrieves from them and cites the exact passage `[1]`
  - Hybrid retrieval (semantic vectors + BM25 keywords) fused with Reciprocal Rank Fusion
  - Lesson memory: every finished lesson is indexed, so later answers build on what you were taught
  - "Ask your library" mode answers strictly from your documents

---

## 🏗️ System Architecture

```
Browser
   │  HTTPS
   ▼
Next.js 14 frontend (Vercel)            React · TypeScript · Tailwind CSS · Zustand
   │  REST + Server-Sent Events, JWT in the Authorization header
   ▼
FastAPI backend (Render, Docker)
   ├─ Middleware   CORS allow-list · "sample content" warning header
   ├─ Routes       auth · subjects · topics · chat (SSE) · quiz · notes · progress · feedback · rag
   │                 every route: JWT auth → ownership check → per-user AI rate limit
   ├─ Agents       Professor · Tutor · Examiner · Scribe ───────────────► Google Gemini API
   ├─ RAG          ingest → chunk → embed → hybrid search (BM25 + vectors) ─► Gemini embeddings
   └─ Data         SQLAlchemy (async) · Alembic migrations
   ▼
PostgreSQL (Neon) in production · SQLite for local development
```

| Layer | Folder | Responsibility |
|------|------|------|
| API | `backend/api/routes/` | HTTP and streaming (SSE) endpoints |
| Agents | `backend/agents/` | Prompts, persona handling and fallbacks for the four agents |
| AI client | `backend/llm/gemini.py` | Gemini generation, token streaming and embeddings |
| RAG | `backend/rag/` | Document ingestion, chunking, embeddings, hybrid retrieval |
| Data | `backend/db/`, `backend/migrations/` | Models, async engine, versioned schema migrations |
| Cross-cutting | `backend/utils/` | Auth, ownership checks, rate limiting, settings |
| Frontend | `frontend/src/` | Pages, chat, quiz, notes, library and progress UI |

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

Without a `GEMINI_API_KEY` everything still runs: the agents use mock content (flagged in the UI as sample content) and retrieval falls back to BM25 keyword search.

---

## 🧪 Testing

**87 automated tests** (pytest) run on every push. They use a temporary SQLite database and a fake Gemini, so they are fast, free and need no API key.

| Suite | Type | What it checks | Tests |
|------|------|------|------|
| `test_security.py` | Security / integration | 22 cross-user attacks on every route return 404; owners keep access; CORS allow-list | 30 |
| `test_navigation.py` | Unit + integration | "next" commands advance the lesson, questions get answered | 19 |
| `test_rag.py` | Integration | PDF/MD/TXT upload, bad files rejected, keyword and hybrid search, cited answers, lesson memory, query rewriting | 13 |
| `test_ingest.py` | Unit | Chunk size and overlap, Markdown headings, PDF pages | 6 |
| `test_progress.py` | Integration | Quiz average, subject-wide quizzes, study-time tracking, saved lesson notes | 6 |
| `test_limits_and_fallback.py` | Integration | Rate limit (429 + Retry-After), sample-content warnings | 5 |
| `test_gemini_client.py` | Contract | Real Gemini SDK against a local mock server: request format, streaming, batching, failure fallbacks | 4 |
| `test_migrations.py` | Migration | Fresh database matches the models; old databases are adopted without data loss; Postgres URL handling | 3 |
| `test_cleanup.py` | Integration | Deleting a subject removes every related row | 1 |

**Techniques:** shared fixtures (`tests/conftest.py`), a deterministic `FakeGemini` swapped in with monkeypatch, a mock HTTP server for the SDK contract tests, an isolated temporary database per run, and a regression test for every bug that was fixed.

**Frontend checks:** TypeScript type check (`tsc --noEmit`), ESLint (`next/core-web-vitals`), and a production build on every Vercel deploy.

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests -q
```

---

## 🔄 CI/CD Pipeline

```
git push → GitHub (main)
   │
   ├─► GitHub Actions CI  (.github/workflows/ci.yml)
   │      ├─ Backend job:  Python 3.11 → pip install → pytest (87 tests)
   │      └─ Frontend job: Node 20 → npm ci → tsc --noEmit → ESLint
   │
   ├─► Render (backend)   deploys only after CI passes (autoDeployTrigger: checksPass)
   │      Docker build → start → Alembic migrations → /health check → live
   │
   └─► Vercel (frontend)  next build → live at https://one01.vercel.app
```

- **Continuous integration:** every push and pull request runs the backend tests and the frontend type check and lint.
- **Continuous deployment:** Render redeploys the backend once the CI checks pass; Vercel rebuilds the frontend on every push.
- **Infrastructure as code:** `render.yaml` defines the service, region, health check and environment variables; `backend/Dockerfile` defines the image.
- **Database changes:** Alembic migrations run automatically when the backend starts.
- **Secrets:** kept in environment variables, never in git (`.env` is ignored, `.dockerignore` keeps it out of the image, Render generates `SECRET_KEY`).

---

## 📋 SDLC

How this project was planned, built and shipped:

| Phase | What was done |
|------|------|
| Requirements & analysis | Audited the codebase and ranked the gaps by severity: cross-user data access, broken features (lesson notes, quiz average, feedback history), no tests, no CI |
| Design | Chose hybrid retrieval (BM25 + vectors) for RAG, one shared ownership-check layer for all routes, Alembic migrations that adopt existing databases, and an explicit warning path when the AI falls back to sample content |
| Implementation | FastAPI backend and typed Next.js frontend, configuration through environment variables, changes tracked in versioned commits on GitHub |
| Testing | A regression test for each fixed bug, security tests for every route, migration tests, and live checks against the real Gemini API |
| Deployment | Docker image, Render Blueprint (infrastructure as code), Vercel, Neon Postgres; step-by-step guide in [DEPLOY.md](https://github.com/DIVY3200/One01/blob/main/DEPLOY.md) |
| Maintenance | Versioned migrations, `/health` endpoint, startup warning for a missing `SECRET_KEY`, troubleshooting table in DEPLOY.md |

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

### AI
- Google Gemini via the `google-genai` SDK (`gemini-3.5-flash-lite` for teaching and query rewriting)
- Gemini embeddings (`gemini-embedding-001`) + NumPy vector search
- BM25 keyword search + Reciprocal Rank Fusion (hybrid retrieval)
- pypdf for document ingestion
- Hugging Face `bart-large-mnli` for chat intent detection (optional)

### Database
- PostgreSQL (Neon in production, Docker locally) or SQLite for local development, chosen by `DATABASE_URL`
- Schema managed by Alembic (`backend/migrations`), applied automatically at startup

### Testing & DevOps
- pytest, FastAPI TestClient, TypeScript type check, ESLint
- GitHub Actions (CI), Render and Vercel (CD), Docker, Neon

### Security
- JWT authentication with bcrypt password hashing
- Per-user data isolation on every route
- CORS allow-list and per-user AI rate limiting

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/DIVY3200/One01.git
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
See [Testing](#-testing) for what the 87 tests cover.

### Run with Docker (Postgres):
```bash
docker-compose up --build
```
Docker uses PostgreSQL instead of the local SQLite file, so it starts with an empty database.

### Deploy online
Free hosting with Neon (database), Render (backend) and Vercel (frontend): see [DEPLOY.md](https://github.com/DIVY3200/One01/blob/main/DEPLOY.md).

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
| **DATABASE_URL** | `sqlite+aiosqlite:///./test.db` locally, `postgresql://…` in Docker / production |
| **SECRET_KEY** | JWT secret (the backend warns at startup if it is missing) |
| **CORS_ORIGINS** | Allowed frontend URLs (JSON list) |


<img width="1196" height="540" alt="WhatsApp Image 2026-04-26 at 11 15 08 PM" src="https://github.com/user-attachments/assets/31d6ff97-38e5-4665-aa45-4106a7c6d8cf" />

# 💡 Future Improvements
- pgvector / dedicated vector DB for very large libraries
- OCR for scanned PDFs
- Multi-model support (Groq)
- Shared rate-limit store (Redis) when running several backend workers
- Make Vercel deployments wait for CI as well
- Advanced analytics dashboard

# 👨‍💻 Author
Divyansh Kaushal

# ⭐ Contribution
Feel free to fork, improve, and contribute!
