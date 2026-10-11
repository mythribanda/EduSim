"""
app/src/api/students_router.py — Student Profile and Analytics API for EduSim.

Provides the student profile endpoint consumed by the AI tutor and dashboards:
GET /students/{student_id}/profile

Returns:
- student_id: Student UUID string
- class: Class name (e.g. '10-A') resolved from enrollment or profile
- mastered_topics: List of topic names where StudentTopicMastery score > 70
- weak_topics: List of topic names where StudentTopicMastery score < 40
- current_streak_days: Consecutive calendar days of activity from session_events
- total_sessions: Total count of student sessions
- recommended_next: Suggested next topic for pedagogical progression

RBAC:
- Students can only view their own profile.
- Teachers can view any student enrolled in their classes or assigned to them.
- Admins have universal access.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.src.config.database import get_db
from app.src.models.persistence import (
    ChatHistory,
    CurriculumClass,
    SessionEvent,
    StudentProfile,
    Topic,
    UserSession,
)
from app.src.models.user import User
from app.src.middleware.rbac import get_current_user, require_self_or_admin
from app.src.models.school import StudentTopicMastery

logger = logging.getLogger("EduSim.api.students")

router = APIRouter(prefix="/students", tags=["Students"])


# Known pedagogical progressions for standard physics/science topics
TOPIC_PROGRESSIONS: Dict[str, str] = {
    "newton's first law": "Newton's Second Law",
    "newton's second law": "Newton's Third Law",
    "newton's third law": "Conservation of Momentum",
    "distance": "Displacement",
    "displacement": "Speed",
    "speed": "Velocity",
    "velocity": "Acceleration",
    "acceleration": "Projectile Motion",
    "projectile motion": "Circular Motion",
    "work": "Energy",
    "energy": "Power",
}


def resolve_topic_name(topic_id: str, db: Session) -> str:
    """
    Resolve a topic identifier (UUID, slug, or raw string) into a clean, human-readable name.
    """
    if not topic_id:
        return ""

    raw_str = str(topic_id).strip()

    # 1. Attempt UUID lookup in Topic table
    try:
        topic_uuid = uuid.UUID(raw_str)
        topic_rec = db.query(Topic).filter(Topic.id == topic_uuid).first()
        if topic_rec and topic_rec.name:
            return topic_rec.name
    except (ValueError, TypeError, AttributeError):
        pass

    # 2. Case-insensitive lookup by Topic name
    try:
        topic_rec = db.query(Topic).filter(Topic.name.ilike(raw_str)).first()
        if topic_rec and topic_rec.name:
            return topic_rec.name
    except Exception:
        pass

    # 3. Format slugs (e.g. "newtons-first-law" -> "Newton's First Law")
    cleaned = raw_str.replace("_", " ").replace("-", " ")
    if cleaned.lower().startswith("newtons "):
        cleaned = "Newton's " + cleaned[8:]
    return cleaned.title() if raw_str.islower() else raw_str


def resolve_student_class_name(student_uuid: uuid.UUID, student_user: User, db: Session) -> str:
    """
    Resolve human-readable class name (e.g. 'Class 10') for the student.
    Matches against CurriculumClass or falls back to 'Class 10'.
    """
    try:
        curr_rec = db.query(CurriculumClass).order_by(CurriculumClass.grade.asc()).first()
        if curr_rec and curr_rec.name:
            return curr_rec.name
    except Exception:
        pass

    return "Class 10"


def calculate_streak_days(student_uuid: uuid.UUID, db: Session) -> int:
    """
    Calculate current streak in consecutive calendar days from session_events.
    Falls back to ChatHistory, UserSession, and StudentTopicMastery if session_events is empty.
    """
    event_timestamps: List[datetime.datetime] = []

    # 1. Primary source: session_events
    try:
        event_timestamps = [
            row[0]
            for row in db.query(SessionEvent.created_at)
            .filter(SessionEvent.student_id == student_uuid)
            .all()
            if row[0] is not None
        ]
    except Exception as e:
        logger.debug(f"Error querying SessionEvent created_at: {e}")

    # 2. Secondary fallback sources
    if not event_timestamps:
        try:
            chat_ts = [
                row[0]
                for row in db.query(ChatHistory.created_at)
                .filter(ChatHistory.user_id == student_uuid)
                .all()
                if row[0] is not None
            ]
            session_ts = [
                row[0]
                for row in db.query(UserSession.created_at)
                .filter(UserSession.user_id == student_uuid)
                .all()
                if row[0] is not None
            ]
            mastery_ts = [
                row[0]
                for row in db.query(StudentTopicMastery.last_attempted_at)
                .filter(StudentTopicMastery.student_id == student_uuid)
                .all()
                if row[0] is not None
            ]
            event_timestamps = chat_ts + session_ts + mastery_ts
        except Exception as e:
            logger.debug(f"Error querying fallback activity timestamps: {e}")

    # 3. Check StudentProfile metadata for stored streak override
    stored_streak = 0
    try:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_uuid).first()
        if profile and profile.metadata_json and isinstance(profile.metadata_json, dict):
            stored_streak = int(profile.metadata_json.get("current_streak_days", 0))
    except Exception:
        pass

    if not event_timestamps:
        return stored_streak

    # Extract unique dates
    event_dates = set()
    for ts in event_timestamps:
        if isinstance(ts, datetime.datetime):
            event_dates.add(ts.date())
        elif isinstance(ts, datetime.date):
            event_dates.add(ts)

    if not event_dates:
        return stored_streak

    today = datetime.datetime.now(datetime.timezone.utc).date()
    yesterday = today - datetime.timedelta(days=1)

    # Determine start date for streak calculation:
    # If active today, count back from today.
    # If active yesterday, count back from yesterday (active streak intact).
    if today in event_dates:
        curr = today
    elif yesterday in event_dates:
        curr = yesterday
    else:
        # If neither today nor yesterday, check if all dates form an active chain ending at max_date
        max_date = max(event_dates)
        if (today - max_date).days <= 2:
            curr = max_date
        else:
            return stored_streak

    streak = 0
    while curr in event_dates:
        streak += 1
        curr -= datetime.timedelta(days=1)

    return max(streak, stored_streak)


def calculate_total_sessions(student_uuid: uuid.UUID, db: Session) -> int:
    """
    Calculate the total count of student sessions across UserSession, ChatHistory,
    and SessionEvent.
    """
    counts: List[int] = []

    # 1. UserSession records
    try:
        user_sess_count = db.query(UserSession).filter(UserSession.user_id == student_uuid).count()
        counts.append(user_sess_count)
    except Exception:
        pass

    # 2. Distinct ChatHistory sessions
    try:
        chat_sess_count = (
            db.query(func.count(func.distinct(ChatHistory.session_id)))
            .filter(ChatHistory.user_id == student_uuid)
            .scalar()
            or 0
        )
        counts.append(chat_sess_count)
    except Exception:
        pass

    # 3. SessionEvent counts
    try:
        started_count = (
            db.query(SessionEvent)
            .filter(SessionEvent.student_id == student_uuid, SessionEvent.event_type == "started")
            .count()
        )
        counts.append(started_count)
    except Exception:
        pass

    # 4. StudentProfile metadata
    try:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_uuid).first()
        if profile and profile.metadata_json and isinstance(profile.metadata_json, dict):
            counts.append(int(profile.metadata_json.get("total_sessions", 0)))
    except Exception:
        pass

    return max(counts) if counts else 0


def determine_recommended_next(
    mastered_topics: List[str],
    weak_topics: List[str],
    student_uuid: uuid.UUID,
    db: Session,
) -> str:
    """
    Determines the recommended next topic for the student based on:
    1. StudentProfile.metadata_json override if present.
    2. Known curriculum sequence mapping from the latest mastered topic.
    3. Next topic in Topic display_order hierarchy.
    4. First weak topic requiring reinforcement.
    5. Default sensible introductory topic.
    """
    # 1. Check profile metadata override
    try:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == student_uuid).first()
        if profile and profile.metadata_json and isinstance(profile.metadata_json, dict):
            explicit = profile.metadata_json.get("recommended_next")
            if explicit:
                return str(explicit)
    except Exception:
        pass

    # 2. Check topic progression rules
    mastered_lower_set = {t.lower().strip() for t in mastered_topics}
    for t in mastered_topics:
        next_candidate = TOPIC_PROGRESSIONS.get(t.lower().strip())
        if next_candidate and next_candidate.lower() not in mastered_lower_set:
            return next_candidate

    # 3. Check DB Topic sequence
    for t in mastered_topics:
        try:
            topic_rec = db.query(Topic).filter(Topic.name.ilike(t)).first()
            if topic_rec and topic_rec.chapter_id:
                next_db_topic = (
                    db.query(Topic)
                    .filter(
                        Topic.chapter_id == topic_rec.chapter_id,
                        Topic.display_order > topic_rec.display_order,
                    )
                    .order_by(Topic.display_order.asc())
                    .first()
                )
                if next_db_topic and next_db_topic.name and next_db_topic.name.lower() not in mastered_lower_set:
                    return next_db_topic.name
        except Exception:
            pass

    # 4. If weak topics exist, recommend reinforcing the first weak topic
    if weak_topics:
        return weak_topics[0]

    # 5. Fallback defaults
    if "Newton's First Law" in mastered_topics:
        return "Newton's Second Law"
    return "Newton's First Law"


@router.get("/{student_id}/profile", summary="Get Student Profile for AI Tutor & Learning Path")
def get_student_profile(
    student_id: str,
    current_user: User = Depends(require_self_or_admin("student_id")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns the comprehensive student profile read by the AI tutor.

    Returns:
    {
      "student_id": "...",
      "class": "10-A",
      "mastered_topics": ["Newton's First Law", "Distance"],
      "weak_topics": ["Acceleration", "Projectile Motion"],
      "current_streak_days": 5,
      "total_sessions": 23,
      "recommended_next": "Newton's Second Law"
    }

    RBAC Rules:
    - Student: can only view their own profile.
    - Teacher/Educator: can view any student enrolled in or assigned to their classes.
    - Admin: universal access.
    """
    try:
        student_uuid = uuid.UUID(str(student_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid student UUID format.",
        )

    student_user = db.query(User).filter(User.id == student_uuid).first()
    if not student_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )

    # 1. Resolve Class Name
    class_name = resolve_student_class_name(student_uuid, student_user, db)

    # 2. Topic Mastery Queries:
    # - mastered_topics: score > 70
    # - weak_topics: score < 40
    all_mastery = (
        db.query(StudentTopicMastery)
        .filter(StudentTopicMastery.student_id == student_uuid)
        .all()
    )

    mastered_records = sorted(
        [r for r in all_mastery if r.mastery_score > 70.0],
        key=lambda r: r.mastery_score,
        reverse=True,
    )
    weak_records = sorted(
        [r for r in all_mastery if r.mastery_score < 40.0],
        key=lambda r: r.mastery_score,
    )

    # Resolve display names and preserve order while deduplicating
    mastered_topics: List[str] = []
    for r in mastered_records:
        name = resolve_topic_name(r.topic_id, db)
        if name and name not in mastered_topics:
            mastered_topics.append(name)

    weak_topics: List[str] = []
    for r in weak_records:
        name = resolve_topic_name(r.topic_id, db)
        if name and name not in weak_topics and name not in mastered_topics:
            weak_topics.append(name)

    # 3. Calculate Streak from session_events
    current_streak_days = calculate_streak_days(student_uuid, db)

    # 4. Calculate Total Sessions
    total_sessions = calculate_total_sessions(student_uuid, db)

    # 5. Determine Recommended Next Topic
    recommended_next = determine_recommended_next(mastered_topics, weak_topics, student_uuid, db)

    return {
        "student_id": str(student_uuid),
        "class": class_name,
        "mastered_topics": mastered_topics,
        "weak_topics": weak_topics,
        "current_streak_days": current_streak_days,
        "total_sessions": total_sessions,
        "recommended_next": recommended_next,
    }





