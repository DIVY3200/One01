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
  - Interactive learning with streaming responses

---

## 🧩 Multi-Agent Architecture

| Agent | Role |
|------|------|
| **Professor** | Generates curriculum and topic structure |
| **Tutor** | Explains concepts and resolves doubts |
| **Examiner** | Creates quizzes and analyzes performance |
| **Scribe** | Generates notes and processes feedback |

---

## ⚙️ Tech Stack

### Frontend
- Next.js 14
- TypeScript
- Tailwind CSS
- Zustand

### Backend
- FastAPI
- Python
- SQLAlchemy (Async)

### AI
- Anthropic Claude API

### Database
- SQLite (local setup) / PostgreSQL (production)

### Others
- JWT Authentication
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
ANTHROPIC_API_KEY=your_api_key
SECRET_KEY=your_secret_key
DATABASE_URL=sqlite+aiosqlite:///./test.db
CORS_ORIGINS=["http://localhost:3000"]
```

### Run backend:
```bash
python -m uvicorn main:app --reload --port 8000
```

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
| **ANTHROPIC_API_KEY** | API key for AI model |
| **DATABASE_URL** | Database connection |
| **SECRET_KEY** | JWT secret |
| **CORS_ORIGINS** | Allowed frontend URLs |


<img width="1196" height="540" alt="WhatsApp Image 2026-04-26 at 11 15 08 PM" src="https://github.com/user-attachments/assets/31d6ff97-38e5-4665-aa45-4106a7c6d8cf" />

# 💡 Future Improvements
- Vector database integration (RAG)
- Multi-model support (Gemini, Groq)
- Deployment on cloud platforms
- Advanced analytics dashboard

# 👨‍💻 Author
Divyansh Kaushal

# ⭐ Contribution
Feel free to fork, improve, and contribute!
