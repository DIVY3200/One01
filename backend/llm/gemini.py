"""
Gemini client (google-genai SDK).

One shared async client for text generation, token streaming and embeddings.
Every call returns None / yields nothing when no API key is configured or the
API call fails, so the agents can keep their mock fallbacks.
"""
import asyncio
import os
import traceback
from typing import AsyncGenerator, List, Optional

from utils.config import settings

_PLACEHOLDER_KEYS = {"", "your-gemini-api-key-here"}
_EMBED_BATCH_SIZE = 100  # max texts per embed_content request

_client = None


def _api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "") or settings.GEMINI_API_KEY


def is_configured() -> bool:
    return _api_key() not in _PLACEHOLDER_KEYS


def get_client():
    """Lazily build the shared client. Returns None if Gemini is unavailable."""
    global _client
    if _client is not None:
        return _client
    if not is_configured():
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("[WARN] google-genai is not installed — run: pip install -r requirements.txt")
        return None
    _client = genai.Client(
        api_key=_api_key(),
        http_options=types.HttpOptions(timeout=120_000),  # milliseconds
    )
    return _client


def _generation_config(system: Optional[str], temperature: float, json_mode: bool):
    from google.genai import types
    return types.GenerateContentConfig(
        system_instruction=system or None,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )


async def generate(
    prompt: str,
    *,
    system: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 1.0,
    model: Optional[str] = None,
    timeout: int = 90,
) -> Optional[str]:
    """Return the full response text, or None if no key / on error."""
    client = get_client()
    if client is None:
        return None
    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model or settings.GEMINI_MODEL,
                contents=prompt,
                config=_generation_config(system, temperature, json_mode),
            ),
            timeout=timeout,
        )
        return response.text
    except asyncio.TimeoutError:
        print(f"[TIMEOUT] Gemini call timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"[ERROR] Gemini generation failed: {e}")
        traceback.print_exc()
        return None


async def stream(
    prompt: str,
    *,
    system: Optional[str] = None,
    temperature: float = 1.0,
    model: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Yield text deltas as Gemini produces them (real token streaming).

    Yields nothing if Gemini is unavailable, so callers can detect that and
    fall back. An error mid-stream ends the stream after the text already sent.
    """
    client = get_client()
    if client is None:
        return
    try:
        response_stream = await client.aio.models.generate_content_stream(
            model=model or settings.GEMINI_MODEL,
            contents=prompt,
            config=_generation_config(system, temperature, json_mode=False),
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        print(f"[ERROR] Gemini streaming failed: {e}")
        traceback.print_exc()


async def embed(texts: List[str], task_type: str) -> Optional[List[List[float]]]:
    """Embed texts with the Gemini embedding model.

    task_type is RETRIEVAL_DOCUMENT for stored chunks and RETRIEVAL_QUERY for
    search queries (only gemini-embedding-001 accepts it). Vectors are not
    normalized here; callers must normalize when GEMINI_EMBED_DIM < 3072.
    """
    client = get_client()
    if client is None or not texts:
        return None
    from google.genai import types

    model = settings.GEMINI_EMBED_MODEL
    config = types.EmbedContentConfig(
        task_type=task_type if "embedding-001" in model else None,
        output_dimensionality=settings.GEMINI_EMBED_DIM,
    )
    vectors: List[List[float]] = []
    try:
        for start in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[start:start + _EMBED_BATCH_SIZE]
            response = await client.aio.models.embed_content(model=model, contents=batch, config=config)
            vectors.extend(e.values for e in response.embeddings)
        return vectors
    except Exception as e:
        print(f"[ERROR] Gemini embedding failed: {e}")
        return None


def describe() -> dict:
    """Which models are active — shown in the UI and /health."""
    return {
        "provider": "google-gemini" if is_configured() else None,
        "model": settings.GEMINI_MODEL if is_configured() else None,
        "fast_model": settings.GEMINI_FAST_MODEL if is_configured() else None,
        "embedding_model": settings.GEMINI_EMBED_MODEL if is_configured() else None,
    }
