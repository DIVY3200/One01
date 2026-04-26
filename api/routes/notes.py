from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from db.database import get_db
from db.models import Note, Subject, Topic, User
from utils.auth import get_current_user

router = APIRouter()


class UpdateNoteRequest(BaseModel):
    content: str

class SyncInsightRequest(BaseModel):
    concept: str
    is_correct: bool
    explanation: str

@router.post("/{subject_id}/sync-insight")
async def sync_insight(
    subject_id: str,
    data: SyncInsightRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Append insight to the subject's general notes
    note_result = await db.execute(select(Note).where(Note.subject_id == subject_id, Note.topic_id == None))
    note = note_result.scalar_one_or_none()
    
    header = "Key Insight (Mastered)" if data.is_correct else "Mistake to Review"
    append_text = f"\n\n**{header}: {data.concept}**\n- {data.explanation}"
    
    if not note:
        note = Note(subject_id=subject_id, content=append_text, is_user_edited=False)
        db.add(note)
    else:
        note.content = (note.content or "") + append_text
    
    # 2. Update Progress weak/strong concepts for PersonaManager awareness
    from db.models import Progress
    prog_result = await db.execute(
        select(Progress).where(Progress.subject_id == subject_id, Progress.user_id == current_user.id)
    )
    prog = prog_result.scalar_one_or_none()
    if prog:
        weak = set(prog.weak_concepts or [])
        strong = set(prog.strong_concepts or [])
        if data.is_correct:
            strong.add(data.concept)
            weak.discard(data.concept)
        else:
            weak.add(data.concept)
            strong.discard(data.concept)
        prog.weak_concepts = list(weak)
        prog.strong_concepts = list(strong)
    
    await db.commit()
    return {"message": "Insight synced", "flagged_as": "strong" if data.is_correct else "weak"}


@router.get("/{subject_id}")
async def get_notes(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Note, Topic.title)
        .join(Topic, Note.topic_id == Topic.id, isouter=True)
        .where(Note.subject_id == subject_id)
        .order_by(Note.created_at)
    )
    rows = result.all()
    return [
        {
            "id": str(n.id),
            "topic_id": str(n.topic_id) if n.topic_id else None,
            "topic_title": title,
            "content": n.content,
            "is_user_edited": n.is_user_edited,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n, title in rows
    ]


@router.put("/{note_id}")
async def update_note(
    note_id: str,
    data: UpdateNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.content = data.content
    note.is_user_edited = True
    await db.commit()
    return {"message": "Note updated"}