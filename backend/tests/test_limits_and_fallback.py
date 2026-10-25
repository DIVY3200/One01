"""Gaps 9-10: per-user AI rate limit, and clear signals when mock content is served."""
from helpers import override, sse


def test_ai_requests_are_rate_limited_per_user(client, subject, register):
    from utils import rate_limit
    headers, subject_id, _ = subject
    rate_limit.reset()  # creating the subject in the fixture already used one AI request
    with override(AI_RATE_LIMIT_PER_MINUTE=2):
        codes =[client.post(f"/api/rag/{subject_id}/search", json={"query": "x"}, headers=headers).status_code for _ in range(3)]
        assert codes == [200, 200, 429]

        limited = client.post(f"/api/rag/{subject_id}/search", json={"query": "x"}, headers=headers)
        assert int(limited.headers["retry-after"]) > 0
        assert "Too many AI requests" in limited.json()["detail"]

        # Non-AI routes and other users are not affected
        assert client.get(f"/api/rag/{subject_id}/documents", headers=headers).status_code == 200
        other = register()
        assert client.get("/api/subjects/", headers=other).status_code == 200


def test_mock_curriculum_is_flagged_in_a_header(client, register):
    response = client.post("/api/subjects/", json={"name": "Chemistry", "purpose": "academic", "level": "beginner"}, headers=register())
    assert response.status_code == 200
    assert "Professor" in response.headers["x-ai-fallback"]


def test_real_ai_responses_have_no_fallback_header(client, register):
    response = client.get("/api/subjects/", headers=register())
    assert "x-ai-fallback" not in response.headers


def test_mock_lesson_streams_a_warning_and_is_flagged_in_history(client, subject):
    headers, _, topics = subject
    events = sse(client.post(f"/api/chat/explain/{topics[0]['id']}", headers=headers).text)
    types = [e.get("type") for e in events]
    assert types.index("ai_fallback") < types.index("text")  # warning arrives before the content
    history = client.get(f"/api/chat/history/{topics[0]['id']}", headers=headers).json()
    assert history[-1]["ai_fallback"] is True


def test_real_lesson_has_no_warning(client, subject, fake_gemini):
    headers, _, topics = subject
    events = sse(client.post(f"/api/chat/explain/{topics[0]['id']}", headers=headers).text)
    assert not any(e.get("type") == "ai_fallback" for e in events)
    history = client.get(f"/api/chat/history/{topics[0]['id']}", headers=headers).json()
    assert history[-1]["ai_fallback"] is False
