from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from db.database import get_db
from db.models import Feedback, Subject, UserPreferences, User
from agents.orchestrator import scribe_process_feedback
from utils.auth import get_current_user

router = APIRouter()


class FeedbackRequest(BaseModel):
    content: str
    categories: Optional[dict] = None


@router.post("/{subject_id}")
async def submit_feedback(
    subject_id: str,
    data: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subject_result.scalar_one_or_none()

    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()

    adjustment = await scribe_process_feedback(
        feedback_text=data.content,
        subject=subject.name if subject else "Unknown",
        ai_name=prefs.ai_teacher_name if prefs else "Lead",
        teaching_style=prefs.teaching_style if prefs else "mentor",
    )

    fb = Feedback(
        subject_id=subject_id,
        user_id=current_user.id,
        content=data.content,
        categories=data.categories,
        ai_response=adjustment.get("response_to_student", ""),
    )
    db.add(fb)
    await db.commit()

    return {
        "message": "Feedback received",
        "ai_response": adjustment.get("response_to_student", ""),
        "adjustments": adjustment,
    }


@router.get("/{subject_id}")
async def get_feedback(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback)
        .where(Feedback.subject_id == subject_id, Feedback.user_id == current_user.id)
        .order_by(Feedback.created_at.desc())
    )
    feedbacks = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "content": f.content,
            "ai_response": f.ai_response,
            "categories": f.categories,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in feedbacks
    ]