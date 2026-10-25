"""llm/gemini.py against a local mock of the Gemini REST API (real SDK, fake server)."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from llm import gemini
from utils.config import settings


class _MockGemini(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        self.seen.append((self.path, body))
        if ":streamGenerateContent" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for word in ["Hello ", "from ", "Gemini"]:
                payload = {"candidates": [{"content": {"role": "model", "parts": [{"text": word}]}}]}
                self.wfile.write(f"data: {json.dumps(payload)}\r\n\r\n".encode())
                self.wfile.flush()
            return
        if ":generateContent" in self.path:
            out = {"candidates": [{"content": {"role": "model", "parts": [{"text": '{"ok": true}'}]}}]}
        elif "mbedContent" in self.path:
            out = {"embeddings": [{"values": [0.1] * 4} for _ in body.get("requests", [body])]}
        else:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def mock_server(monkeypatch):
    from google import genai
    from google.genai import types

    _MockGemini.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockGemini)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = genai.Client(api_key="test-key", http_options=types.HttpOptions(base_url=f"http://127.0.0.1:{server.server_port}", timeout=10_000))
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "_client", client)
    yield _MockGemini.seen
    server.shutdown()


def test_generate_sends_model_system_prompt_and_json_mode(mock_server):
    text = asyncio.run(gemini.generate("hi", system="be brief", json_mode=True, temperature=0.5))
    path, body = mock_server[-1]
    assert text == '{"ok": true}'
    assert f"{settings.GEMINI_MODEL}:generateContent" in path
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["temperature"] == 0.5
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"


def test_stream_yields_deltas(mock_server):
    async def collect():
        return [chunk async for chunk in gemini.stream("hi", model="custom-model")]
    assert asyncio.run(collect()) == ["Hello ", "from ", "Gemini"]
    assert "custom-model:streamGenerateContent" in mock_server[-1][0]


def test_embeddings_are_batched_with_task_type_and_dimension(mock_server):
    vectors = asyncio.run(gemini.embed(["a"] * 150, task_type="RETRIEVAL_DOCUMENT"))
    calls = [(p, b) for p, b in mock_server if "mbedContent" in p]
    assert len(vectors) == 150 and len(calls) == 2
    first = calls[0][1].get("requests", [calls[0][1]])[0]
    assert first["taskType"] == "RETRIEVAL_DOCUMENT"
    assert first["outputDimensionality"] == settings.GEMINI_EMBED_DIM


def test_failures_return_nothing_so_agents_can_fall_back(monkeypatch):
    from google import genai
    from google.genai import types
    dead = genai.Client(api_key="k", http_options=types.HttpOptions(base_url="http://127.0.0.1:9", timeout=2_000))
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "_client", dead)

    async def run():
        return (
            await gemini.generate("x"),
            [c async for c in gemini.stream("x")],
            await gemini.embed(["x"], "RETRIEVAL_QUERY"),
        )
    assert asyncio.run(run()) == (None, [], None)
