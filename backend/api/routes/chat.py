from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import AsyncIterator, Optional, List
import json
import asyncio
import re

import httpx

from db.database import get_db
from db.models import Subject, Topic, Message, Note, UserPreferences, Progress, User
from agents import fallback
from agents.orchestrator import (
    build_persona_context,
    tutor_explain_topic,
    tutor_handle_doubt,
    scribe_generate_notes,
)
from rag import service as rag
from utils.auth import get_current_user
from utils.config import settings
from utils.ownership import owned_topic
from utils.rate_limit import ai_rate_limit

router = APIRouter()

FALLBACK_MESSAGE = "Gemini is unavailable right now, so this is sample content rather than a real lesson."

# ── Navigation Intent Detection ──────────────────────────────────
# A message only advances the lesson when it is made purely of "move on" words
# ("next", "ok got it, continue", "I'm ready for the next topic"). A question
# mark, a question word or any other content means it is answered as a doubt.
_NAV_TRIGGERS = {
    "next", "continue", "proceed", "skip", "advance", "forward", "ready", "start", "begin",
    "understood", "understand", "got", "get", "clear", "ok", "okay", "yes", "yep", "yeah",
    "sure", "move", "go", "ahead", "done",
}
_NAV_FILLER = {
    "on", "it", "lets", "let's", "let", "us", "to", "the", "a", "topic", "please", "now", "i",
    "im", "i'm", "am", "we", "can", "that", "this", "all", "good", "great", "cool", "fine",
    "alright", "right", "perfect", "thanks", "thank", "you", "and", "so", "keep", "going",
    "with", "one", "part", "section", "concept", "subtopic", "chapter", "lesson", "makes",
    "sense", "for",
}
_QUESTION_WORDS = {
    "what", "why", "how", "when", "where", "which", "who", "whom", "whose", "explain",
    "describe", "define", "tell", "show", "example", "examples", "difference", "mean",
    "means", "meaning", "confused", "confusing", "help", "not", "don't", "dont", "didn't",
    "doesn't", "isn't",
}
_HF_NAV_LABEL = "navigation next proceeding continuing"


def navigation_intent(text: str) -> Optional[bool]:
    """True = clearly "move on", False = a question or content, None = unsure."""
    text = text.strip().lower().replace("’", "'")
    if not text or len(text) > 80 or "?" in text:
        return False
    words = re.findall(r"[a-z']+", text)
    if not words or any(w in _QUESTION_WORDS for w in words):
        return False
    if not any(w in _NAV_TRIGGERS for w in words):
        return False
    if all(w in _NAV_TRIGGERS or w in _NAV_FILLER for w in words):
        return True
    return None


async def _hf_says_navigation(text: str) -> Optional[bool]:
    """Optional zero-shot tiebreaker (Hugging Face bart-large-mnli) for unsure messages."""
    if not settings.HF_TOKEN or settings.HF_TOKEN.startswith("your-"):
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                "https://api-inference.huggingface.co/models/facebook/bart-large-mnli",
                headers={"Authorization": f"Bearer {settings.HF_TOKEN}"},
                json={"inputs": text, "parameters": {"candidate_labels": ["asking a question", _HF_NAV_LABEL]}},
            )
        if response.status_code == 200:
            labels = response.json().get("labels", [])
            return bool(labels) and labels[0] == _HF_NAV_LABEL
    except Exception as e:
        print(f"HF API Error: {e}")
    return None


async def is_navigation_command(text: str) -> bool:
    intent = navigation_intent(text)
    if intent is None:
        intent = await _hf_says_navigation(text)
    return bool(intent)  # still unsure → answer it; skipping content by mistake is worse


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _relay_tutor(chunks: AsyncIterator[str], collected: List[str]) -> AsyncIterator[str]:
    """Forward tutor chunks as SSE text events, warning once if the tutor fell back to mock content."""
    warned = False
    async for chunk in chunks:
        if not warned and "Tutor" in fallback.used():
            warned = True
            yield _sse({"type": "ai_fallback", "message": FALLBACK_MESSAGE})
        collected.append(chunk)
        yield _sse({"chunk": chunk, "type": "text"})


def _message_metadata(sources: list, query: Optional[str] = None) -> Optional[dict]:
    meta = {}
    if sources:
        meta["sources"] = sources
        if query:
            meta["query"] = query
    if "Tutor" in fallback.used():
        meta["ai_fallback"] = True
    return meta or None


async def _save_topic_notes(db: AsyncSession, topic: Topic, content: str) -> None:
    """Store the Scribe's notes for a topic, without overwriting notes the student edited."""
    note = (await db.execute(select(Note).where(Note.topic_id == topic.id))).scalar_one_or_none()
    if note is None:
        db.add(Note(subject_id=topic.subject_id, topic_id=topic.id, content=content, is_user_edited=False))
    elif not note.is_user_edited:
        note.content = content


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


