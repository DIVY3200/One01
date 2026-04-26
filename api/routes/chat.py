from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import json
import asyncio
import re

from db.database import get_db
from db.models import Subject, Topic, Message, UserPreferences, Progress, User
from agents.orchestrator import (
    build_persona_context,
    tutor_explain_topic,
    tutor_handle_doubt,
    scribe_generate_notes,
)
from utils.auth import get_current_user

router = APIRouter()

# ── Navigation Intent Detection ──────────────────────────────────
NAVIGATION_PATTERNS = [
    r"\bnext\b", r"\bmove\s+on\b", r"\bproceed\b", r"\bcontinue\b",
    r"\bunderstood\b", r"\bgot\s+it\b", r"\blets?\s+go\b", r"\blet'?s\s+go\b",
    r"\bnext\s+topic\b", r"\bskip\b", r"\bforward\b", r"\bready\b",
    r"\bstart\b", r"\bbegin\b", r"\bgo\s+ahead\b", r"\bi\s+understand\b",
    r"\bmove\s+to\s+next\b", r"\badvance\b", r"\bokay\s+next\b", r"\bok\s+next\b",
    r"\byes\b", r"\byep\b", r"\byeah\b", r"\bsure\b", r"\bclear\b",
]
_NAV_RE = re.compile("|".join(NAVIGATION_PATTERNS), re.IGNORECASE)


import os
import requests

def is_navigation_command(text: str) -> bool:
    """Detect if user input is a navigation command vs. a genuine question using Hugging Face Zero-Shot."""
    text = text.strip()
    if len(text) > 60:
        return False

    hf_token = os.getenv("HF_TOKEN") or "your-hf-token-here"
    if hf_token and hf_token != "your-hf-token-here":
        api_url = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
        headers = {"Authorization": f"Bearer {hf_token}"}
        payload = {
            "inputs": text,
            "parameters": {"candidate_labels": ["asking a question", "navigation next proceeding continuing"]}
        }
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=3.0)
            if response.status_code == 200:
                result = response.json()
                if result.get("labels", [])[0] == "navigation next proceeding continuing":
                    return True
                return False
        except Exception as e:
            print(f"HF API Error: {e}")
            pass

    # Fallback to Regex
    return bool(_NAV_RE.search(text))


class ChatRequest(BaseModel):
    topic_id: str
    message: str
    message_type: str = "doubt"  # explain, doubt


async def get_persona_context(user: User, subject: Subject, db: AsyncSession) -> str:
    prefs_result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == user.id))
    prefs = prefs_result.scalar_one_or_none()

    progress_result = await db.execute(
        select(Progress).where(Progress.subject_id == subject.id, Progress.user_id == user.id)
    )
    progress = progress_result.scalar_one_or_none()
    weak_concepts = progress.weak_concepts if progress and progress.weak_concepts else []

    return build_persona_context(
        teaching_style=prefs.teaching_style if prefs else "mentor",
        ai_name=prefs.ai_teacher_name if prefs else "Lead",
        ai_gender=prefs.ai_gender if prefs else "neutral",
        nickname=prefs.nickname if prefs else "buddy",
        subject=subject.name,
        purpose=subject.purpose,
        level=subject.level,
        weak_concepts=weak_concepts,
    )


