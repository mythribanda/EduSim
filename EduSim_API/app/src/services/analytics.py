"""
app/src/services/analytics.py — Pure Python / SQLAlchemy Class Analytics Service for EduSim.

Computes comprehensive class-level analytics, topic breakdowns, engagement metrics,
most asked topics, assignment submission counts, and at-risk student rosters using deterministic database queries.
Zero LLM or AI calls — 100% pure SQL aggregations and Python math.
"""

from __future__ import annotations

import csv
import datetime
import io
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Union
from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.src.config.database import SessionLocal
from app.src.models.persistence import SessionEvent, Topic, ChatHistory
from app.src.models.user import User
from app.src.models.school import Class, StudentEnrollment, StudentTopicMastery, Assignment, Submission

logger = logging.getLogger("EduSim.services.analytics")


def _normalize_uuid(val: Union[str, uuid.UUID]) -> uuid.UUID:
    """Safely convert a string or UUID into a uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def format_last_active(dt: Optional[datetime.datetime]) -> str:
    """Format a datetime into a human-readable relative time string (e.g. '3 days ago')."""
    if not dt:
        return "never"
    now = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago" if minutes == 1 else f"{minutes} mins ago"
    hours = minutes // 60
    if hours < 24:
        return "today" if hours < 12 else f"{hours} hours ago"
    days = diff.days
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    weeks = days // 7
    if weeks == 1:
        return "1 week ago"
    if weeks < 4:
        return f"{weeks} weeks ago"
    months = days // 30
    if months == 1:
        return "1 month ago"
    if months < 12:
        return f"{months} months ago"
    years = days // 365
    return f"{years} year ago" if years == 1 else f"{years} years ago"


def resolve_topic_name(topic_id: str, db: Session) -> str:
    """Resolve a topic identifier into a clean, human-readable name."""
    if not topic_id:
        return "Unknown Topic"

    raw_str = str(topic_id).strip()

    # 1. UUID lookup in Topic table
    try:
        topic_uuid = uuid.UUID(raw_str)
        topic_rec = db.query(Topic).filter(Topic.id == topic_uuid).first()
        if topic_rec and topic_rec.name:
            return topic_rec.name
    except Exception:
        pass

    # 2. Case-insensitive lookup by Topic.name
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


def get_class_analytics(
    class_id: Union[str, uuid.UUID],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Computes class analytics:
    {
      "class_average_mastery": float,
      "topic_breakdown": [
        {"topic": "Newton's First Law", "avg_mastery": 78.0, "weak_students": 3},
        ...
      ],
      "most_asked_topics": ["acceleration", "force", "velocity"],
      "engagement": {"active_this_week": int, "total_students": int},
      "assignments_submitted": int,
      "at_risk_students": [{"id": str, "student_id": str, "name": str, "mastery": float, "last_active": str}]
    }
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        cid = _normalize_uuid(class_id)

        # Verify class exists
        cls = db.query(Class).filter(Class.id == cid).first()
        if not cls:
            raise ValueError(f"Class with ID '{class_id}' not found.")

        # 1. Enrolled student IDs
        enrollments = (
            db.query(StudentEnrollment.student_id)
            .filter(
                StudentEnrollment.class_id == cid,
                StudentEnrollment.status == "active",
            )
            .all()
        )
        student_ids = [row[0] for row in enrollments]
        total_students = len(student_ids)

        # Query total assignment submissions for this class
        assignments_submitted = (
            db.query(func.count(Submission.id))
            .join(Assignment, Assignment.id == Submission.assignment_id)
            .filter(Assignment.class_id == cid)
            .scalar()
            or 0
        )

        if total_students == 0:
            return {
                "class_id": str(cid),
                "class_name": cls.name,
                "grade_level": cls.grade_level,
                "class_average_mastery": 0.0,
                "topic_breakdown": [],
                "most_asked_topics": [],
                "engagement": {"active_this_week": 0, "total_students": 0},
                "assignments_submitted": int(assignments_submitted),
                "at_risk_students": [],
            }

        # -------------------------------------------------------------
        # 2. Class Average Mastery (SQL Aggregation)
        # -------------------------------------------------------------
        overall_avg = (
            db.query(func.avg(StudentTopicMastery.mastery_score))
            .filter(StudentTopicMastery.student_id.in_(student_ids))
            .scalar()
        )
        class_average_mastery = round(float(overall_avg or 0.0), 1)

        # -------------------------------------------------------------
        # 3. Topic Breakdown (SQL Aggregations)
        # -------------------------------------------------------------
        topic_stats = (
            db.query(
                StudentTopicMastery.topic_id,
                func.avg(StudentTopicMastery.mastery_score).label("avg_score"),
                func.count(StudentTopicMastery.student_id).label("student_count"),
            )
            .filter(StudentTopicMastery.student_id.in_(student_ids))
            .group_by(StudentTopicMastery.topic_id)
            .order_by(func.avg(StudentTopicMastery.mastery_score).asc())
            .all()
        )

        topic_breakdown: List[Dict[str, Any]] = []
        for t_id, avg_score, s_count in topic_stats:
            resolved = resolve_topic_name(t_id, db)
            
            # Count weak students (score < 40) for this specific topic
            weak_count = (
                db.query(func.count(StudentTopicMastery.id))
                .filter(
                    StudentTopicMastery.student_id.in_(student_ids),
                    StudentTopicMastery.topic_id == t_id,
                    StudentTopicMastery.mastery_score < 40.0,
                )
                .scalar()
                or 0
            )

            topic_breakdown.append({
                "topic": resolved,
                "avg_mastery": round(float(avg_score or 0.0), 1),
                "weak_students": int(weak_count),
            })

        # -------------------------------------------------------------
        # 4. Most Asked Topics (from session_events & ChatHistory)
        # -------------------------------------------------------------
        topic_counter: Counter[str] = Counter()

        # Extract topics from session_events
        events = (
            db.query(SessionEvent.payload)
            .filter(SessionEvent.student_id.in_(student_ids))
            .order_by(SessionEvent.created_at.desc())
            .limit(300)
            .all()
        )
        for (payload,) in events:
            if isinstance(payload, dict):
                for key in ("topic", "topic_name", "chapter", "subject", "question_topic"):
                    val = payload.get(key)
                    if val and isinstance(val, str) and len(val.strip()) > 1:
                        topic_counter[val.strip().lower()] += 1
                        break

        # Also inspect recent ChatHistory questions
        chats = (
            db.query(ChatHistory.topic)
            .filter(ChatHistory.user_id.in_(student_ids))
            .order_by(ChatHistory.created_at.desc())
            .limit(100)
            .all()
        )
        for (t_name,) in chats:
            if t_name and isinstance(t_name, str) and len(t_name.strip()) > 1:
                topic_counter[t_name.strip().lower()] += 1

        most_asked_topics = [t for t, _ in topic_counter.most_common(5)]

        # -------------------------------------------------------------
        # 5. Engagement (Active this week vs total students)
        # -------------------------------------------------------------
        seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)

        active_event_students = {
            row[0]
            for row in db.query(SessionEvent.student_id)
            .filter(
                SessionEvent.student_id.in_(student_ids),
                SessionEvent.created_at >= seven_days_ago,
            )
            .all()
        }

        active_user_table_students = {
            row[0]
            for row in db.query(User.id)
            .filter(
                User.id.in_(student_ids),
                User.last_active_at >= seven_days_ago,
            )
            .all()
        }

        active_this_week = len(active_event_students | active_user_table_students)

        # -------------------------------------------------------------
        # 6. At-Risk Students (Mastery < 40 or Critical Weaknesses)
        # -------------------------------------------------------------
        users = db.query(User).filter(User.id.in_(student_ids)).all()
        user_map = {u.id: u for u in users}

        student_mastery_stats = (
            db.query(
                StudentTopicMastery.student_id,
                func.avg(StudentTopicMastery.mastery_score).label("avg_mastery"),
                func.min(StudentTopicMastery.mastery_score).label("min_mastery"),
            )
            .filter(StudentTopicMastery.student_id.in_(student_ids))
            .group_by(StudentTopicMastery.student_id)
            .all()
        )
        student_mastery_map = {row[0]: (float(row[1] or 0.0), float(row[2] or 0.0)) for row in student_mastery_stats}

        latest_event_map: Dict[uuid.UUID, datetime.datetime] = {}
        latest_events = (
            db.query(
                SessionEvent.student_id,
                func.max(SessionEvent.created_at).label("latest_event"),
            )
            .filter(SessionEvent.student_id.in_(student_ids))
            .group_by(SessionEvent.student_id)
            .all()
        )
        for sid, max_dt in latest_events:
            if max_dt:
                latest_event_map[sid] = max_dt

        at_risk_students: List[Dict[str, Any]] = []
        for sid in student_ids:
            u = user_map.get(sid)
            s_name = getattr(u, "name", None) or getattr(u, "email", "Student")
            s_email = getattr(u, "email", "") or ""

            stats_tuple = student_mastery_map.get(sid, (0.0, 0.0))
            avg_m, min_m = stats_tuple

            # Check if at risk: average mastery < 40 or min mastery < 40
            if avg_m < 40.0 or min_m < 40.0 or len(student_mastery_map) == 0:
                last_dt = latest_event_map.get(sid) or getattr(u, "last_active_at", None)
                last_active_str = format_last_active(last_dt)

                at_risk_students.append({
                    "id": str(sid),
                    "student_id": str(sid),
                    "name": s_name,
                    "email": s_email,
                    "mastery": round(avg_m, 1),
                    "last_active": last_active_str,
                })

        at_risk_students.sort(key=lambda s: s["mastery"])

        return {
            "class_id": str(cid),
            "class_name": cls.name,
            "grade_level": cls.grade_level,
            "class_average_mastery": class_average_mastery,
            "topic_breakdown": topic_breakdown,
            "most_asked_topics": most_asked_topics,
            "engagement": {
                "active_this_week": active_this_week,
                "total_students": total_students,
            },
            "assignments_submitted": int(assignments_submitted),
            "at_risk_students": at_risk_students,
        }

    finally:
        if close_db:
            db.close()


def export_class_analytics_csv(
    class_id: Union[str, uuid.UUID],
    db: Optional[Session] = None,
) -> str:
    """
    Exports a comprehensive CSV analytics report for a class.
    """
    analytics = get_class_analytics(class_id, db=db)
    
    output = io.StringIO()
    writer = csv.writer(output)

    # Header / Overview
    writer.writerow(["EDUSIM CLASS ANALYTICS REPORT"])
    writer.writerow(["Generated At (UTC)", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["Class Name", analytics.get("class_name", "N/A")])
    writer.writerow(["Grade Level", analytics.get("grade_level", "N/A")])
    writer.writerow(["Class Average Mastery (%)", analytics["class_average_mastery"]])
    writer.writerow(["Total Enrolled Students", analytics["engagement"]["total_students"]])
    writer.writerow(["Active This Week", analytics["engagement"]["active_this_week"]])
    writer.writerow(["Assignments Submitted", analytics.get("assignments_submitted", 0)])
    writer.writerow([])

    # Topic Breakdown
    writer.writerow(["--- TOPIC BREAKDOWN ---"])
    writer.writerow(["Topic Name", "Average Mastery (%)", "Weak Students (<40%)", "Status"])
    for topic in analytics.get("topic_breakdown", []):
        score = topic["avg_mastery"]
        status = "Mastered" if score >= 70 else ("Moderate" if score >= 40 else "Critical Weakness")
        writer.writerow([topic["topic"], score, topic["weak_students"], status])
    writer.writerow([])

    # At-Risk Students
    writer.writerow(["--- AT-RISK STUDENTS (<40% MASTERY) ---"])
    writer.writerow(["Student ID", "Student Name", "Email", "Mastery Score (%)", "Last Active"])
    for student in analytics.get("at_risk_students", []):
        writer.writerow([
            student.get("id", student.get("student_id", "")),
            student["name"],
            student.get("email", ""),
            student["mastery"],
            student["last_active"],
        ])
    writer.writerow([])

    # Most Asked Topics
    writer.writerow(["--- MOST ASKED TOPICS (STUDENT QUERIES) ---"])
    writer.writerow(["Rank", "Topic Name"])
    for rank, topic in enumerate(analytics.get("most_asked_topics", []), start=1):
        writer.writerow([rank, topic])

    return output.getvalue()


__all__ = ["get_class_analytics", "export_class_analytics_csv", "format_last_active", "resolve_topic_name"]
