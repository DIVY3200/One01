"""Tracks when an agent served mock content because Gemini was unavailable.

Agents call note("Professor") in their fallback branch. The middleware gives
each request its own record and adds an `X-AI-Fallback` header to normal JSON
responses; streaming routes check used() and send an `ai_fallback` event.
"""
from contextvars import ContextVar
from typing import List, Optional

HEADER = "X-AI-Fallback"

_state: ContextVar[Optional[dict]] = ContextVar("ai_fallback_state", default=None)


def note(agent: str) -> None:
    print(f"Using MOCK FALLBACK for {agent}")
    state = _state.get()
    if state is not None:
        state.setdefault("agents", []).append(agent)


def used() -> List[str]:
    state = _state.get()
    return sorted(set(state.get("agents", []))) if state else []


class FallbackHeaderMiddleware:
    """Pure ASGI middleware, so the endpoint runs in the same context as this record."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state: dict = {}
        token = _state.set(state)

        async def send_with_header(message):
            if message["type"] == "http.response.start" and state.get("agents"):
                agents = ",".join(sorted(set(state["agents"])))
                message = {**message, "headers": [*message.get("headers", []), (HEADER.lower().encode(), agents.encode())]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            _state.reset(token)
