"""RAG service: ingestion, lesson memory, query rewriting and grounded prompt context."""
import asyncio
from typing import List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import AsyncSessionLocal
from db.models import Document, DocumentChunk, Topic
from llm import gemini
from rag import embeddings, retriever
from rag.ingest import Chunk, chunk_sections, extract_sections, markdown_sections, strip_quiz_blocks
from rag.retriever import RetrievedChunk
from utils.config import settings

_SNIPPET_CHARS = 280
_background_tasks: set = set()


# ─── Ingestion ────────────────────────────────────────────────────
def _embedding_text(title: str, chunk: Chunk) -> str:
    """Contextual chunk header: embed each chunk together with where it came from."""
    header = title + (f" — {chunk.heading}" if chunk.heading else "")
    return f"{header}\n{chunk.text}"


async def _store_chunks(db: AsyncSession, doc: Document, chunks: List[Chunk]) -> None:
    model_name, vectors = await embeddings.embed_documents([_embedding_text(doc.filename, c) for c in chunks])
    for i, chunk in enumerate(chunks):
        db.add(DocumentChunk(
            document_id=doc.id,
            subject_id=doc.subject_id,
            chunk_index=i,
            content=chunk.text,
            page=chunk.page,
            heading=chunk.heading[:500] if chunk.heading else None,
            embedding=embeddings.to_bytes(vectors[i]) if vectors is not None else None,
            embedding_model=model_name,
        ))
    doc.num_chunks = len(chunks)
    doc.embedding_model = model_name


async def ingest_upload(db: AsyncSession, subject_id: str, user_id: str, filename: str, data: bytes) -> Document:
    """Parse, chunk, embed and store an uploaded file. Raises UnsupportedFileError / parser errors."""
    sections = await asyncio.to_thread(extract_sections, filename, data)
    chunks = chunk_sections(sections, settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)

    doc = Document(
        subject_id=subject_id,
        user_id=user_id,
        filename=filename,
        source_type="upload",
        size_bytes=len(data),
        num_pages=max((s.page or 0 for s in sections), default=0) or None,
    )
    db.add(doc)
    await db.flush()

    if chunks:
        await _store_chunks(db, doc, chunks)
    else:
        doc.status = "failed"
        doc.error = "No extractable text found. Scanned PDFs need OCR before upload."

    await db.commit()
    retriever.invalidate(subject_id)
    return doc


async def delete_document(db: AsyncSession, doc: Document) -> None:
    subject_id = doc.subject_id
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    await db.execute(delete(Document).where(Document.id == doc.id))
    await db.commit()
    retriever.invalidate(subject_id)


async def delete_subject_library(db: AsyncSession, subject_id: str) -> None:
    """Remove a subject's documents and chunks. The caller commits."""
    await db.execute(delete(DocumentChunk).where(DocumentChunk.subject_id == subject_id))
    await db.execute(delete(Document).where(Document.subject_id == subject_id))
    retriever.invalidate(subject_id)


# ─── Lesson memory ────────────────────────────────────────────────
async def index_lesson(db: AsyncSession, topic: Topic, user_id: str) -> Optional[Document]:
    """Store the tutor's explanation of a topic as a searchable 'lesson' source.

    Re-indexing replaces the previous version, so the library always holds
    the latest explanation of each topic.
    """
    old_ids = (await db.execute(
        select(Document.id).where(Document.topic_id == topic.id, Document.source_type == "lesson")
    )).scalars().all()
    if old_ids:
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(old_ids)))
        await db.execute(delete(Document).where(Document.id.in_(old_ids)))

    text = strip_quiz_blocks(topic.explanation_content or "")
    chunks = chunk_sections(markdown_sections(text), settings.RAG_CHUNK_SIZE, settings.RAG_CHUNK_OVERLAP)
    doc = None
    if chunks:
        doc = Document(
            subject_id=topic.subject_id,
            user_id=user_id,
            topic_id=topic.id,
            filename=f"Lesson: {topic.title}",
            source_type="lesson",
            size_bytes=len(text.encode("utf-8")),
        )
        db.add(doc)
        await db.flush()
        await _store_chunks(db, doc, chunks)

    await db.commit()
    retriever.invalidate(topic.subject_id)
    return doc


def schedule_lesson_index(topic_id: str, user_id: str) -> None:
    """Index a finished lesson in the background, with its own DB session."""
    if not gemini.is_configured():
        return  # mock lessons are filler text; keep them out of the library

    async def run():
        try:
            async with AsyncSessionLocal() as db:
                topic = (await db.execute(select(Topic).where(Topic.id == topic_id))).scalar_one_or_none()
                if topic:
                    await index_lesson(db, topic, user_id)
        except Exception as e:
            print(f"[RAG] Lesson indexing failed for topic {topic_id}: {e}")

    task = asyncio.create_task(run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# ─── Retrieval ────────────────────────────────────────────────────
async def rewrite_query(message: str, topic_title: str, history: List[dict]) -> str:
    """Turn a follow-up like "go deeper on that" into a standalone search query."""
    fallback = f"{topic_title}: {message}"
    if not history or not gemini.is_configured():
        return fallback

    conversation = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in history[-4:])
    prompt = f"""Rewrite the student's latest message as a standalone search query for finding passages in their study material.
Resolve pronouns and vague references ("this", "that formula", "go deeper") using the conversation. Keep key technical terms.
Return ONLY the query, at most 25 words.

Current topic: {topic_title}
Conversation:
{conversation}

Latest message: {message}"""
    result = await gemini.generate(prompt, model=settings.GEMINI_FAST_MODEL, timeout=15)
    query = result.strip().splitlines()[0].strip().strip('"') if result and result.strip() else ""
    return query or fallback


