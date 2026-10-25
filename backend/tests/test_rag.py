"""RAG library: ingestion, hybrid retrieval, grounded answers and lesson memory."""
import time

from helpers import (
    BACKPROP_MD, FAKE_LESSON, OPTIMIZERS_PDF, PHOTOSYNTHESIS_TXT, REWRITTEN_QUERY,
    db_rows, hex_id, override, sse, text_of,
)
from utils.config import settings


def upload(client, headers, subject_id, name, data):
    return client.post(f"/api/rag/{subject_id}/documents", headers=headers, files={"file": (name, data)})


def search(client, headers, subject_id, query):
    response = client.post(f"/api/rag/{subject_id}/search", json={"query": query}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["results"]


def wait_for_lesson(client, headers, subject_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = client.get(f"/api/rag/{subject_id}/documents", headers=headers).json()
        lessons = [d for d in docs if d["source_type"] == "lesson"]
        if lessons:
            return lessons
        time.sleep(0.1)
    return []


# ── Keyword mode (no Gemini key) ─────────────────────────────────
def test_status_reports_keyword_mode_without_a_key(client, register):
    status = client.get("/api/rag/status", headers=register()).json()
    assert status["retrieval"] == "keyword (BM25)"
    assert status["model"] is None


def test_upload_markdown_pdf_and_text(client, subject):
    headers, subject_id, _ = subject
    md = upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode()).json()
    assert md["status"] == "ready" and md["num_chunks"] >= 2 and md["embedding_model"] is None

    pdf = upload(client, headers, subject_id, "optimizers.pdf", OPTIMIZERS_PDF).json()
    assert pdf["num_pages"] == 2 and pdf["num_chunks"] == 2

    assert upload(client, headers, subject_id, "bio.txt", PHOTOSYNTHESIS_TXT.encode()).status_code == 200
    assert len(client.get(f"/api/rag/{subject_id}/documents", headers=headers).json()) == 3


def test_bad_uploads_are_rejected(client, subject):
    headers, subject_id, _ = subject
    assert upload(client, headers, subject_id, "virus.exe", b"MZ").status_code == 400
    assert upload(client, headers, subject_id, "empty.md", b"").status_code == 400
    assert upload(client, headers, subject_id, "broken.pdf", b"%PDF-1.4 garbage").status_code == 422


def test_keyword_search_finds_the_right_passage_and_page(client, subject):
    headers, subject_id, _ = subject
    upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode())
    upload(client, headers, subject_id, "optimizers.pdf", OPTIMIZERS_PDF)

    top = search(client, headers, subject_id, "chain rule vanishing gradients sigmoid")[0]
    assert top["title"] == "backprop.md" and top["keyword_score"] and top["dense_score"] is None

    top = search(client, headers, subject_id, "Adam squared gradients")[0]
    assert top["title"] == "optimizers.pdf" and top["page"] == 2


def test_ask_without_gemini_shows_the_passages(client, subject):
    headers, subject_id, _ = subject
    upload(client, headers, subject_id, "bio.txt", PHOTOSYNTHESIS_TXT.encode())
    events = sse(client.post(f"/api/rag/{subject_id}/ask", json={"question": "How does the Calvin cycle fix carbon?"}, headers=headers).text)
    sources = next(e for e in events if e.get("type") == "sources")["sources"]
    assert sources[0]["title"] == "bio.txt"
    assert "most relevant passages" in text_of(events)
    assert any(e.get("type") == "ai_fallback" for e in events)
    assert events[-1]["type"] == "done"


def test_lessons_and_doubts_cite_the_library(client, subject):
    headers, subject_id, topics = subject
    upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode())
    topic = topics[0]

    events = sse(client.post(f"/api/chat/explain/{topic['id']}", headers=headers).text)
    assert any(e.get("type") == "sources" for e in events)

    events = sse(client.post("/api/chat/doubt", json={"topic_id": topic["id"], "message": "why do gradients vanish with sigmoid activations"}, headers=headers).text)
    sources = next(e for e in events if e.get("type") == "sources")
    assert any(s["title"] == "backprop.md" for s in sources["sources"])
    assert sources["query"].startswith(topic["title"])  # heuristic query when no LLM rewrite

    history = client.get(f"/api/chat/history/{topic['id']}", headers=headers).json()
    assert any(m["role"] == "assistant" and m["sources"] for m in history)


