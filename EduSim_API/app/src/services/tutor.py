"""
app/src/services/tutor.py — Context-Aware Socratic AI Tutor Service for EduSim.

Builds personalized, context-aware prompts based on student profile (class level,
weak topics, topic mastery scores) and retrieved textbook context chunks.
Routes generation through the AI router and persists Q&A interactions to chat history.
"""

import uuid
import logging
import re
from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session

from app.src.config.database import SessionLocal
from app.src.models.user import User
from app.src.models.persistence import ChatHistory, Topic
from app.src.models.school import StudentTopicMastery
from app.src.services.mastery import get_weak_topics, update_mastery, TopicMasteryItem
from app.src.services.ai_router import call_ai

logger = logging.getLogger("EduSim.services.tutor")

SOCRATIC_INSTRUCTION = (
    "Do not give the full answer. Ask one guiding question first. "
    "If student is below 40% mastery, use simpler language."
)


def _normalize_uuid(val: Union[str, uuid.UUID]) -> uuid.UUID:
    """Safely convert a string or UUID into a uuid.UUID."""
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(val))


def _truncate_textbook_chunks(
    chunks: Optional[List[Union[str, Dict[str, Any]]]],
    max_chunks: int = 3,
    max_tokens: int = 800,
) -> List[str]:
    """
    Sanitize and limit textbook chunks to at most max_chunks (3) and
    total text length strictly < max_tokens (approx. 4 chars/token -> 3200 chars).
    """
    if not chunks:
        return []

    # Extract text content from string or dict chunks
    extracted: List[str] = []
    for c in chunks[:max_chunks]:
        if isinstance(c, dict):
            text = c.get("text") or c.get("content") or c.get("chunk") or ""
        else:
            text = str(c or "")
        text = text.strip()
        if text:
            extracted.append(text)

    # Approximate token cap (~4 chars per token -> 800 tokens ~ 3000 chars)
    max_char_limit = max_tokens * 4
    total_chars = 0
    selected_chunks: List[str] = []

    for chunk in extracted:
        if total_chars >= max_char_limit:
            break
        remaining_chars = max_char_limit - total_chars
        if len(chunk) <= remaining_chars:
            selected_chunks.append(chunk)
            total_chars += len(chunk)
        else:
            # Truncate at word boundary
            truncated = chunk[:remaining_chars].rsplit(" ", 1)[0] + "..."
            selected_chunks.append(truncated)
            break

    return selected_chunks


def identify_topic_from_text(
    text: str,
    db: Optional[Session] = None,
) -> Optional[str]:
    """
    Identifies a known physics topic from the query or text.
    Checks curriculum topics in DB first, followed by known physics domain concepts.
    """
    if not text:
        return None

    text_lower = text.lower()
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # TODO: [Curriculum V2 Migration] Migrate topic identification from legacy Topic to CurriculumNode(level='topic')
        # 1. Check Topic table names in database
        try:
            db_topics = db.query(Topic.name).all()
            for (t_name,) in db_topics:
                if t_name and len(t_name) > 3 and t_name.lower() in text_lower:
                    return t_name
        except Exception:
            pass

        # 2. Check StudentTopicMastery records
        try:
            mastery_topics = db.query(StudentTopicMastery.topic_id).distinct().all()
            for (m_topic,) in mastery_topics:
                if m_topic and len(m_topic) > 3 and m_topic.lower() in text_lower:
                    return m_topic
        except Exception:
            pass

        # 3. Common domain physics topics regex/keywords
        known_topics = [
            ("Newton's First Law", ["newton's first law", "first law of motion", "inertia"]),
            ("Newton's Second Law", ["newton's second law", "second law of motion", "f=ma", "f = ma", "force and acceleration"]),
            ("Newton's Third Law", ["newton's third law", "action and reaction", "third law of motion"]),
            ("Acceleration", ["acceleration", "accelerate", "deceleration", "a = (v-u)/t"]),
            ("Velocity & Speed", ["velocity", "speed", "displacement", "distance"]),
            ("Projectile Motion", ["projectile", "trajectory", "launch angle", "parabolic"]),
            ("Friction", ["friction", "static friction", "kinetic friction", "coefficient of friction"]),
            ("Gravitation", ["gravity", "gravitation", "gravitational force", "free fall"]),
            ("Work & Energy", ["work done", "kinetic energy", "potential energy", "conservation of energy"]),
            ("Refraction of Light", ["refraction", "refractive index", "snell's law", "prism"]),
            ("Reflection of Light", ["reflection", "mirror", "focal length", "concave", "convex"]),
            ("Ohm's Law & Circuits", ["ohm's law", "resistance", "resistor", "current", "voltage"]),
        ]

        for canonical_name, keywords in known_topics:
            for kw in keywords:
                if kw in text_lower:
                    return canonical_name

        return None
    finally:
        if close_db:
            db.close()