async def _get_topic_context(topic: Topic, subject: Subject, db: AsyncSession) -> dict:
    """Build rich context about the current topic position in the outline."""
    # Get all topics for this subject ordered by index
    all_topics_result = await db.execute(
        select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.index_order)
    )
    all_topics = all_topics_result.scalars().all()

    current_idx = None
    prev_topic = None
    next_topic = None
    for i, t in enumerate(all_topics):
        if t.id == topic.id:
            current_idx = i
            if i > 0:
                prev_topic = all_topics[i - 1]
            if i < len(all_topics) - 1:
                next_topic = all_topics[i + 1]
            break

    topic_outline = next((t for t in subject.outline.get("topics", []) if t.get("index") == topic.index_order), {})
    subtopics = topic_outline.get("subtopics", [])
    current_sub_idx = getattr(topic, 'current_subtopic_index', 0)
    current_sub = subtopics[current_sub_idx] if subtopics and current_sub_idx < len(subtopics) else topic.title

    return {
        "current_index": current_idx,
        "total_topics": len(all_topics),
        "current_title": topic.title,
        "prev_title": prev_topic.title if prev_topic else None,
        "prev_was_completed": prev_topic.status == "completed" if prev_topic else False,
        "next_title": next_topic.title if next_topic else None,
        "next_topic": next_topic,
        "all_topics": all_topics,
        "subtopics": subtopics,
        "current_subtopic_index": current_sub_idx,
        "current_subtopic": current_sub,
    }


async def _advance_to_next_topic(
    current_topic: Topic,
    subject: Subject,
    user: User,
    db: AsyncSession,
) -> Optional[Topic]:
    """Mark current topic completed and return the next one, or None."""
    from sqlalchemy.sql import func

    # Mark current as completed
    current_topic.status = "completed"
    current_topic.completed_at = func.now()

    # Advance subject's current_topic_index
    topic_ctx_result = await db.execute(
        select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.index_order)
    )
    all_topics = topic_ctx_result.scalars().all()

    next_topic = None
    for i, t in enumerate(all_topics):
        if t.id == current_topic.id and i < len(all_topics) - 1:
            next_topic = all_topics[i + 1]
            subject.current_topic_index = i + 1
            next_topic.status = "in_progress"
            break

    # Update progress record
    prog_result = await db.execute(
        select(Progress).where(Progress.subject_id == subject.id, Progress.user_id == user.id)
    )
    prog = prog_result.scalar_one_or_none()
    if prog:
        completed_count = sum(1 for t in all_topics if t.status == "completed" or t.id == current_topic.id)
        prog.completed_topics = completed_count
        prog.last_activity = func.now()

    await db.commit()
    return next_topic


