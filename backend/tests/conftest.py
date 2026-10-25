"""Shared test setup: a throwaway SQLite database and no real Gemini calls."""
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

_TMP_DIR = Path(tempfile.mkdtemp(prefix="one01-tests-"))
DB_PATH = _TMP_DIR / "test.db"

# Must be set before the app (and its settings) are imported. Environment
# variables win over backend/.env, so a developer's real key is never used.
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB_PATH.as_posix()}",
    "GEMINI_API_KEY": "",
    "HF_TOKEN": "",
    "SECRET_KEY": "test-secret-key",
    "AI_RATE_LIMIT_PER_MINUTE": "1000",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from helpers import FakeGemini  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    from utils import rate_limit
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture
def register(client):
    """register() -> auth headers for a brand-new user."""
    def _register():
        email = f"user-{uuid.uuid4().hex[:10]}@test.dev"
        response = client.post("/api/auth/register", json={"email": email, "password": "pw123456"})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    return _register


@pytest.fixture
def subject(client, register):
    """A user with one subject (mock curriculum). Returns (headers, subject_id, topics)."""
    headers = register()
    response = client.post(
        "/api/subjects/", json={"name": "Machine Learning", "purpose": "academic", "level": "beginner"}, headers=headers
    )
    assert response.status_code == 200, response.text
    subject_id = response.json()["id"]
    topics = client.get(f"/api/subjects/{subject_id}", headers=headers).json()["topics"]
    return headers, subject_id, topics


@pytest.fixture
def fake_gemini(monkeypatch):
    """Replace Gemini with a deterministic fake (streaming, embeddings, query rewrite)."""
    from llm import gemini
    fake = FakeGemini()
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "embed", fake.embed)
    monkeypatch.setattr(gemini, "stream", fake.stream)
    monkeypatch.setattr(gemini, "generate", fake.generate)
    return fake