@router.post("/explain/{topic_id}", dependencies=[Depends(ai_rate_limit)])
async def explain_topic(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream explanation for a topic."""
    topic = await owned_topic(db, topic_id, current_user)

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
        # RAG: ground the lesson in the student's library
        reference_ctx, sources = await rag.grounded_context(
            db, subject.id, f"{topic.title}: {topic_ctx['current_subtopic']}"
        )
        if sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        parts: List[str] = []
        async for event in _relay_tutor(tutor_explain_topic(
            topic_title=topic.title,
            subject=subject.name,
            previous_context=previous_context,
            persona_context=persona_ctx,
            topic_position=topic_ctx,
            reference_context=reference_ctx,
        ), parts):
            yield event
        full_content = "".join(parts)

        # Save message and update topic content
        msg = Message(
            topic_id=topic.id,
            user_id=current_user.id,
            role="assistant",
            content=full_content,
            agent_type="tutor",
            metadata_=_message_metadata(sources),
        )
        db.add(msg)
        topic.explanation_content = full_content
        db.add(topic)  # re-attach: FastAPI closes the request session before streaming starts

        # Scribe: generate notes in background
        yield f"data: {json.dumps({'type': 'notes_generating'})}\n\n"
        notes_content = await scribe_generate_notes(
            topic_title=topic.title,
            subject=subject.name,
            explanation_content=full_content,
        )
        await _save_topic_notes(db, topic, notes_content)
        yield f"data: {json.dumps({'type': 'notes_ready', 'notes': notes_content})}\n\n"
        await db.commit()
        rag.schedule_lesson_index(topic.id, current_user.id)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream_and_save(), media_type="text/event-stream")


@router.post("/doubt", dependencies=[Depends(ai_rate_limit)])
async def handle_doubt(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle a student message — either a doubt or a navigation command."""
    topic = await owned_topic(db, data.topic_id, current_user)

    subject_result = await db.execute(select(Subject).where(Subject.id == topic.subject_id))
    subject = subject_result.scalar_one_or_none()

    # ── Intent Detection ──────────────────────────────────────────
    if await is_navigation_command(data.message):
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
        # RAG: rewrite the follow-up into a standalone query, then retrieve
        reference_ctx, sources, search_query = await rag.conversational_context(
            db, subject.id, data.message, topic.title, history
        )
        if sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'query': search_query})}\n\n"

        parts: List[str] = []
        async for event in _relay_tutor(tutor_handle_doubt(
            doubt=data.message,
            topic_title=topic.title,
            explanation_so_far=topic.explanation_content or "",
            persona_context=persona_ctx,
            conversation_history=history,
            topic_position=topic_ctx,
            reference_context=reference_ctx,
        ), parts):
            yield event
        full_content = "".join(parts)

        ai_msg = Message(
            topic_id=topic.id,
            user_id=current_user.id,
            role="assistant",
            content=full_content,
            agent_type="tutor",
            metadata_=_message_metadata(sources, search_query),
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

            reference_ctx, sources = await rag.grounded_context(
                db, subject.id, f"{current_topic.title}: {topic_ctx['current_subtopic']}"
            )
            if sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

            parts: List[str] = []
            async for event in _relay_tutor(tutor_explain_topic(
                topic_title=current_topic.title,
                subject=subject.name,
                previous_context="", # Skip previous context for subtopics to keep it focused
                persona_context=persona_ctx_str,
                topic_position=topic_ctx,
                reference_context=reference_ctx,
            ), parts):
                yield event
            full_content = "".join(parts)

            msg = Message(
                topic_id=current_topic.id,
                user_id=user.id,
                role="assistant",
                content=full_content,
                agent_type="tutor",
                metadata_=_message_metadata(sources),
            )
            db.add(msg)
            existing_content = current_topic.explanation_content or ""
            current_topic.explanation_content = existing_content + "\n\n" + full_content
            db.add(current_topic)  # re-attach: FastAPI closes the request session before streaming starts

            yield f"data: {json.dumps({'type': 'notes_generating'})}\n\n"
            notes_content = await scribe_generate_notes(
                topic_title=current_topic.title,
                subject=subject.name,
                explanation_content=current_topic.explanation_content,
            )
            await _save_topic_notes(db, current_topic, notes_content)
            yield f"data: {json.dumps({'type': 'notes_ready', 'notes': notes_content})}\n\n"
            await db.commit()
            rag.schedule_lesson_index(current_topic.id, user.id)
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

        reference_ctx, sources = await rag.grounded_context(
            db, subject.id, f"{next_topic.title}: {topic_ctx['current_subtopic']}"
        )
        if sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        parts: List[str] = []
        async for event in _relay_tutor(tutor_explain_topic(
            topic_title=next_topic.title,
            subject=subject.name,
            previous_context=previous_context,
            persona_context=persona_ctx_str,
            topic_position=topic_ctx,
            reference_context=reference_ctx,
        ), parts):
            yield event
        full_content = "".join(parts)

        msg = Message(
            topic_id=next_topic.id,
            user_id=user.id,
            role="assistant",
            content=full_content,
            agent_type="tutor",
            metadata_=_message_metadata(sources),
        )
        db.add(msg)
        next_topic.explanation_content = full_content
        db.add(next_topic)  # re-attach: FastAPI closes the request session before streaming starts

        # Generate notes for new topic
        yield f"data: {json.dumps({'type': 'notes_generating'})}\n\n"
        notes_content = await scribe_generate_notes(
            topic_title=next_topic.title,
            subject=subject.name,
            explanation_content=full_content,
        )
        await _save_topic_notes(db, next_topic, notes_content)
        yield f"data: {json.dumps({'type': 'notes_ready', 'notes': notes_content})}\n\n"
        await db.commit()
        rag.schedule_lesson_index(next_topic.id, user.id)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream_next(), media_type="text/event-stream")


@router.get("/history/{topic_id}")
async def get_history(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    topic = await owned_topic(db, topic_id, current_user)
    msgs_result = await db.execute(
        select(Message).where(Message.topic_id == topic.id).order_by(Message.created_at)
    )
    msgs = msgs_result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "agent_type": m.agent_type,
            "sources": (m.metadata_ or {}).get("sources", []),
            "query": (m.metadata_ or {}).get("query"),
            "ai_fallback": bool((m.metadata_ or {}).get("ai_fallback")),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]