def test_mock_lessons_are_not_saved_as_lesson_memory(client, subject):
    headers, subject_id, topics = subject
    client.post(f"/api/chat/explain/{topics[0]['id']}", headers=headers)
    time.sleep(0.3)
    docs = client.get(f"/api/rag/{subject_id}/documents", headers=headers).json()
    assert not any(d["source_type"] == "lesson" for d in docs)


def test_deleting_a_document_removes_it_from_search(client, subject):
    headers, subject_id, _ = subject
    doc = upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode()).json()
    assert client.delete(f"/api/rag/documents/{doc['id']}", headers=headers).status_code == 200
    results = search(client, headers, subject_id, "chain rule vanishing gradients sigmoid")
    assert all(r["title"] != "backprop.md" for r in results)


# ── Hybrid mode (fake Gemini) ────────────────────────────────────
def test_hybrid_search_with_gemini_embeddings(client, subject, fake_gemini):
    headers, subject_id, _ = subject
    status = client.get("/api/rag/status", headers=headers).json()
    assert status["retrieval"].startswith("hybrid")

    md = upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode()).json()
    assert md["embedding_model"] == f"{settings.GEMINI_EMBED_MODEL}@{settings.GEMINI_EMBED_DIM}"
    upload(client, headers, subject_id, "optimizers.pdf", OPTIMIZERS_PDF)

    blob = db_rows("select embedding from document_chunks where document_id = ?", hex_id(md["id"]))[0][0]
    import numpy as np
    vector = np.frombuffer(blob, dtype=np.float32)
    assert len(vector) == settings.GEMINI_EMBED_DIM and abs(np.linalg.norm(vector) - 1) < 1e-4

    top = search(client, headers, subject_id, "learning rate step size")[0]
    assert top["title"] == "optimizers.pdf"
    assert top["dense_score"] is not None and top["keyword_score"] is not None


def test_streaming_lesson_is_grounded_and_saved_to_memory(client, subject, fake_gemini):
    headers, subject_id, topics = subject
    upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode())
    topic = topics[0]

    events = sse(client.post(f"/api/chat/explain/{topic['id']}", headers=headers).text)
    lesson = "".join(e["chunk"] for e in events if e.get("type") == "text")
    assert lesson == "".join(FAKE_LESSON)
    assert not any(e.get("type") == "ai_fallback" for e in events)
    assert "REFERENCE MATERIAL" in fake_gemini.prompts[-1] and "GROUNDING RULES" in fake_gemini.prompts[-1]

    saved = db_rows("select explanation_content from topics where id = ?", hex_id(topic["id"]))[0][0]
    assert saved == lesson

    lessons = wait_for_lesson(client, headers, subject_id)
    assert [d["filename"] for d in lessons] == [f"Lesson: {topic['title']}"]

    # Re-teaching replaces the lesson instead of duplicating it
    client.post(f"/api/chat/explain/{topic['id']}", headers=headers)
    time.sleep(1.0)
    docs = client.get(f"/api/rag/{subject_id}/documents", headers=headers).json()
    assert sum(d["source_type"] == "lesson" for d in docs) == 1


def test_follow_up_question_is_rewritten_before_search(client, subject, fake_gemini):
    headers, subject_id, topics = subject
    upload(client, headers, subject_id, "backprop.md", BACKPROP_MD.encode())
    topic = topics[0]
    client.post(f"/api/chat/explain/{topic['id']}", headers=headers)  # creates chat history

    events = sse(client.post("/api/chat/doubt", json={"topic_id": topic["id"], "message": "go deeper on that"}, headers=headers).text)
    sources = next(e for e in events if e.get("type") == "sources")
    assert sources["query"] == REWRITTEN_QUERY
    assert "go deeper on that" in fake_gemini.prompts[-1] and "[1]" in fake_gemini.prompts[-1]


def test_ask_streams_a_grounded_answer(client, subject, fake_gemini):
    headers, subject_id, _ = subject
    upload(client, headers, subject_id, "optimizers.pdf", OPTIMIZERS_PDF)
    events = sse(client.post(f"/api/rag/{subject_id}/ask", json={"question": "what does Adam track?"}, headers=headers).text)
    assert text_of(events).endswith("[1].")
    assert "Use ONLY the excerpts" in fake_gemini.prompts[-1]


def test_upload_limit_is_enforced(client, subject):
    headers, subject_id, _ = subject
    with override(RAG_MAX_UPLOAD_MB=0):
        assert upload(client, headers, subject_id, "big.md", b"x" * 10).status_code == 413
