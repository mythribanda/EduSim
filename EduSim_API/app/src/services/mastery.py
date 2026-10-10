"""
app/src/services/mastery.py — Pure Python Topic Mastery Tracking System for EduSim.

Calculates student proficiency, accuracy, and streaks using deterministic mathematics.
No LLM calls or AI services anywhere in this module.
"""

from __future__ import annotations

import uuid
import datetime
from typing import List, Optional, Union, Any
from sqlalchemy.orm import Session

from app.src.config.database import SessionLocal
from app.src.models.school import StudentTopicMastery

__all__ = [
    "StudentTopicMastery",
    "update_mastery",
    "get_weak_topics",
    "get_recommended_difficulty",
    "calculate_mastery_score",
    "TopicMasteryItem",
]


class TopicMasteryItem(str):
    """
    Representation of a weak topic identifier.
    Inherits from str so it acts directly as a string topic_id (e.g. `topic_id in weak_topics`
    and `topic == "topic_id"` evaluate to True), while also providing object attribute
    access (`item.topic_id`, `item.id`, `item.mastery_score`, `item.record`).
    """
    topic_id: str
    mastery_score: float
    record: Optional[StudentTopicMastery]

    def __new__(cls, topic_id: Union[str, uuid.UUID], mastery_score: float = 0.0, record: Optional[StudentTopicMastery] = None):
        str_id = str(topic_id)
        instance = super().__new__(cls, str_id)
        instance.topic_id = str_id
        instance.mastery_score = float(mastery_score)
        instance.record = record
        return instance

    @property
    def id(self) -> str:
        return self.topic_id

    def __eq__(self, other: Any) -> bool:
        if hasattr(other, "id"):
            return str(self.topic_id) == str(other.id)
        return str(self.topic_id) == str(other)

    def __repr__(self) -> str:
        return f"TopicMasteryItem(topic_id='{self.topic_id}', score={self.mastery_score})"


def calculate_mastery_score(correct_streak: int, total_correct: int, total_attempts: int) -> float:
    """
    Calculates student mastery score using the transparent 0–100 algorithm:
        accuracy = total_correct / total_attempts if total_attempts > 0 else 0.0
        accuracy_component = accuracy * 60.0
        streak_component = (min(correct_streak, 10) / 10.0) * 40.0
        mastery_score = accuracy_component + streak_component
        clamped to [0.0, 100.0]

    Parameters:
        correct_streak: Current streak of consecutive correct answers.
        total_correct: Total number of correct answers for this topic.
        total_attempts: Total number of attempts for this topic.

    Returns:
        Mastery score rounded to 2 decimal places in range [0.0, 100.0].
    """
    if total_attempts <= 0:
        return 0.0

    accuracy = max(0.0, min(1.0, total_correct / total_attempts))
    accuracy_component = accuracy * 60.0
    streak_component = (min(max(0, correct_streak), 10) / 10.0) * 40.0
    mastery_score = accuracy_component + streak_component

    # Clamp the final result to 0–100
    return round(min(100.0, max(0.0, float(mastery_score))), 2)


def _normalize_uuid(val: Union[str, uuid.UUID]) -> uuid.UUID:
    """Safely convert a string or UUID into a uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        # Generate deterministic UUID for arbitrary test strings (e.g. 'student-123')
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def update_mastery(
    student_id: Union[str, uuid.UUID],
    topic_id: Union[str, uuid.UUID],
    is_correct: bool,
    db: Optional[Session] = None,
) -> StudentTopicMastery:
    """
    Updates a StudentTopicMastery record for the given student and topic.
    Pure Python math driven — no LLM calls.

    Parameters:
        student_id: Student UUID or string identifier.
        topic_id: Topic UUID or string identifier.
        is_correct: Whether the current attempt was answered correctly.
        db: Optional existing SQLAlchemy session. If None, a managed session is used.

    Returns:
        The updated StudentTopicMastery instance.
    """
    norm_student_id = _normalize_uuid(student_id)
    norm_topic_id = str(topic_id)

    session = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        # Fetch or initialize record
        record = (
            session.query(StudentTopicMastery)
            .filter(
                StudentTopicMastery.student_id == norm_student_id,
                StudentTopicMastery.topic_id == norm_topic_id,
            )
            .first()
        )

        if not record:
            record = StudentTopicMastery(
                id=uuid.uuid4(),
                student_id=norm_student_id,
                topic_id=norm_topic_id,
                correct_streak=0,
                total_attempts=0,
                total_correct=0,
                mastery_score=0.0,
            )
            session.add(record)

        # Update attempt metrics
        record.total_attempts += 1
        if is_correct:
            record.correct_streak += 1
            record.total_correct += 1
        else:
            record.correct_streak = 0

        # Calculate mastery score: (correct_streak * 0.4) + (total_correct / total_attempts * 0.6), capped 0–100
        record.mastery_score = calculate_mastery_score(
            correct_streak=record.correct_streak,
            total_correct=record.total_correct,
            total_attempts=record.total_attempts,
        )
        record.last_attempted_at = datetime.datetime.now(datetime.timezone.utc)

        session.commit()
        session.refresh(record)
        return record
    finally:
        if should_close:
            session.close()


def get_weak_topics(
    student_id: Union[str, uuid.UUID],
    db: Optional[Session] = None,
) -> List[TopicMasteryItem]:
    """
    Returns topics where student's mastery_score < 40.

    Parameters:
        student_id: Student UUID or string identifier.
        db: Optional existing SQLAlchemy session.

    Returns:
        List of TopicMasteryItem instances (each behaves as a string topic_id,
        and provides .topic_id, .id, and .mastery_score properties).
    """
    norm_student_id = _normalize_uuid(student_id)
    session = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        records = (
            session.query(StudentTopicMastery)
            .filter(
                StudentTopicMastery.student_id == norm_student_id,
                StudentTopicMastery.mastery_score < 40.0,
            )
            .order_by(StudentTopicMastery.mastery_score.asc())
            .all()
        )
        return [TopicMasteryItem(r.topic_id, r.mastery_score, r) for r in records]
    finally:
        if should_close:
            session.close()


def get_recommended_difficulty(
    student_id: Union[str, uuid.UUID],
    topic_id: Union[str, uuid.UUID],
    db: Optional[Session] = None,
) -> str:
    """
    Returns recommended question/task difficulty based on mastery bands:
      - mastery_score < 40: "easy"
      - 40 <= mastery_score < 70: "medium"
      - mastery_score >= 70: "hard"

    If no mastery record exists yet for the topic, defaults to "easy".

    Parameters:
        student_id: Student UUID or string identifier.
        topic_id: Topic UUID or string identifier.
        db: Optional existing SQLAlchemy session.

    Returns:
        "easy", "medium", or "hard"
    """
    norm_student_id = _normalize_uuid(student_id)
    norm_topic_id = str(topic_id)
    session = db if db is not None else SessionLocal()
    should_close = db is None

    try:
        record = (
            session.query(StudentTopicMastery)
            .filter(
                StudentTopicMastery.student_id == norm_student_id,
                StudentTopicMastery.topic_id == norm_topic_id,
            )
            .first()
        )

        if not record:
            return "easy"

        score = record.mastery_score
        if score < 40.0:
            return "easy"
        elif score < 70.0:
            return "medium"
        else:
            return "hard"
    finally:
        if should_close:
            session.close()
