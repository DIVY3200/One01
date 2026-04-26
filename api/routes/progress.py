from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_db
from db.models import Progress, User
from utils.auth import get_current_user

router = APIRouter()

@router.get("/{subject_id}")
async def get_progress(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Progress).where(Progress.subject_id == subject_id, Progress.user_id == current_user.id)
    )
    prog = result.scalar_one_or_none()
    if not prog:
        return {"total_topics": 0, "completed_topics": 0, "completion_percent": 0, "avg_quiz_score": 0, "weak_concepts": [], "strong_concepts": [], "time_spent_minutes": 0}
    return {
        "total_topics": prog.total_topics,
        "completed_topics": prog.completed_topics,
        "completion_percent": round((prog.completed_topics / max(prog.total_topics, 1)) * 100, 1),
        "avg_quiz_score": round(prog.avg_quiz_score or 0, 1),
        "weak_concepts": prog.weak_concepts or [],
        "strong_concepts": prog.strong_concepts or [],
        "time_spent_minutes": prog.time_spent_minutes or 0,
        "last_activity": prog.last_activity.isoformat() if prog.last_activity else None,
    }