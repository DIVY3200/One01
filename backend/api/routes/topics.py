from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional

from db.database import get_db
from db.models import Topic, Progress, Subject, User
from utils.auth import get_current_user

router = APIRouter()


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return {
        "id": str(topic.id),
        "title": topic.title,
        "index_order": topic.index_order,
        "status": topic.status,
        "explanation_content": topic.explanation_content,
        "subject_id": str(topic.subject_id),
    }


@router.patch("/{topic_id}/complete")
async def mark_topic_complete(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    topic.status = "completed"
    topic.completed_at = func.now()

    prog_result = await db.execute(
        select(Progress).where(
            Progress.subject_id == topic.subject_id,
            Progress.user_id == current_user.id,
        )
    )
    prog = prog_result.scalar_one_or_none()
    if prog:
        prog.completed_topics = min(prog.completed_topics + 1, prog.total_topics)
        prog.last_activity = func.now()

    await db.commit()
    return {"message": "Topic marked complete"}