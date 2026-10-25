"""Test data and fakes shared by the test modules."""
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager

import numpy as np

from utils.config import settings


@contextmanager
def override(**values):
    """Temporarily change settings, e.g. override(AI_RATE_LIMIT_PER_MINUTE=3)."""
    old = {key: getattr(settings, key) for key in values}
    for key, value in values.items():
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in old.items():
            setattr(settings, key, value)


def db_rows(sql: str, *params) -> list:
    """Read-only query against the test database (UUIDs are stored as 32-char hex, see hex_id)."""
    connection = sqlite3.connect(os.environ["DATABASE_URL"].split(":///", 1)[1])
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def hex_id(value: str) -> str:
    return uuid.UUID(value).hex


def sse(body: str) -> list:
    """Parse a Server-Sent Events response body into its JSON events."""
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def text_of(events: list) -> str:
    return "".join(e.get("chunk", "") for e in events if e.get("chunk"))


def make_pdf(pages: list) -> bytes:
    """A minimal valid PDF with one text page per entry (lines split on newlines)."""
    objects = {}
    page_ids = [4 + 2 * i for i in range(len(pages))]
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for i, text in enumerate(pages):
        page_id, content_id = page_ids[i], page_ids[i] + 1
        lines = " ".join(f"({line}) Tj T*" for line in text.split("\n"))
        stream = f"BT /F1 12 Tf 72 720 Td 14 TL {lines} ET".encode()
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for object_id in sorted(objects):
        offsets[object_id] = len(out)
        out += f"{object_id} 0 obj\n".encode() + objects[object_id] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode() + b"0000000000 65535 f \n"
    for object_id in range(1, size):
        out += f"{offsets[object_id]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


BACKPROP_MD = """# Backpropagation in Machine Learning

Backpropagation computes gradients of the loss with respect to every weight by applying the chain rule
layer by layer, from the output back to the input. Each layer multiplies the upstream gradient by its local Jacobian.

## Vanishing gradients

With sigmoid activations the derivative is at most 0.25, so multiplying many of them makes gradients
shrink exponentially in deep networks. ReLU activations and residual connections mitigate vanishing gradients.

## Weight update

After backpropagation, gradient descent updates each weight: w = w - learning_rate * dL/dw.
""" + ("Additional filler sentence about training neural networks in machine learning. " * 30)

PHOTOSYNTHESIS_TXT = """Photosynthesis converts light energy into chemical energy in chloroplasts.
The Calvin cycle fixes carbon dioxide into glucose using ATP and NADPH produced by the light reactions."""

OPTIMIZERS_PDF = make_pdf([
    "Gradient descent for machine learning\nThe learning rate controls the step size of each update.\nToo large a learning rate makes training diverge.",
    "Momentum and Adam\nAdam keeps running averages of gradients and squared gradients.\nIt adapts the learning rate per parameter.",
])

FAKE_LESSON = ["Gradients ", "vanish because ", "sigmoid derivatives are small [1]."]
REWRITTEN_QUERY = "vanishing gradients sigmoid derivative backpropagation"


class FakeGemini:
    """Deterministic stand-in for llm.gemini: hashed bag-of-words embeddings, canned stream."""

    def __init__(self):
        self.prompts = []

    @staticmethod
    def _vector(text: str) -> list:
        v = np.zeros(settings.GEMINI_EMBED_DIM, dtype=np.float32)
        for token in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(token.encode()).hexdigest(), 16) % len(v)] += 1.0
        return (v * 3.7).tolist()  # un-normalized on purpose, like gemini-embedding-001 at 768-d

    async def embed(self, texts, task_type):
        return [self._vector(t) for t in texts]

    async def stream(self, prompt, **kwargs):
        self.prompts.append(prompt)
        for part in FAKE_LESSON:
            await asyncio.sleep(0)
            yield part

    async def generate(self, prompt, **kwargs):
        if kwargs.get("model") == settings.GEMINI_FAST_MODEL:
            return f'"{REWRITTEN_QUERY}"\n'
        return None  # other agents use their mock fallbacks
