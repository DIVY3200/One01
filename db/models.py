from sqlalchemy import Column, String, Text, Integer, Float, Boolean, ForeignKey, JSON, TIMESTAMP, Uuid as UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from db.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    onboarding_completed = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)
    subjects = relationship("Subject", back_populates="user")


class UserPreferences(Base):
    __tablename__ = "user_preferences"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    nickname = Column(String(100), default="buddy")
    ai_teacher_name = Column(String(100), default="Lead")
    ai_gender = Column(String(20), default="neutral")
    teaching_style = Column(String(50), default="mentor")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="preferences")


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    purpose = Column(String(50), default="academic")
    level = Column(String(50), default="beginner")
    outline = Column(JSON)
    current_topic_index = Column(Integer, default=0)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="subjects")
    topics = relationship("Topic", back_populates="subject", order_by="Topic.index_order", cascade="all, delete-orphan", passive_deletes=True)
    notes = relationship("Note", back_populates="subject", cascade="all, delete-orphan", passive_deletes=True)
    progress = relationship("Progress", back_populates="subject", uselist=False, cascade="all, delete-orphan", passive_deletes=True)
    feedback = relationship("Feedback", back_populates="subject", cascade="all, delete-orphan", passive_deletes=True)
    weak_points = relationship("WeakPoint", back_populates="subject", cascade="all, delete-orphan", passive_deletes=True)


class Topic(Base):
    __tablename__ = "topics"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(UUID(as_uuid=False), ForeignKey("subjects.id", ondelete="CASCADE"))
    title = Column(String(500), nullable=False)
    index_order = Column(Integer, nullable=False)
    status = Column(String(30), default="pending")
    current_subtopic_index = Column(Integer, default=0)
    explanation_content = Column(Text)
    completed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    subject = relationship("Subject", back_populates="topics")
    messages = relationship("Message", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True)
    quiz_sets = relationship("QuizSet", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True)
    note = relationship("Note", back_populates="topic", uselist=False, cascade="all, delete-orphan", passive_deletes=True)


class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id = Column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    agent_type = Column(String(50))
    metadata_ = Column("metadata", JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    topic = relationship("Topic", back_populates="messages")


class QuizSet(Base):
    __tablename__ = "quiz_sets"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id = Column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="CASCADE"))
    quiz_type = Column(String(30), nullable=False)
    questions = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    topic = relationship("Topic", back_populates="quiz_sets")
    attempts = relationship("QuizAttempt", back_populates="quiz_set", cascade="all, delete-orphan", passive_deletes=True)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    quiz_set_id = Column(UUID(as_uuid=False), ForeignKey("quiz_sets.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    answers = Column(JSON, nullable=False)
    score = Column(Float)
    wrong_concepts = Column(JSON)
    feedback = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    quiz_set = relationship("QuizSet", back_populates="attempts")


class Note(Base):
    __tablename__ = "notes"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(UUID(as_uuid=False), ForeignKey("subjects.id", ondelete="CASCADE"))
    topic_id = Column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="CASCADE"))
    content = Column(Text, default="")
    is_user_edited = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    subject = relationship("Subject", back_populates="notes")
    topic = relationship("Topic", back_populates="note")


class Progress(Base):
    __tablename__ = "progress"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(UUID(as_uuid=False), ForeignKey("subjects.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    total_topics = Column(Integer, default=0)
    completed_topics = Column(Integer, default=0)
    avg_quiz_score = Column(Float, default=0)
    weak_concepts = Column(JSON, default=list)
    strong_concepts = Column(JSON, default=list)
    time_spent_minutes = Column(Integer, default=0)
    last_activity = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now())
    subject = relationship("Subject", back_populates="progress")


class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(UUID(as_uuid=False), ForeignKey("subjects.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    content = Column(Text, nullable=False)
    categories = Column(JSON)
    ai_response = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    subject = relationship("Subject", back_populates="feedback")


class WeakPoint(Base):
    __tablename__ = "weak_points"
    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(UUID(as_uuid=False), ForeignKey("subjects.id", ondelete="CASCADE"))
    topic_id = Column(UUID(as_uuid=False), ForeignKey("topics.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    subject = relationship("Subject", back_populates="weak_points")