@router.post("/explain/{topic_id}")
async def explain_topic(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream explanation for a topic."""
    topic_result = await db.execute(select(Topic).where(Topic.id == topic_id))
    topic = topic_result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    subject_result = await db.execute(select(Subject).where(Subject.id == topic.subject_id))
    subject = subject_result.scalar_one_or_none()

    persona_ctx = await get_persona_context(current_user, subject, db)
    topic_ctx = await _get_topic_context(topic, subject, db)

    # Build previous context from the prior topic's explanation
    previous_context = ""
    if topic_ctx["prev_title"] and topic_ctx["current_index"] > 0:
        prev_topics = topic_ctx["all_topics"]
        prev_t = prev_topics[topic_ctx["current_index"] - 1]
        if prev_t.explanation_content:
            # Summarize: just take the first 300 chars to avoid bloat
            previous_context = f"Previously covered: '{prev_t.title}'. Key points: {prev_t.explanation_content[:300]}..."

    # Update topic status
    topic.status = "in_progress"
    await db.commit()

    async def stream_and_save():
        full_content = ""
        async for chunk in tutor_explain_topic(
            topic_title=topic.title,
            subject=subject.name,
            previous_context=previous_context,
            persona_context=persona_ctx,
            topic_position=topic_ctx,
        ):
            full_content += chunk
            yield f"data: {json.dumps({'chunk': chunk, 'type': 'text'})}\n\n"

        # Save message and update topic content
        msg = Message(
            topic_id=topic.id,
            user_id=current_user.id,
            role="assistant",
            content=full_content,
            agent_type="tutor",
        )
        db.add(msg)
        topic.explanation_content = full_content

        # Scribe: generate notes in background
        yield f"data: {json.dumps({'type': 'notes_generating'})}\n\n"
        notes_content = await scribe_generate_notes(
            topic_title=topic.title,
            subject=subject.name,
            explanation_content=full_content,
        )
        yield f"data: {json.dumps({'type': 'notes_ready', 'notes': notes_content})}\n\n"
        await db.commit()
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream_and_save(), media_type="text/event-stream")


@router.post("/doubt")
async def handle_doubt(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle a student message — either a doubt or a navigation command."""
    topic_result = await db.execute(select(Topic).where(Topic.id == data.topic_id))
    topic = topic_result.scalar_one_or_none()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    subject_result = await db.execute(select(Subject).where(Subject.id == topic.subject_id))
    subject = subject_result.scalar_one_or_none()

    # ── Intent Detection ──────────────────────────────────────────
    if is_navigation_command(data.message):
        return await _handle_topic_advance(
            current_topic=topic,
            subject=subject,
            user=current_user,
            user_message=data.message,
            db=db,
        )

    # ── Regular Doubt Flow ────────────────────────────────────────
    persona_ctx = await get_persona_context(current_user, subject, db)
    topic_ctx = await _get_topic_context(topic, subject, db)

    # Get conversation history
    msgs_result = await db.execute(
        select(Message).where(Message.topic_id == topic.id).order_by(Message.created_at)
    )
    msgs = msgs_result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in msgs[-10:]]

    # Save user message
    user_msg = Message(
        topic_id=topic.id,
        user_id=current_user.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)

    # Adaptive Learning Sync (Memory)
    is_failed_quiz = "I think I misunderstood" in data.message
    if is_failed_quiz:
        from db.models import WeakPoint
        wp = WeakPoint(subject_id=subject.id, topic_id=topic.id, user_id=current_user.id)
        db.add(wp)

    await db.commit()

    async def stream_response():
        full_content = ""
        async for chunk in tutor_handle_doubt(
            doubt=data.message,
            topic_title=topic.title,
            explanation_so_far=topic.explanation_content or "",
            persona_context=persona_ctx,
            conversation_history=history,
            topic_position=topic_ctx,
        ):
            full_content += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        ai_msg = Message(
            topic_id=topic.id,
            user_id=current_user.id,
            role="assistant",
            content=full_content,
            agent_type="tutor",
        )
        db.add(ai_msg)

        # Adaptive Learning Sync (Notes)
        if is_failed_quiz:
            from db.models import Note
            note_result = await db.execute(select(Note).where(Note.subject_id == subject.id, Note.topic_id == None))
            note = note_result.scalar_one_or_none()
            remedial_excerpt = full_content.split("```")[0].strip()[:500]
            append_text = f"\n\n**Mistake to Review: {topic.title}**\n- Failed concept evaluation. Remedial: {remedial_excerpt}..."
            
            if not note:
                note = Note(subject_id=subject.id, content=append_text, is_user_edited=False)
                db.add(note)
            else:
                note.content = (note.content or "") + append_text

        await db.commit()
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


