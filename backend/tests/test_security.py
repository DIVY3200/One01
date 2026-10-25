"""Gap 1: every route only exposes the current user's own data. Plus CORS."""
import pytest

from helpers import BACKPROP_MD, db_rows, hex_id


@pytest.fixture
def victim(client, subject):
    """User A with a subject, a lesson (+ saved notes), a quiz set, feedback and a document."""
    headers, subject_id, topics = subject
    topic_id = topics[0]["id"]
    client.post(f"/api/chat/explain/{topic_id}", headers=headers)
    quiz = client.post("/api/quiz/generate", json={"topic_id": topic_id, "quiz_types": ["mcq"]}, headers=headers).json()
    client.post(f"/api/feedback/{subject_id}", json={"content": "Slow down please"}, headers=headers)
    doc = client.post(f"/api/rag/{subject_id}/documents", headers=headers, files={"file": ("notes.md", BACKPROP_MD.encode())}).json()
    notes = client.get(f"/api/notes/{subject_id}", headers=headers).json()
    return {
        "headers": headers,
        "subject_id": subject_id,
        "topic_id": topic_id,
        "quiz_set_id": quiz["quiz_sets"][0]["id"],
        "note_id": notes[0]["id"],
        "document_id": doc["id"],
    }


ATTACKS = [
    ("get", "/api/subjects/{subject_id}", None),
    ("delete", "/api/subjects/{subject_id}", None),
    ("get", "/api/topics/{topic_id}", None),
    ("patch", "/api/topics/{topic_id}/complete", None),
    ("post", "/api/chat/explain/{topic_id}", None),
    ("post", "/api/chat/doubt", {"topic_id": "{topic_id}", "message": "why?"}),
    ("get", "/api/chat/history/{topic_id}", None),
    ("post", "/api/quiz/generate", {"topic_id": "{topic_id}"}),
    ("post", "/api/quiz/generate", {"subject_id": "{subject_id}"}),
    ("post", "/api/quiz/submit", {"quiz_set_id": "{quiz_set_id}", "answers": ["A"]}),
    ("get", "/api/quiz/sets/{topic_id}", None),
    ("get", "/api/notes/{subject_id}", None),
    ("put", "/api/notes/{note_id}", {"content": "hacked"}),
    ("post", "/api/notes/{subject_id}/sync-insight", {"concept": "x", "is_correct": True, "explanation": "y"}),
    ("get", "/api/progress/{subject_id}", None),
    ("post", "/api/progress/{subject_id}/heartbeat", None),
    ("get", "/api/feedback/{subject_id}", None),
    ("post", "/api/feedback/{subject_id}", {"content": "hi"}),
    ("get", "/api/rag/{subject_id}/documents", None),
    ("post", "/api/rag/{subject_id}/search", {"query": "gradients"}),
    ("post", "/api/rag/{subject_id}/ask", {"question": "gradients?"}),
    ("delete", "/api/rag/documents/{document_id}", None),
]


@pytest.mark.parametrize("method,path,body", ATTACKS, ids=[f"{m.upper()} {p}" for m, p, _ in ATTACKS])
def test_other_users_cannot_touch_the_data(client, register, victim, method, path, body):
    attacker = register()
    url = path.format(**victim)
    kwargs = {"headers": attacker}
    if body is not None:
        kwargs["json"] = {k: (v.format(**victim) if isinstance(v, str) else v) for k, v in body.items()}
    response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 404, f"{method.upper()} {url} -> {response.status_code}: {response.text[:200]}"


def test_victim_data_is_unchanged_after_attacks(client, register, victim):
    attacker = register()
    client.put(f"/api/notes/{victim['note_id']}", json={"content": "hacked"}, headers=attacker)
    client.delete(f"/api/subjects/{victim['subject_id']}", headers=attacker)
    note = db_rows("select content from notes where id = ?", hex_id(victim["note_id"]))[0][0]
    assert note != "hacked"
    assert client.get(f"/api/subjects/{victim['subject_id']}", headers=victim["headers"]).status_code == 200


def test_owner_still_has_access(client, victim):
    h = victim["headers"]
    assert client.get(f"/api/chat/history/{victim['topic_id']}", headers=h).status_code == 200
    assert client.get(f"/api/quiz/sets/{victim['topic_id']}", headers=h).status_code == 200
    assert client.get(f"/api/feedback/{victim['subject_id']}", headers=h).json()[0]["content"] == "Slow down please"


@pytest.mark.parametrize("origin,allowed", [
    ("http://localhost:3000", True),
    ("http://127.0.0.1:3000", True),
    ("https://evil.example", False),
])
def test_cors_only_allows_configured_origins(client, origin, allowed):
    response = client.options("/api/subjects/", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    assert (response.headers.get("access-control-allow-origin") == origin) is allowed


@pytest.mark.parametrize("configured", [
    '["https://one01.vercel.app/"]',  # trailing slash
    "https://one01.vercel.app",       # plain string instead of a JSON list
    ' [ "https://one01.vercel.app" ] ',
])
def test_cors_setting_formats(configured):
    from helpers import override
    from main import _cors_origins
    with override(CORS_ORIGINS=configured):
        assert _cors_origins() == ["https://one01.vercel.app"]
