from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from db.database import get_db
from db.models import Subject, Topic, Progress, UserPreferences, User, Message
from agents.orchestrator import professor_generate_outline
from utils.auth import get_current_user

router = APIRouter()


class CreateSubjectRequest(BaseModel):
    name: str
    purpose: str  # academic, job, research
    level: str  # beginner, intermediate, advanced


@router.post("/")
async def create_subject(
    data: CreateSubjectRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get user preferences
    prefs_result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))
    prefs = prefs_result.scalar_one_or_none()
    nickname = prefs.nickname if prefs else "buddy"
    ai_name = prefs.ai_teacher_name if prefs else "Lead"

    # Check for similarity
    base_context = None
    st_model = getattr(request.app.state, "st_model", None)
    if st_model is not None:
        existing_res = await db.execute(select(Subject).where(Subject.user_id == current_user.id))
        all_subjects = existing_res.scalars().all()
        if all_subjects:
            names = [s.name for s in all_subjects]
            embeddings = st_model.encode(names, convert_to_tensor=True)
            new_emb = st_model.encode([data.name], convert_to_tensor=True)
            from sentence_transformers import util
            cosine_scores = util.cos_sim(new_emb, embeddings)[0]
            max_idx = cosine_scores.argmax()
            if cosine_scores[max_idx] >= 0.8:
                base_context = all_subjects[max_idx].outline

    # Professor Agent generates outline (with detailed error handling)
    try:
        outline = await professor_generate_outline(
            subject=data.name,
            purpose=data.purpose,
            level=data.level,
            nickname=nickname,
            ai_name=ai_name,
            base_context=base_context,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to generate subject outline: {str(e)}. Please check your API keys and try again."
        )

    # Validate outline structure
    if not outline or not isinstance(outline, dict) or "topics" not in outline:
        raise HTTPException(
            status_code=503,
            detail="The AI generated an invalid outline. This usually means the LLM returned non-JSON text. Please try again."
        )

    subject = Subject(
        user_id=current_user.id,
        name=data.name,
        purpose=data.purpose,
        level=data.level,
        outline=outline,
    )
    db.add(subject)
    await db.flush()

    # Create topic records
    for topic_data in outline.get("topics", []):
        topic = Topic(
            subject_id=subject.id,
            title=topic_data["title"],
            index_order=topic_data["index"],
            status="pending",
        )
        db.add(topic)

    # Initialize progress
    progress = Progress(
        subject_id=subject.id,
        user_id=current_user.id,
        total_topics=outline.get("total_topics", len(outline.get("topics", []))),
        completed_topics=0,
    )
    db.add(progress)

    await db.commit()
    await db.refresh(subject)

    return {"id": str(subject.id), "outline": outline, "message": f"Subject '{data.name}' created!"}


@router.get("/")
async def list_subjects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Subject).where(Subject.user_id == current_user.id))
    subjects = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "purpose": s.purpose,
            "level": s.level,
            "current_topic_index": s.current_topic_index,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in subjects
    ]


@router.get("/{subject_id}")
async def get_subject(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.user_id == str(current_user.id))
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    topics_result = await db.execute(
        select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.index_order)
    )
    topics = topics_result.scalars().all()

    return {
        "id": str(subject.id),
        "name": subject.name,
        "purpose": subject.purpose,
        "level": subject.level,
        "outline": subject.outline,
        "current_topic_index": subject.current_topic_index,
        "topics": [
            {
                "id": str(t.id),
                "title": t.title,
                "index_order": t.index_order,
                "status": t.status,
            }
            for t in topics
        ],
    }


@router.delete("/{subject_id}")
async def delete_subject(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.user_id == str(current_user.id)
        )
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    try:
        # Use raw SQL DELETE — the database-level ON DELETE CASCADE ForeignKey
        # constraints will automatically clean up all child rows (topics, messages,
        # quiz_sets, attempts, notes, progress, feedback, weak_points).
        # This avoids the async lazy-loading issue with ORM cascade + db.delete().
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Subject).where(Subject.id == subject_id))
        await db.commit()
    except Exception as e:
        await db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete subject: {str(e)}")

    return {"message": "Subject deleted successfully"}