from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from db.database import get_db
from db.models import Topic, Subject, QuizSet, QuizAttempt, Progress, User
from agents.orchestrator import examiner_generate_quiz, examiner_analyze_answers
from utils.auth import get_current_user

router = APIRouter()


class GenerateQuizRequest(BaseModel):
    topic_id: Optional[str] = None
    subject_id: Optional[str] = None
    topic_title: Optional[str] = None
    question_type: Optional[str] = None
    count: int = 5
    quiz_types: List[str] = ["mcq", "theory"]


class SubmitAnswersRequest(BaseModel):
    quiz_set_id: str
    answers: List[str]


@router.post("/generate")
async def generate_quiz(
    data: GenerateQuizRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    topic = None
    if data.topic_id:
        topic_result = await db.execute(select(Topic).where(Topic.id == data.topic_id))
        topic = topic_result.scalar_one_or_none()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

    subject_id_to_use = topic.subject_id if topic else data.subject_id
    if not subject_id_to_use:
        raise HTTPException(status_code=400, detail="Missing subject_id or topic_id")

    subject_result = await db.execute(select(Subject).where(Subject.id == subject_id_to_use))
    subject = subject_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    topic_title = topic.title if topic else data.topic_title

    # specific subtopics
    subtopics = []
    if subject.outline and "topics" in subject.outline:
        for t in subject.outline["topics"]:
            if t.get("title") == topic_title:
                subtopics = t.get("subtopics", [])
                break

    progress_result = await db.execute(
        select(Progress).where(Progress.subject_id == subject.id, Progress.user_id == current_user.id)
    )
    progress = progress_result.scalar_one_or_none()
    weak_concepts = progress.weak_concepts if progress else []

    created_sets = []
    types_to_generate = data.quiz_types
    if data.question_type and data.question_type in ["mcq", "theory", "numerical"]:
        types_to_generate = [data.question_type]

    # Fetch recent past questions to avoid repetition
    past_questions = []
    if topic:
        recent_sets_res = await db.execute(
            select(QuizSet)
            .where(QuizSet.topic_id == topic.id)
            .order_by(QuizSet.created_at.desc())
            .limit(5)
        )
        recent_sets = recent_sets_res.scalars().all()
        for qs in recent_sets:
            if qs.questions:
                for q in qs.questions:
                    if "question" in q:
                        past_questions.append(q["question"])
                    if len(past_questions) >= 10:
                        break
            if len(past_questions) >= 10:
                break

    for qt in types_to_generate:
        quiz_data = await examiner_generate_quiz(
            topic_title=topic_title or "General Topic",
            subject=subject.name,
            level=subject.level,
            quiz_type=qt,
            explanation_content=topic.explanation_content if topic else "",
            weak_concepts=weak_concepts,
            subtopics=subtopics,
            past_questions=past_questions,
            count=data.count,
        )
        qs = QuizSet(
            topic_id=topic.id if topic else None,
            quiz_type=qt,
            questions=quiz_data.get("questions", []),
        )
        db.add(qs)
        await db.flush()
        
        created_sets.append({
            "id": str(qs.id),
            "quiz_type": qt,
            "questions": quiz_data.get("questions", []),
        })

    await db.commit()
    return {"quiz_sets": created_sets}


@router.post("/submit")
async def submit_answers(
    data: SubmitAnswersRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    qs_result = await db.execute(select(QuizSet).where(QuizSet.id == data.quiz_set_id))
    quiz_set = qs_result.scalar_one_or_none()
    if not quiz_set:
        raise HTTPException(status_code=404, detail="Quiz set not found")

    topic_result = await db.execute(select(Topic).where(Topic.id == quiz_set.topic_id))
    topic = topic_result.scalar_one_or_none()

    # Examiner analyzes answers
    analysis = await examiner_analyze_answers(
        quiz_type=quiz_set.quiz_type,
        questions=quiz_set.questions,
        user_answers=data.answers,
        topic_title=topic.title if topic else "Dynamic Topic",
    )

    attempt = QuizAttempt(
        quiz_set_id=quiz_set.id,
        user_id=current_user.id,
        answers=data.answers,
        score=analysis.get("score", 0),
        wrong_concepts=analysis.get("wrong_concepts", []),
        feedback=analysis.get("detailed_feedback", ""),
    )
    db.add(attempt)

    # Update progress weak/strong concepts
    subject_id_to_use = topic.subject_id if topic else None
    if not subject_id_to_use:
        # If no topic, try to find subject from quiz_set's context if available, otherwise just skip progress update
        pass # Handle dynamic quizzes that lack topic

    subject = None
    if subject_id_to_use:
        subject_result = await db.execute(select(Subject).where(Subject.id == subject_id_to_use))
        subject = subject_result.scalar_one_or_none()

    if subject:
        progress_result = await db.execute(
            select(Progress).where(Progress.subject_id == subject.id, Progress.user_id == current_user.id)
        )
        progress = progress_result.scalar_one_or_none()
        if progress:
            current_weak = set(progress.weak_concepts or [])
            current_strong = set(progress.strong_concepts or [])
            current_weak.update(analysis.get("wrong_concepts", []))
            current_strong.update(analysis.get("strong_concepts", []))
            # Remove from weak if now strong
            current_weak -= current_strong
            progress.weak_concepts = list(current_weak)
            progress.strong_concepts = list(current_strong)
            # Rolling average score
            progress.avg_quiz_score = (progress.avg_quiz_score + analysis.get("score", 0)) / 2

        # Parallel Note Synchronization (Scribe Agent)
        from db.models import Note
        note_result = await db.execute(
            select(Note).where(Note.subject_id == subject.id, Note.topic_id == None)
        )
        note = note_result.scalar_one_or_none()
        
        mastered_list = "\n".join([f"- {c}" for c in analysis.get("strong_concepts", [])]) or "None"
        revisit_list = "\n".join([f"- {c}" for c in analysis.get("wrong_concepts", [])]) or "None"
        
        summary_text = f"\n\n### Quiz Summary ({quiz_set.quiz_type.upper()})\n"
        summary_text += f"**Key Questions/Concepts Mastered**\n{mastered_list}\n\n"
        summary_text += f"**Concepts to Revisit**\n{revisit_list}\n\n"
        if quiz_set.quiz_type == "numerical":
            summary_text += f"**Important Formulas & Details**\n- Keep practicing derivations and step-by-step limits.\n\n"
            
        if not note:
            note = Note(
                subject_id=subject.id,
                content=summary_text,
                is_user_edited=False
            )
            db.add(note)
        else:
            note.content = (note.content or "") + summary_text

    await db.commit()
    return {"analysis": analysis}


@router.get("/sets/{topic_id}")
async def get_quiz_sets(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(QuizSet).where(QuizSet.topic_id == topic_id))
    sets = result.scalars().all()
    return [{"id": str(s.id), "quiz_type": s.quiz_type, "questions": s.questions} for s in sets]