async def retrieve(db: AsyncSession, subject_id: str, query: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    return await retriever.hybrid_search(
        db, subject_id, query, top_k=top_k or settings.RAG_TOP_K, candidates=settings.RAG_CANDIDATES
    )


def format_context(results: List[RetrievedChunk]) -> str:
    blocks = []
    for n, r in enumerate(results, 1):
        c = r.chunk
        where = [f'"{c.title}"']
        if c.page:
            where.append(f"page {c.page}")
        if c.heading:
            where.append(f'section "{c.heading}"')
        blocks.append(f"[{n}] {', '.join(where)}\n{c.content}")
    return "\n\n".join(blocks)


def source_payload(results: List[RetrievedChunk]) -> List[dict]:
    """Citation metadata sent to the frontend (and saved with the message)."""
    sources = []
    for n, r in enumerate(results, 1):
        c = r.chunk
        snippet = c.content[:_SNIPPET_CHARS] + ("…" if len(c.content) > _SNIPPET_CHARS else "")
        sources.append({
            "n": n,
            "chunk_id": c.id,
            "document_id": c.document_id,
            "title": c.title,
            "source_type": c.source_type,
            "page": c.page,
            "heading": c.heading,
            "snippet": snippet,
            "score": r.score,
            "dense_score": r.dense_score,
            "keyword_score": r.keyword_score,
        })
    return sources


def grounding_block(results: List[RetrievedChunk]) -> str:
    """Prompt section that grounds the tutor in retrieved material."""
    if not results:
        return ""
    return f"""REFERENCE MATERIAL — retrieved from the student's library (their uploaded documents and earlier lessons):
{format_context(results)}

GROUNDING RULES:
- When the reference material is relevant, build on it and cite it inline as [1], [2] right after the claim it supports.
- Only cite the numbers listed above. Never invent sources, page numbers or quotes.
- If the material does not cover something, say so briefly and continue from general knowledge without a citation."""


async def grounded_context(db: AsyncSession, subject_id: str, query: str) -> Tuple[str, List[dict]]:
    """Retrieve for a query → (prompt block, citation payload). Empty if the library has no match."""
    results = await retrieve(db, subject_id, query)
    return grounding_block(results), source_payload(results)


async def conversational_context(
    db: AsyncSession, subject_id: str, message: str, topic_title: str, history: List[dict]
) -> Tuple[str, List[dict], str]:
    """Like grounded_context, but rewrites a chat follow-up into a search query first.

    Returns (prompt block, citation payload, query used). Skips the rewrite
    LLM call entirely when the subject's library is empty.
    """
    if await retriever.library_size(db, subject_id) == 0:
        return "", [], ""
    query = await rewrite_query(message, topic_title, history)
    block, sources = await grounded_context(db, subject_id, query)
    return block, sources, query


# ─── Library Q&A ──────────────────────────────────────────────────
def library_qa_prompt(question: str, results: List[RetrievedChunk], persona_context: str) -> str:
    return f"""{persona_context}

You are answering a question about the student's own study library. Use ONLY the excerpts below.

EXCERPTS:
{format_context(results)}

QUESTION: {question}

RULES:
- Answer only from the excerpts and cite every claim inline as [n].
- If the excerpts do not contain the answer, say "I couldn't find that in your library" and suggest what to upload or search for. Do not answer from general knowledge.
- Use Markdown, and LaTeX ($...$) for math.
- Do NOT add a ```quiz block."""


def extractive_answer(results: List[RetrievedChunk]) -> str:
    """Fallback when Gemini is unavailable: show the best passages directly."""
    if not results:
        return "I couldn't find anything about that in your library yet. Try uploading notes or a PDF for this subject."
    lines = ["Gemini is unavailable right now, so here are the most relevant passages from your library:\n"]
    for n, r in enumerate(results[:3], 1):
        passage = " ".join(r.chunk.content[:600].split())
        lines.append(f"**[{n}] {r.chunk.title}**\n\n> {passage}\n")
    return "\n".join(lines)


def describe() -> dict:
    return {
        **gemini.describe(),
        "embedding_backends": embeddings.available_models(),
        "retrieval": "hybrid (dense + BM25, RRF)" if embeddings.available_models() else "keyword (BM25)",
        "top_k": settings.RAG_TOP_K,
        "chunk_size": settings.RAG_CHUNK_SIZE,
        "chunk_overlap": settings.RAG_CHUNK_OVERLAP,
    }
