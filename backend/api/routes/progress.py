import time
from typing import Dict, Tuple

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func

from api.routes.quiz import subject_quiz_average
from db.database import get_db
from db.models import Progress, User
from utils.auth import get_current_user
from utils.ownership import owned_subject

router = APIRouter()

# Heartbeats arrive once a minute while the student is studying; ignore extras
# (several open tabs, retries) that come in faster than that.
_HEARTBEAT_MIN_GAP_SECONDS = 50
_last_heartbeat: Dict[Tuple[str, str], float] = {}


@router.get("/{subject_id}")
async def get_progress(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject = await owned_subject(db, subject_id, current_user)
    result = await db.execute(
        select(Progress).where(Progress.subject_id == subject.id, Progress.user_id == current_user.id)
    )
    prog = result.scalar_one_or_none()
    if not prog:
        return {"total_topics": 0, "completed_topics": 0, "completion_percent": 0, "avg_quiz_score": 0, "weak_concepts": [], "strong_concepts": [], "time_spent_minutes": 0}
    return {
        "total_topics": prog.total_topics,
        "completed_topics": prog.completed_topics,
        "completion_percent": round((prog.completed_topics / max(prog.total_topics, 1)) * 100, 1),
        "avg_quiz_score": round(await subject_quiz_average(db, subject.id, current_user.id), 1),
        "weak_concepts": prog.weak_concepts or [],
        "strong_concepts": prog.strong_concepts or [],
        "time_spent_minutes": prog.time_spent_minutes or 0,
        "last_activity": prog.last_activity.isoformat() if prog.last_activity else None,
    }


@router.post("/{subject_id}/heartbeat")
async def study_heartbeat(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Adds one minute of study time; sent each minute while a study page is visible and in use."""
    subject = await owned_subject(db, subject_id, current_user)
    key = (str(current_user.id), str(subject.id))
    now = time.monotonic()
    last = _last_heartbeat.get(key)
    if last is not None and now - last < _HEARTBEAT_MIN_GAP_SECONDS:
        return {"counted": False}
    _last_heartbeat[key] = now

    result = await db.execute(
        select(Progress).where(Progress.subject_id == subject.id, Progress.user_id == current_user.id)
    )
    prog = result.scalar_one_or_none()
    if not prog:
        return {"counted": False}
    prog.time_spent_minutes = (prog.time_spent_minutes or 0) + 1
    prog.last_activity = func.now()
    await db.commit()
    return {"counted": True, "time_spent_minutes": prog.time_spent_minutes}
