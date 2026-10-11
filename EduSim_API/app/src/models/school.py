from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UUID,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.src.config.database import Base


class StudentTopicMastery(Base):
    """
    Tracks a student's mastery level in a given topic using streak and accuracy metrics.
    Pure Python math driven — no LLM calls.
    """
    __tablename__ = "student_topic_mastery"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(255), nullable=False, index=True)
    mastery_score = Column(Float, default=0.0, nullable=False, index=True)
    correct_streak = Column(Integer, default=0, nullable=False)
    total_attempts = Column(Integer, default=0, nullable=False)
    total_correct = Column(Integer, default=0, nullable=False)
    last_attempted_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to user
    student = relationship("User", foreign_keys=[student_id], lazy="joined")

    __table_args__ = (
        UniqueConstraint("student_id", "topic_id", name="uq_student_topic_mastery"),
        Index("ix_mastery_student_score", "student_id", "mastery_score"),
    )


class Question(Base):
    """
    Cached physics practice and quiz questions.
    Caches generated MCQs by (topic, difficulty, class_level) to prevent redundant AI calls.
    """
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String(255), nullable=False, index=True)
    difficulty = Column(String(50), nullable=False, index=True)
    class_level = Column(String(50), nullable=False, index=True)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)
    correct = Column(String(255), nullable=False)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_questions_lookup", "topic", "difficulty", "class_level"),
    )


__all__ = [
    "StudentTopicMastery",
    "Question",
]
