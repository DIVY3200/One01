from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from db.database import get_db
from db.models import Progress, Feedback, Topic, Subject, User, UserPreferences
from agents.orchestrator import scribe_process_feedback, generate_question_bank
from utils.auth import get_current_user

# ─── Progress Router ──────────────────────────────────────────────
progress_router = APIRouter()


@progress_router.get("/{subject_id}")
async def get_progress(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Progress).where(
            Progress.subject_id == subject_id,
            Progress.user_id == current_user.id
        )
    )
    prog = result.scalar_one_or_none()
    if not prog:
        raise HTTPException(status_code=404, detail="Progress not found")

    return {
        "total_topics": prog.total_topics,
        "completed_topics": prog.completed_topics,
        "completion_percent": round((prog.completed_topics / max(prog.total_topics, 1)) * 100, 1),
        "avg_quiz_score": round(prog.avg_quiz_score, 1),
        "weak_concepts": prog.weak_concepts or [],
        "strong_concepts": prog.strong_concepts or [],
        "time_spent_minutes": prog.time_spent_minutes,
        "last_activity": prog.last_activity.isoformat() if prog.last_activity else None,
    }


# ─── Feedback Router ──────────────────────────────────────────────
feedback_router = APIRouter()


class FeedbackRequest(BaseModel):
    content: str
    categories: Optional[dict] = None


@feedback_router.post("/{subject_id}")
async def submit_feedback(
    subject_id: str,
    data: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subject_result.scalar_one_or_none()

    prefs_result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))
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


# ─── Topics Router ────────────────────────────────────────────────
topics_router = APIRouter()


@topics_router.patch("/{topic_id}/complete")
async def mark_topic_complete(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    from sqlalchemy.sql import func
    topic.status = "completed"
    topic.completed_at = func.now()

    # Update progress
    prog_result = await db.execute(
        select(Progress).where(Progress.subject_id == topic.subject_id, Progress.user_id == current_user.id)
    )
    prog = prog_result.scalar_one_or_none()
    if prog:
        prog.completed_topics += 1
        prog.last_activity = func.now()

    await db.commit()
    return {"message": "Topic marked complete"}


# ─── Question Bank Router ─────────────────────────────────────────
qbank_router = APIRouter()


class QuestionBankRequest(BaseModel):
    subject_id: str
    topic_title: str
    question_type: str  # mcq, theory, numerical
    count: int = 5


@qbank_router.post("/generate")
async def generate_qbank(
    data: QuestionBankRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject_result = await db.execute(select(Subject).where(Subject.id == data.subject_id))
    subject = subject_result.scalar_one_or_none()

    result = await generate_question_bank(
        subject=subject.name if subject else "Unknown",
        topic_title=data.topic_title,
        question_type=data.question_type,
        count=min(data.count, 20),
        level=subject.level if subject else "intermediate",
    )
    return result