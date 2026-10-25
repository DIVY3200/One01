import json
import os
import traceback

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.chat import get_persona_context
from db.database import get_db
from db.models import Document, Subject, User
from agents import fallback
from llm import gemini
from rag import service as rag
from rag.ingest import SUPPORTED_EXTENSIONS, UnsupportedFileError
from utils.auth import get_current_user
from utils.config import settings
from utils.ownership import owned_subject
from utils.rate_limit import ai_rate_limit

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class AskRequest(BaseModel):
    question: str


def _document_out(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "source_type": doc.source_type,
        "topic_id": str(doc.topic_id) if doc.topic_id else None,
        "size_bytes": doc.size_bytes,
        "num_pages": doc.num_pages,
        "num_chunks": doc.num_chunks,
        "embedding_model": doc.embedding_model,
        "status": doc.status,
        "error": doc.error,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get("/status")
async def rag_status(current_user: User = Depends(get_current_user)):
    """Active LLM / embedding models and retrieval mode."""
    return rag.describe()


@router.get("/{subject_id}/documents")
async def list_documents(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject = await owned_subject(db, subject_id, current_user)
    result = await db.execute(
        select(Document).where(Document.subject_id == subject.id).order_by(Document.created_at.desc())
    )
    return [_document_out(d) for d in result.scalars().all()]


@router.post("/{subject_id}/documents", dependencies=[Depends(ai_rate_limit)])
async def upload_document(
    subject_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF / Markdown / text file into the subject's library."""
    subject = await owned_subject(db, subject_id, current_user)
    filename = os.path.basename(file.filename or "upload.txt")
    if os.path.splitext(filename)[1].lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a PDF, Markdown (.md) or text (.txt) file.")

    max_bytes = settings.RAG_MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.RAG_MAX_UPLOAD_MB} MB.")
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")

    try:
        doc = await rag.ingest_upload(db, subject.id, current_user.id, filename, data)
    except UnsupportedFileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=f"Could not read '{filename}': {e}")
    return _document_out(doc)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .join(Subject, Document.subject_id == Subject.id)
        .where(Document.id == document_id, Subject.user_id == str(current_user.id))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await rag.delete_document(db, doc)
    return {"message": "Document deleted"}


@router.post("/{subject_id}/search", dependencies=[Depends(ai_rate_limit)])
async def search_library(
    subject_id: str,
    data: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Raw hybrid retrieval results with per-retriever scores (retrieval inspector)."""
    subject = await owned_subject(db, subject_id, current_user)
    results = await rag.retrieve(db, subject.id, data.query, top_k=max(1, min(data.top_k, 20)))
    return {"query": data.query, "results": rag.source_payload(results)}


@router.post("/{subject_id}/ask", dependencies=[Depends(ai_rate_limit)])
async def ask_library(
    subject_id: str,
    data: AskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Answer a question strictly from the subject's library, streamed with citations."""
    subject = await owned_subject(db, subject_id, current_user)
    persona_ctx = await get_persona_context(current_user, subject, db)
    # Retrieve before streaming: the request's DB session is closed once the stream starts.
    results = await rag.retrieve(db, subject.id, data.question)

    async def stream_answer():
        yield f"data: {json.dumps({'type': 'sources', 'sources': rag.source_payload(results)})}\n\n"

        streamed = False
        if results:
            async for chunk in gemini.stream(rag.library_qa_prompt(data.question, results, persona_ctx)):
                streamed = True
                yield f"data: {json.dumps({'chunk': chunk, 'type': 'text'})}\n\n"
        if not streamed:
            if results:  # Gemini failed, so show the passages themselves
                fallback.note("Tutor")
                yield f"data: {json.dumps({'type': 'ai_fallback', 'message': 'Gemini is unavailable right now, so these are the closest passages rather than an answer.'})}\n\n"
            yield f"data: {json.dumps({'chunk': rag.extractive_answer(results), 'type': 'text'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream_answer(), media_type="text/event-stream")
