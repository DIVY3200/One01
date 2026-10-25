"""Lookups that only return rows belonging to the current user.

Every route that takes an ID from the URL or body goes through one of these,
so a user can never read or change another user's data by guessing IDs.
Rows owned by someone else are reported as 404, the same as missing rows.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Note, QuizSet, Subject, Topic, User


async def owned_subject(db: AsyncSession, subject_id: str, user: User) -> Subject:
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.user_id == user.id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


async def owned_topic(db: AsyncSession, topic_id: str, user: User) -> Topic:
    result = await db.execute(
        select(Topic)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Topic.id == topic_id, Subject.user_id == user.id)
    )
    topic = result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


async def owned_note(db: AsyncSession, note_id: str, user: User) -> Note:
    result = await db.execute(
        select(Note)
        .join(Subject, Note.subject_id == Subject.id)
        .where(Note.id == note_id, Subject.user_id == user.id)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


async def owned_quiz_set(db: AsyncSession, quiz_set_id: str, user: User) -> QuizSet:
    result = await db.execute(
        select(QuizSet)
        .join(Subject, QuizSet.subject_id == Subject.id)
        .where(QuizSet.id == quiz_set_id, Subject.user_id == user.id)
    )
    quiz_set = result.scalar_one_or_none()
    if not quiz_set:
        raise HTTPException(status_code=404, detail="Quiz set not found")
    return quiz_set
