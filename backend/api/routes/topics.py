from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from db.database import get_db
from db.models import Topic, Progress, User
from utils.auth import get_current_user
from utils.ownership import owned_topic

router = APIRouter()


@router.get("/{topic_id}")
async def get_topic(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    topic = await owned_topic(db, topic_id, current_user)
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
    topic = await owned_topic(db, topic_id, current_user)
    if topic.status != "completed":
        topic.status = "completed"
        topic.completed_at = func.now()
        await db.flush()

    prog_result = await db.execute(
        select(Progress).where(
            Progress.subject_id == topic.subject_id,
            Progress.user_id == current_user.id,
        )
    )
    prog = prog_result.scalar_one_or_none()
    if prog:
        # Count instead of incrementing, so completing the same topic twice can't inflate progress
        completed = await db.execute(
            select(func.count(Topic.id)).where(Topic.subject_id == topic.subject_id, Topic.status == "completed")
        )
        prog.completed_topics = completed.scalar() or 0
        prog.last_activity = func.now()

    await db.commit()
    return {"message": "Topic marked complete"}