async def _handle_topic_advance(
    current_topic: Topic,
    subject: Subject,
    user: User,
    user_message: str,
    db: AsyncSession,
):
    """Auto-advance to the next sub-topic, or next main topic if all sub-topics are completed."""
    # Save user navigation message
    user_msg = Message(
        topic_id=current_topic.id,
        user_id=user.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)

    topic_ctx = await _get_topic_context(current_topic, subject, db)
    subtopics = topic_ctx["subtopics"]
    current_sub_idx = topic_ctx["current_subtopic_index"]

    # Check if we can advance within the SAME main topic
    if subtopics and current_sub_idx < len(subtopics) - 1:
        current_topic.current_subtopic_index += 1
        await db.commit()
        
        # Refresh context for the new subtopic
        persona_ctx_str = await get_persona_context(user, subject, db)
        topic_ctx = await _get_topic_context(current_topic, subject, db)
        
        async def stream_next_subtopic():
            # Add a visual separator if this is the same topic stream
            chunk_data = json.dumps({'chunk': '\n\n---\n\n', 'type': 'text'})
            yield f"data: {chunk_data}\n\n"
            
            full_content = ""
            async for chunk in tutor_explain_topic(
                topic_title=current_topic.title,
                subject=subject.name,
                previous_context="", # Skip previous context for subtopics to keep it focused
                persona_context=persona_ctx_str,
                topic_position=topic_ctx,
            ):
                full_content += chunk
                yield f"data: {json.dumps({'chunk': chunk, 'type': 'text'})}\n\n"

            msg = Message(
                topic_id=current_topic.id,
                user_id=user.id,
                role="assistant",
                content=full_content,
                agent_type="tutor",
            )
            db.add(msg)
            existing_content = current_topic.explanation_content or ""
            current_topic.explanation_content = existing_content + "\n\n" + full_content

            yield f"data: {json.dumps({'type': 'notes_generating'})}\n\n"
            notes_content = await scribe_generate_notes(
                topic_title=current_topic.title,
                subject=subject.name,
                explanation_content=current_topic.explanation_content,
            )
            yield f"data: {json.dumps({'type': 'notes_ready', 'notes': notes_content})}\n\n"
            await db.commit()
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(stream_next_subtopic(), media_type="text/event-stream")

    # If all subtopics are completed, advance to the NEXT MAIN TOPIC
    next_topic = await _advance_to_next_topic(current_topic, subject, user, db)

    if not next_topic:
        # All topics completed — congratulate
        async def stream_congrats():
            congrats = (
                "🎉 **Congratulations!** You've completed all topics in this subject! "
                "You've covered every concept in the outline. "
                "Feel free to revisit any topic from the sidebar, take quizzes, or explore a new subject!"
            )
            yield f"data: {json.dumps({'chunk': congrats, 'type': 'text'})}\n\n"

            ai_msg = Message(
                topic_id=current_topic.id,
                user_id=user.id,
                role="assistant",
                content=congrats,
                agent_type="tutor",
            )
            db.add(ai_msg)
            await db.commit()
            yield f"data: {json.dumps({'type': 'subject_complete'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(stream_congrats(), media_type="text/event-stream")

    # Stream explanation for the next topic
    persona_ctx_str = await get_persona_context(user, subject, db)
    topic_ctx = await _get_topic_context(next_topic, subject, db)

    # Previous context from the topic we just completed
    previous_context = ""
    if current_topic.explanation_content:
        previous_context = (
            f"Previously covered: '{current_topic.title}'. "
            f"Key points: {current_topic.explanation_content[:300]}..."
        )

    async def stream_next():
        # Notify frontend about the topic change
        yield f"data: {json.dumps({'type': 'topic_advanced', 'new_topic_id': str(next_topic.id), 'new_topic_title': next_topic.title, 'completed_topic_id': str(current_topic.id)})}\n\n"

        full_content = ""
        async for chunk in tutor_explain_topic(
            topic_title=next_topic.title,
            subject=subject.name,
            previous_context=previous_context,
            persona_context=persona_ctx_str,
            topic_position=topic_ctx,
        ):
            full_content += chunk
            yield f"data: {json.dumps({'chunk': chunk, 'type': 'text'})}\n\n"

        msg = Message(
            topic_id=next_topic.id,
            user_id=user.id,
            role="assistant",
            content=full_content,
            agent_type="tutor",
        )
        db.add(msg)
        next_topic.explanation_content = full_content

        # Generate notes for new topic
        yield f"data: {json.dumps({'type': 'notes_generating'})}\n\n"
        notes_content = await scribe_generate_notes(
            topic_title=next_topic.title,
            subject=subject.name,
            explanation_content=full_content,
        )
        yield f"data: {json.dumps({'type': 'notes_ready', 'notes': notes_content})}\n\n"
        await db.commit()
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream_next(), media_type="text/event-stream")


@router.get("/history/{topic_id}")
async def get_history(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msgs_result = await db.execute(
        select(Message).where(Message.topic_id == topic_id).order_by(Message.created_at)
    )
    msgs = msgs_result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "agent_type": m.agent_type,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]