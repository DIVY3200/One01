"""
Embedding backends, in order of preference:
  1. Gemini (GEMINI_EMBED_MODEL) when an API key is configured
  2. Local sentence-transformers MiniLM, if it was loaded at startup
  3. None — retrieval falls back to keyword (BM25) search only

Every stored vector records the model that produced it, so queries are only
ever compared against vectors from the same model.
"""
import asyncio
from typing import List, Optional, Tuple

import numpy as np

from llm import gemini
from utils.config import settings

LOCAL_MODEL_NAME = "local/all-MiniLM-L6-v2"

_local_model = None  # SentenceTransformer instance, set by main.lifespan


def set_local_model(model) -> None:
    global _local_model
    _local_model = model


def gemini_model_name() -> str:
    # The dimension is part of the name: vectors of different sizes never mix.
    return f"{settings.GEMINI_EMBED_MODEL}@{settings.GEMINI_EMBED_DIM}"


def available_models() -> List[str]:
    models = []
    if gemini.is_configured():
        models.append(gemini_model_name())
    if _local_model is not None:
        models.append(LOCAL_MODEL_NAME)
    return models


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


async def _local_encode(texts: List[str]) -> np.ndarray:
    vectors = await asyncio.to_thread(
        _local_model.encode, texts, normalize_embeddings=True, convert_to_numpy=True
    )
    return np.asarray(vectors, dtype=np.float32)


async def embed_documents(texts: List[str]) -> Tuple[Optional[str], Optional[np.ndarray]]:
    """Embed chunks for storage. Returns (model_name, unit vectors) or (None, None)."""
    if not texts:
        return None, None
    if gemini.is_configured():
        vectors = await gemini.embed(texts, task_type="RETRIEVAL_DOCUMENT")
        if vectors is not None:
            return gemini_model_name(), _normalize(np.asarray(vectors, dtype=np.float32))
    if _local_model is not None:
        return LOCAL_MODEL_NAME, await _local_encode(texts)
    return None, None


async def embed_query(text: str, model_name: str) -> Optional[np.ndarray]:
    """Embed a search query with the same model the stored vectors used."""
    if model_name == gemini_model_name() and gemini.is_configured():
        vectors = await gemini.embed([text], task_type="RETRIEVAL_QUERY")
        if vectors is not None:
            return _normalize(np.asarray(vectors, dtype=np.float32))[0]
        return None
    if model_name == LOCAL_MODEL_NAME and _local_model is not None:
        return (await _local_encode([text]))[0]
    return None


def to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)
