# One01 — Adaptive Agentic AI Teaching Platform

> Your personal Council of AI Agents. Learn anything, at any level, in any style.

---

## Architecture

```
One01
├── frontend/          Next.js 14 + TypeScript + Tailwind
├── backend/           FastAPI + Python + Anthropic SDK
│   └── agents/        Multi-Agent Orchestrator
│       ├── Professor  Curriculum & outline generation
│       ├── Tutor      Persona-based explanation & doubt resolution
│       ├── Examiner   Quiz generation & knowledge gap analysis
│       └── Scribe     Notes generation & feedback processing
├── docker-compose.yml Orchestrates all services
└── README.md
```

## Multi-Agent System

| Agent | Role | Trigger |
|-------|------|---------|
| **Professor** | Generates structured curriculum outline | When user creates a new subject |
| **Tutor** | Explains topics, resolves doubts, adopts persona | When user starts a lesson or asks a question |
| **Examiner** | Creates MCQ/Theory/Numerical quizzes, analyzes answers, tags weak concepts | After each topic is explained |
| **Scribe** | Writes markdown notes, processes feedback, updates teaching style | After explanations & feedback submissions |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Zustand, React Markdown + KaTeX |
| Backend | FastAPI, Python 3.11, SQLAlchemy (async) |
| AI | Anthropic Claude (claude-sonnet-4) via official SDK |
| Database | PostgreSQL 16 |
| Cache | Redis |
| Containers | Docker + Docker Compose |
| Auth | JWT (python-jose + passlib) |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose installed
- Anthropic API key ([get one here](https://console.anthropic.com))

### 1. Clone & configure

```bash
git clone <your-repo>
cd One01
```

Edit `backend/.env`:
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
SECRET_KEY=pick-a-long-random-string
```

### 2. Run with Docker

```bash
docker-compose up --build
```

That's it. Services:
- **Frontend** → http://localhost:3000
- **Backend API** → http://localhost:8000
- **API Docs** → http://localhost:8000/docs
- **PostgreSQL** → localhost:5432
- **Redis** → localhost:6379

## Full Startup Instructions

Follow these steps to get the entire One01 system up and running, covering both Docker and local development environments.

### Using Docker (recommended)
1. Ensure Docker and Docker Compose are installed.
2. Copy the example environment file and set your Anthropic API key:
   ```bash
   cp backend/.env.example backend/.env
   # edit backend/.env and set ANTHROPIC_API_KEY
   ```
3. Build and start all services:
   ```bash
   docker-compose up --build
   ```
4. The application will be available at:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Running Backend and Frontend Separately (without Docker)
#### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Now you can access the frontend at http://localhost:3000 and the backend API at http://localhost:8000.
- **Redis** → localhost:6379

### 3. First-time setup in the app

1. Go to http://localhost:3000
2. Register an account
3. Complete the 3-step onboarding (nickname, teacher name/gender, teaching style)
4. Add your first subject on the dashboard
5. The Professor Agent will generate your curriculum outline
6. Click any topic → "Begin Lesson" to start learning

---

## Development (without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env         

# Start PostgreSQL locally first, then:
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
# Create .env.local:
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

---

## Feature Walkthrough

### Onboarding
- Choose your **nickname** (how the AI addresses you)
- Name your **AI teacher** and set their pronouns
- Pick a **teaching persona**: Brother · Friend · Philosopher · Scientist · Professor · Mentor

### Adding a Subject
- Enter any topic: "Quantum Mechanics", "Machine Learning", "Roman History", etc.
- Select **purpose**: Academic / Job / Research
- Select **level**: Beginner / Intermediate / Advanced
- The **Professor Agent** generates a 8-15 topic curriculum instantly

### Learning (Chat tab)
- Select a topic from the outline
- Click **"Begin Lesson"** → Tutor Agent streams a full explanation
- Includes hooks, analogies, formulas (LaTeX), examples, and key takeaways
- Ask doubts in the chat → Tutor adapts its explanation style

### Quiz (Quiz tab)
- Generate **MCQ**, **Theory**, and/or **Numerical** question sets
- Submit answers → **Examiner Agent** scores and identifies weak concepts
- Weak concepts are automatically prioritized in future lessons

### Notes
- **Scribe Agent** auto-generates markdown notes for each topic
- Notes include definitions, formulas, key principles, and your common mistakes
- Fully **editable** in split preview/edit mode with LaTeX support

### Progress Report
- Visual completion bar
- Average quiz score tracking
- Strong concepts ✅ and weak concepts ⚠️ tracking
- Time spent tracking

### Question Bank
- Generate unlimited practice questions on demand
- Any topic, any type (MCQ/Theory/Numerical), any count
- Full solutions and explanations included

### Feedback
- Describe issues with tone, pace, clarity, depth, examples
- **Scribe Agent** processes feedback and adjusts teaching style
- AI teacher responds acknowledging the feedback

---

## Environment Variables

### Backend (`backend/.env`)

```env
ANTHROPIC_API_KEY=sk-ant-...         # Required
DATABASE_URL=postgresql://...        # Auto-set by Docker
REDIS_URL=redis://...                # Auto-set by Docker
SECRET_KEY=your-jwt-secret           # Change this!
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080    # 7 days
APP_ENV=development
CORS_ORIGINS=["http://localhost:3000"]
```

### Frontend (`frontend/.env.local` for dev)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Docker Commands

```bash
# Start everything
docker-compose up --build

# Start in background
docker-compose up -d --build

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop everything
docker-compose down

# Reset database (⚠️ destroys all data)
docker-compose down -v

# Rebuild a single service
docker-compose up --build backend

# Shell into backend
docker-compose exec backend bash

# Shell into database
docker-compose exec postgres psql -U one01 -d one01_db
```

---

## Deployment

### Moving between devices (the Docker way)

```bash
# On source device — save images
docker save one01_backend one01_frontend | gzip > one01_images.tar.gz

# On target device — load images
docker load < one01_images.tar.gz

# Copy the project folder and run
docker-compose up -d
```

### Cloud deployment
The app is ready for any cloud platform that supports Docker Compose:
- **Railway**: `railway up`
- **Render**: Connect repo, use Docker service
- **AWS ECS / GCP Cloud Run**: Push images to ECR/GCR
- **DigitalOcean App Platform**: Docker Compose support built-in

---

## API Reference

All endpoints are documented at `http://localhost:8000/docs` (Swagger UI).

Key endpoints:
```
POST /api/auth/register          Register
POST /api/auth/login             Login (returns JWT)
POST /api/auth/preferences       Save onboarding preferences
GET  /api/auth/me                Current user + preferences

POST /api/subjects/              Create subject (Professor Agent generates outline)
GET  /api/subjects/              List all subjects
GET  /api/subjects/{id}          Subject + topics

POST /api/chat/explain/{topic_id}  Stream topic explanation (SSE)
POST /api/chat/doubt             Stream doubt response (SSE)
GET  /api/chat/history/{topic_id}  Conversation history

POST /api/quiz/generate          Generate quiz sets (Examiner Agent)
POST /api/quiz/submit            Submit answers + get analysis
GET  /api/quiz/sets/{topic_id}   Get existing quiz sets

GET  /api/notes/{subject_id}     Get all notes for subject
PUT  /api/notes/{note_id}        Update/edit a note

GET  /api/progress/{subject_id}  Progress report
PATCH /api/topics/{id}/complete  Mark topic as complete

POST /api/feedback/{subject_id}  Submit feedback (Scribe Agent processes)
GET  /api/feedback/{subject_id}  Feedback history
```

---

## Project Structure

```
one01/
├── docker-compose.yml
│
├── backend/
│   ├── Dockerfile
│   ├── .env                    ← Add your API key here
│   ├── requirements.txt
│   ├── main.py                 FastAPI app + router registration
│   ├── agents/
│   │   └── orchestrator.py     ← All 4 agents live here
│   ├── api/routes/
│   │   ├── auth.py
│   │   ├── subjects.py
│   │   ├── topics.py
│   │   ├── chat.py             ← Streaming SSE routes
│   │   ├── quiz.py
│   │   ├── notes.py
│   │   ├── progress.py
│   │   └── feedback.py
│   ├── db/
│   │   ├── database.py         SQLAlchemy async engine
│   │   ├── models.py           ORM models
│   │   └── init.sql            DB schema (auto-run by Docker)
│   └── utils/
│       ├── auth.py             JWT + password hashing
│       └── config.py           Settings from .env
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tailwind.config.js
    ├── next.config.js
    └── src/
        ├── app/
        │   ├── globals.css       Design tokens, prose styles
        │   ├── layout.tsx        Root layout
        │   ├── page.tsx          Redirect logic
        │   ├── auth/page.tsx     Login + Register
        │   ├── onboarding/page.tsx  3-step personalization
        │   └── dashboard/
        │       ├── layout.tsx    Sidebar navigation
        │       ├── page.tsx      Subject management
        │       ├── learn/[subjectId]/page.tsx    ← Main learning UI
        │       ├── notes/[subjectId]/page.tsx
        │       ├── progress/[subjectId]/page.tsx
        │       ├── questions/[subjectId]/page.tsx
        │       └── feedback/[subjectId]/page.tsx
        ├── components/
        │   └── quiz/QuizPanel.tsx
        ├── lib/
        │   └── api.ts           Axios + SSE streaming helpers
        └── store/
            └── useStore.ts      Zustand global state
```

---

## Customization

### Adding a new teaching style
In `backend/agents/orchestrator.py`, add to `style_map`:
```python
"coach": "a motivational coach who uses sports analogies, keeps energy high, and focuses on achieving goals"
```
In `frontend/src/app/onboarding/page.tsx`, add to `TEACHING_STYLES`.

### Changing the AI model
In `backend/agents/orchestrator.py`:
```python
MODEL = "claude-opus-4-20250514"  # For more powerful responses
```

### Adding a vector database (advanced)
For storing subject-specific documents (textbooks, papers):
1. Add Pinecone/Weaviate to `requirements.txt`
2. Create an embedding service in `backend/services/embeddings.py`
3. Update the Professor Agent to retrieve relevant context before generating outlines

---