def build_tutor_prompt(
    student_id: Union[str, uuid.UUID],
    question: str,
    textbook_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
    db: Optional[Session] = None,
) -> Dict[str, str]:
    """
    Builds a fully context-aware Socratic system prompt and user query pair.

    1. Loads student profile (mastery scores, weak topics, class level).
    2. Builds a system prompt including:
       - Student's class level (e.g., Class 10)
       - Their weakest topic if related to the question
       - A Socratic instruction: "Do not give the full answer. Ask one guiding question first. If student is below 40% mastery, use simpler language."
       - Textbook chunks as context (max 3 chunks, total < 800 tokens)
    3. Returns {"system": system_prompt, "user": question}
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        uid = _normalize_uuid(student_id)

        # -------------------------------------------------------------
        # 1. Load Student Profile
        # -------------------------------------------------------------
        user = db.query(User).filter(User.id == uid).first()
        student_name = getattr(user, "name", "Student") if user else "Student"

        # Determine class level (default: 'Class 10')
        class_level = "Class 10"

        # Retrieve weak topics and topic masteries
        weak_topics: List[TopicMasteryItem] = get_weak_topics(uid, db=db)
        all_masteries = db.query(StudentTopicMastery).filter(StudentTopicMastery.student_id == uid).all()
        mastery_map = {m.topic_id: m.mastery_score for m in all_masteries}

        # -------------------------------------------------------------
        # 2. Check for Weakest Topic Related to the Question
        # -------------------------------------------------------------
        q_lower = question.lower()
        identified_topic = identify_topic_from_text(question, db=db)

        related_weak_topic: Optional[str] = None
        related_weak_score: Optional[float] = None
        is_student_below_40 = False

        # First priority: check if any of the student's weak topics match the question
        for wt in weak_topics:
            topic_str = str(wt).lower()
            if topic_str in q_lower or (identified_topic and str(wt).lower() in identified_topic.lower()):
                related_weak_topic = str(wt)
                related_weak_score = getattr(wt, "mastery_score", 0.0)
                is_student_below_40 = True
                break

        # Second priority: if question identified a topic that is in student's mastery records
        if not related_weak_topic and identified_topic:
            score = mastery_map.get(identified_topic)
            if score is not None:
                if score < 40.0:
                    related_weak_topic = identified_topic
                    related_weak_score = score
                    is_student_below_40 = True
            elif weak_topics:
                # If student has other weak topics, note the weakest overall
                sorted_weak = sorted(weak_topics, key=lambda t: getattr(t, "mastery_score", 0.0))
                related_weak_topic = str(sorted_weak[0])
                related_weak_score = getattr(sorted_weak[0], "mastery_score", 0.0)
                is_student_below_40 = True
        elif not related_weak_topic and weak_topics:
            # Note overall weak area
            sorted_weak = sorted(weak_topics, key=lambda t: getattr(t, "mastery_score", 0.0))
            related_weak_topic = str(sorted_weak[0])
            related_weak_score = getattr(sorted_weak[0], "mastery_score", 0.0)
            is_student_below_40 = True

        # -------------------------------------------------------------
        # 3. Format Textbook Chunks (max 3 chunks, total < 800 tokens)
        # -------------------------------------------------------------
        sanitized_chunks = _truncate_textbook_chunks(textbook_chunks, max_chunks=3, max_tokens=800)

        # -------------------------------------------------------------
        # 4. Build System Prompt
        # -------------------------------------------------------------
        system_lines = [
            f"You are an expert, encouraging Socratic AI Physics Tutor for {class_level} students.",
            "",
            "### Student Context:",
            f"- Student Name: {student_name}",
            f"- Education Level: {class_level}",
        ]

        if related_weak_topic:
            score_str = f" ({related_weak_score:.1f}% mastery)" if related_weak_score is not None else ""
            system_lines.append(f"- Weakest Topic Area: {related_weak_topic}{score_str}")

        system_lines.extend([
            "",
            "### Core Pedagogical Instructions:",
            f"- {SOCRATIC_INSTRUCTION}",
        ])

        if is_student_below_40:
            system_lines.append(
                "- Tone & Language Adjustment: The student currently has low mastery (< 40%) in this concept area. "
                "Use intuitive everyday analogies, simple everyday words, short sentences, and break the concept "
                "down into the most fundamental first step."
            )
        else:
            system_lines.append(
                "- Tone: Engaging, concise, encouraging, and academically supportive."
            )

        if sanitized_chunks:
            system_lines.extend([
                "",
                "### Textbook Context (Reference Material):",
                "Use the following excerpts from the curriculum textbook to guide your explanation accurately:",
            ])
            for i, chunk in enumerate(sanitized_chunks, 1):
                system_lines.append(f"--- [Exceprt {i}] ---")
                system_lines.append(chunk)

        system_lines.extend([
            "",
            "### Response Guidelines:",
            "1. Respond directly to the student's question.",
            "2. Never provide the complete solution or full derivation in your first reply.",
            "3. Ask exactly ONE clear, interactive guiding question to lead the student to discover the answer.",
        ])

        system_prompt = "\n".join(system_lines)
        return {"system": system_prompt, "user": question}

    finally:
        if close_db:
            db.close()


async def ask_tutor_service(
    student_id: Union[str, uuid.UUID],
    question: str,
    textbook_chunks: Optional[List[Union[str, Dict[str, Any]]]] = None,
    session_id: Optional[Union[str, uuid.UUID]] = None,
    db: Optional[Session] = None,
    model: str = "gemma3:4b",
) -> Dict[str, Any]:
    """
    Full end-to-end tutor service:
    1. Calls build_tutor_prompt()
    2. Calls call_ai() from the AI router
    3. Saves Q&A pair to chat_history
    4. Calls update_mastery() if question maps to an identifiable topic
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        uid = _normalize_uuid(student_id)
        sid = _normalize_uuid(session_id) if session_id else uuid.uuid4()

        # 1. Build prompt
        prompt_dict = build_tutor_prompt(uid, question, textbook_chunks=textbook_chunks, db=db)
        system_prompt = prompt_dict["system"]
        user_query = prompt_dict["user"]

        # 2. Call AI router
        ai_result = await call_ai(
            prompt=user_query,
            system_prompt=system_prompt,
            model=model,
            timeout=12.0,
        )
        ai_response_text = ai_result.get("text", "").strip()

        # 3. Identify topic
        identified_topic = identify_topic_from_text(question, db=db)

        # 4. Save Q&A pair to ChatHistory
        user_chat = ChatHistory(
            user_id=uid,
            session_id=sid,
            session_type="tutor",
            role="user",
            topic=identified_topic or "Physics Inquiry",
            content=question,
            metadata_json={"student_id": str(uid)},
        )
        assistant_chat = ChatHistory(
            user_id=uid,
            session_id=sid,
            session_type="tutor",
            role="assistant",
            topic=identified_topic or "Physics Inquiry",
            content=ai_response_text,
            metadata_json={
                "provider": ai_result.get("provider"),
                "tokens_used": ai_result.get("tokens_used"),
            },
        )
        db.add(user_chat)
        db.add(assistant_chat)

        # 5. Call update_mastery() if mapped to an identifiable topic
        mastery_record = None
        if identified_topic:
            try:
                mastery_record = update_mastery(
                    student_id=uid,
                    topic_id=identified_topic,
                    is_correct=False,
                    db=db,
                )
                logger.info(
                    "Mastery updated from tutor inquiry: student=%s topic=%r new_score=%.1f",
                    uid, identified_topic, mastery_record.mastery_score,
                )
            except Exception as ex:
                logger.warning("Could not update mastery for topic %r: %s", identified_topic, ex)

        db.commit()
        db.refresh(user_chat)
        db.refresh(assistant_chat)

        return {
            "success": True,
            "response": ai_response_text,
            "explanation": ai_response_text,
            "session_id": str(sid),
            "topic": identified_topic,
            "provider": ai_result.get("provider", "unknown"),
            "tokens_used": ai_result.get("tokens_used", 0),
            "system_prompt": system_prompt,
            "mastery_score": mastery_record.mastery_score if mastery_record else None,
        }

    except Exception as e:
        db.rollback()
        logger.error("Error in ask_tutor_service: %s", e)
        raise
    finally:
        if close_db:
            db.close()


__all__ = [
    "identify_topic_from_text",
    "build_tutor_prompt",
    "ask_tutor_service",
    "SOCRATIC_INSTRUCTION",
]
