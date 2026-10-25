"""
Hybrid retrieval over a subject's library.

  dense   cosine similarity between unit vectors (semantic match)
  sparse  Okapi BM25 over tokens (exact terms, formulas, names)
  fusion  Reciprocal Rank Fusion: score = Σ 1 / (RRF_K + rank)

Each subject's index is built from the database once and cached in memory.
It is rebuilt when chunks are added or removed (fingerprint check), so it
stays correct across multiple workers too.
"""
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, DocumentChunk
from rag import embeddings

RRF_K = 60

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = frozenset(
    "a an the and or of to in on for is are was were be been being it its this that these those "
    "with as by at from what how why which who whom when where do does did can could should would "
    "will i you me my your we our they them their he she his her not no so if then than there here "
    "about into over also just very please explain tell".split()
)


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


class BM25:
    def __init__(self, docs: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.lengths = [len(d) for d in docs]
        self.avgdl = (sum(self.lengths) / self.n) if self.n else 1.0
        self.postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        for i, doc in enumerate(docs):
            for term, freq in Counter(doc).items():
                self.postings[term].append((i, freq))

    def scores(self, query: List[str]) -> np.ndarray:
        scores = np.zeros(self.n, dtype=np.float32)
        for term in set(query):
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = math.log(1 + (self.n - len(postings) + 0.5) / (len(postings) + 0.5))
            for i, freq in postings:
                norm = freq + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avgdl)
                scores[i] += idf * freq * (self.k1 + 1) / norm
        return scores


@dataclass
class IndexedChunk:
    id: str
    document_id: str
    title: str
    source_type: str
    chunk_index: int
    page: Optional[int]
    heading: Optional[str]
    content: str


@dataclass
class RetrievedChunk:
    chunk: IndexedChunk
    score: float                      # fused RRF score
    dense_score: Optional[float]      # cosine similarity, if found by the dense retriever
    keyword_score: Optional[float]    # BM25 score, if found by the keyword retriever


class SubjectIndex:
    def __init__(self, fingerprint, chunks: List[IndexedChunk], vectors: Dict[str, Tuple[List[int], List[np.ndarray]]]):
        self.fingerprint = fingerprint
        self.chunks = chunks
        self.bm25 = BM25([tokenize(f"{c.heading or ''} {c.content}") for c in chunks])
        # embedding model → (row positions in self.chunks, matrix of unit vectors)
        self.dense = {model: (np.array(rows), np.vstack(vecs)) for model, (rows, vecs) in vectors.items()}

    def dense_model(self) -> Optional[str]:
        """The embedding model covering most chunks that we can still embed queries with."""
        usable = [m for m in self.dense if m in embeddings.available_models()]
        return max(usable, key=lambda m: len(self.dense[m][0]), default=None)


_cache: Dict[str, SubjectIndex] = {}


def invalidate(subject_id: str) -> None:
    _cache.pop(str(subject_id), None)


async def _fingerprint(db: AsyncSession, subject_id: str):
    result = await db.execute(
        select(func.count(DocumentChunk.id), func.max(DocumentChunk.created_at))
        .where(DocumentChunk.subject_id == subject_id)
    )
    count, latest = result.one()
    return count, str(latest)


async def library_size(db: AsyncSession, subject_id: str) -> int:
    count, _ = await _fingerprint(db, str(subject_id))
    return count


async def get_index(db: AsyncSession, subject_id: str) -> SubjectIndex:
    subject_id = str(subject_id)
    fingerprint = await _fingerprint(db, subject_id)
    cached = _cache.get(subject_id)
    if cached and cached.fingerprint == fingerprint:
        return cached

    rows = await db.execute(
        select(DocumentChunk, Document.filename, Document.source_type)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.subject_id == subject_id, Document.status == "ready")
        .order_by(Document.created_at, DocumentChunk.chunk_index)
    )
    chunks: List[IndexedChunk] = []
    vectors: Dict[str, Tuple[List[int], List[np.ndarray]]] = defaultdict(lambda: ([], []))
    for chunk, filename, source_type in rows.all():
        if chunk.embedding and chunk.embedding_model:
            positions, vecs = vectors[chunk.embedding_model]
            positions.append(len(chunks))
            vecs.append(embeddings.from_bytes(chunk.embedding))
        chunks.append(IndexedChunk(
            id=str(chunk.id),
            document_id=str(chunk.document_id),
            title=filename,
            source_type=source_type,
            chunk_index=chunk.chunk_index,
            page=chunk.page,
            heading=chunk.heading,
            content=chunk.content,
        ))

    index = SubjectIndex(fingerprint, chunks, vectors)
    _cache[subject_id] = index
    return index


async def hybrid_search(
    db: AsyncSession,
    subject_id: str,
    query: str,
    top_k: int,
    candidates: int,
) -> List[RetrievedChunk]:
    index = await get_index(db, subject_id)
    if not index.chunks or not query.strip():
        return []

    # Sparse: BM25 over the whole library
    keyword_scores = index.bm25.scores(tokenize(query))
    keyword_ranked = [int(i) for i in np.argsort(-keyword_scores)[:candidates] if keyword_scores[i] > 0]

    # Dense: cosine similarity (dot product of unit vectors)
    dense_ranked: List[int] = []
    dense_scores: Dict[int, float] = {}
    model = index.dense_model()
    if model:
        query_vec = await embeddings.embed_query(query, model)
        if query_vec is not None:
            positions, matrix = index.dense[model]
            sims = matrix @ query_vec
            for j in np.argsort(-sims)[:candidates]:
                pos = int(positions[j])
                dense_ranked.append(pos)
                dense_scores[pos] = float(sims[j])

    # Reciprocal Rank Fusion
    fused: Dict[int, float] = defaultdict(float)
    for ranking in (dense_ranked, keyword_ranked):
        for rank, pos in enumerate(ranking):
            fused[pos] += 1.0 / (RRF_K + rank + 1)

    best = sorted(fused, key=fused.get, reverse=True)[:top_k]
    return [
        RetrievedChunk(
            chunk=index.chunks[pos],
            score=round(fused[pos], 5),
            dense_score=round(dense_scores[pos], 4) if pos in dense_scores else None,
            keyword_score=round(float(keyword_scores[pos]), 3) if keyword_scores[pos] > 0 else None,
        )
        for pos in best
    ]
