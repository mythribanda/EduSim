import json
import logging
import re
import uuid
from typing import List, Dict, Any, Union, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.src.config.database import SessionLocal
from app.src.models.school import Question
from app.src.services.ai_router import call_ai
from app.src.models.question_models import (
    QuestionGenerateRequest,
    QuestionItem,
    QuestionGenerationResponse,
)

logger = logging.getLogger("EduSim.question_service")


class QuestionService:
    @staticmethod
    def _normalize_class_level(cl: Union[str, int]) -> str:
        """Normalize class level e.g. 10 -> '10', 'Class 10' -> '10'."""
        s = str(cl).strip()
        m = re.search(r"\d+", s)
        return m.group(0) if m else s

    @staticmethod
    def _parse_llm_json(raw_text: str) -> List[Dict[str, Any]]:
        """Extract and parse a JSON array of questions from LLM output."""
        if not raw_text:
            return []

        cleaned = raw_text.strip()
        # Remove markdown code blocks if present
        cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
        # Fix unescaped backslashes (e.g. from LaTeX equations)
        cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', cleaned)

        # Try direct JSON parsing
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for k in ("questions", "data", "results", "mcqs"):
                    if k in parsed and isinstance(parsed[k], list):
                        return parsed[k]
                return [parsed]
        except Exception:
            pass

        # Try searching for JSON array brackets [...]
        match = re.search(r"\[\s*\{.*\}\s*\]", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

        # Try searching for single JSON object {...}
        match_obj = re.search(r"\{\s*\"question\".*\}", cleaned, flags=re.DOTALL)
        if match_obj:
            try:
                parsed = json.loads(match_obj.group(0))
                if isinstance(parsed, dict):
                    if "questions" in parsed and isinstance(parsed["questions"], list):
                        return parsed["questions"]
                    return [parsed]
            except Exception:
                pass

        logger.warning("Failed to parse JSON questions from LLM response: %s", raw_text[:200])
        return []

    @staticmethod
    async def generate_cached_questions(
        topic: str,
        difficulty: str = "medium",
        class_level: Union[str, int] = "10",
        count: int = 3,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Question generator with caching logic:
        1. Check DB questions table: SELECT questions WHERE topic=? AND difficulty=? AND class_level=? LIMIT count
        2. If enough cached questions exist, return them (zero AI cost)
        3. If not enough, call Ollama to generate the shortfall only
        4. Prompt to Ollama: "Generate {n} physics MCQ questions about {topic} at {difficulty} level for Class {class_level}. Return ONLY a JSON array: [{question, options:[a,b,c,d], correct, explanation}]"
        5. Parse JSON response, validate structure, save to questions table, return
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            norm_topic = topic.strip()
            norm_diff = difficulty.strip().lower()
            norm_class = str(class_level).strip()

            # -------------------------------------------------------------
            # Step 1: Check database cache
            # -------------------------------------------------------------
            cached_rows = (
                db.query(Question)
                .filter(
                    func.lower(Question.topic) == norm_topic.lower(),
                    func.lower(Question.difficulty) == norm_diff,
                    func.lower(Question.class_level) == norm_class.lower(),
                )
                .limit(count)
                .all()
            )

            result: List[Dict[str, Any]] = []
            for q in cached_rows:
                result.append({
                    "id": str(q.id),
                    "question": q.question,
                    "options": q.options if isinstance(q.options, list) else list(q.options or []),
                    "correct": q.correct,
                    "explanation": q.explanation or "",
                    "topic": q.topic,
                    "difficulty": q.difficulty,
                    "class_level": q.class_level,
                })

            # -------------------------------------------------------------
            # Step 2: If enough cached exist, return them (Zero AI Cost)
            # -------------------------------------------------------------
            if len(result) >= count:
                logger.info(
                    "[Question Cache HIT] Served %d questions from DB cache for topic=%r difficulty=%r class=%r (Zero AI Cost)",
                    len(result[:count]), norm_topic, norm_diff, norm_class,
                )
                return result[:count]

            # -------------------------------------------------------------
            # Step 3: Calculate shortfall
            # -------------------------------------------------------------
            shortfall = count - len(result)
            logger.info(
                "[Question Cache MISS/PARTIAL] Cached=%d, Shortfall=%d for topic=%r difficulty=%r class=%r",
                len(result), shortfall, norm_topic, norm_diff, norm_class,
            )

            # -------------------------------------------------------------
            # Step 4: Prompt to Ollama for shortfall only
            # -------------------------------------------------------------
            prompt = (
                f"Generate {shortfall} physics MCQ questions about {norm_topic} "
                f"at {norm_diff} level for Class {norm_class}. "
                f"Return ONLY a JSON array: [{{\"question\": \"...\", \"options\": [\"a\", \"b\", \"c\", \"d\"], \"correct\": \"...\", \"explanation\": \"...\"}}]"
            )
            system_prompt = (
                "You are an expert physics educator creating curriculum-aligned multiple choice questions. "
                "Output ONLY a valid JSON array matching the exact structure requested. Do not include markdown code blocks or prose."
            )

            ai_resp = await call_ai(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                timeout=15.0,
                response_format={"type": "json_object"},
            )

            raw_text = ai_resp.get("text", "")
            parsed_questions = QuestionService._parse_llm_json(raw_text)

            # -------------------------------------------------------------
            # Step 5: Validate, save to questions table, and add to results
            # -------------------------------------------------------------
            new_records: List[Question] = []
            for item in parsed_questions:
                if not isinstance(item, dict):
                    continue

                q_text = str(item.get("question") or "").strip()
                if not q_text:
                    continue

                opts = item.get("options")
                if not isinstance(opts, list) or len(opts) < 2:
                    # Fallback options if missing or invalid
                    opts = [str(opts)] if opts else ["Option A", "Option B", "Option C", "Option D"]
                opts = [str(o).strip() for o in opts]

                correct_val = str(item.get("correct") or item.get("answer") or opts[0]).strip()
                expl_val = str(item.get("explanation") or "").strip()

                new_q = Question(
                    id=uuid.uuid4(),
                    topic=norm_topic,
                    difficulty=norm_diff,
                    class_level=norm_class,
                    question=q_text,
                    options=opts,
                    correct=correct_val,
                    explanation=expl_val,
                )
                db.add(new_q)
                new_records.append(new_q)

                result.append({
                    "id": str(new_q.id),
                    "question": new_q.question,
                    "options": new_q.options,
                    "correct": new_q.correct,
                    "explanation": new_q.explanation,
                    "topic": new_q.topic,
                    "difficulty": new_q.difficulty,
                    "class_level": new_q.class_level,
                })

            if new_records:
                try:
                    db.commit()
                    for r in new_records:
                        db.refresh(r)
                    logger.info(
                        "[Question Cache SAVED] Successfully cached %d newly generated questions in DB.",
                        len(new_records),
                    )
                except Exception as save_err:
                    db.rollback()
                    logger.warning("Could not persist generated questions to DB: %s", save_err)

            return result[:count]

        finally:
            if close_db:
                db.close()

    # Legacy method kept for backward-compatibility
    @staticmethod
    async def generate_questions(
        subject: str, 
        class_name: str, 
        chapter: str, 
        topic: str,
        formula: str = "",
        difficulty: str = "Medium",
        question_type: str = "mixed"
    ) -> QuestionGenerationResponse:
        cl = class_name or "10"
        t = topic or chapter or subject or "Physics"
        diff = difficulty or "medium"
        qs = await QuestionService.generate_cached_questions(topic=t, difficulty=diff, class_level=cl, count=4)
        return QuestionGenerationResponse(questions=qs)

    @staticmethod
    async def submit_question_answer(
        topic: str,
        selected_option: str,
        student_id: Optional[str] = None,
        question_id: Optional[str] = None,
        correct_option: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate student quiz answer, update student topic mastery, record session event,
        and return result feedback with next topic recommendation.
        """
        from app.src.services.mastery import update_mastery, get_recommended_difficulty
        from app.src.models.persistence import SessionEvent
        from app.src.api.students_router import TOPIC_PROGRESSIONS

        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            # Resolve student UUID or default
            raw_uid = student_id or "00000000-0000-0000-0000-000000000001"
            try:
                uid = uuid.UUID(str(raw_uid))
            except (ValueError, TypeError):
                uid = uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_uid))

            explanation = ""
            expected_correct = correct_option

            # 1. Lookup Question in DB if ID provided
            if question_id:
                try:
                    q_uuid = uuid.UUID(str(question_id))
                    q_rec = db.query(Question).filter(Question.id == q_uuid).first()
                    if q_rec:
                        expected_correct = q_rec.correct
                        explanation = q_rec.explanation or ""
                except Exception:
                    pass

            if not expected_correct:
                expected_correct = selected_option  # Fallback if unknown

            # 2. Evaluate correctness (case/whitespace insensitive)
            sel_clean = str(selected_option).strip().lower()
            exp_clean = str(expected_correct).strip().lower()
            is_correct = (sel_clean == exp_clean) or (sel_clean in exp_clean) or (exp_clean in sel_clean)

            # 3. Update Mastery Score
            mastery_rec = update_mastery(
                student_id=uid,
                topic_id=topic,
                is_correct=is_correct,
                db=db,
            )

            # 4. Get Recommended Difficulty
            rec_diff = get_recommended_difficulty(uid, topic, db)

            # 5. Determine Recommended Next Topic
            norm_topic_lower = topic.strip().lower()
            rec_next = TOPIC_PROGRESSIONS.get(norm_topic_lower, "Newton's Second Law")
            if norm_topic_lower == rec_next.lower():
                rec_next = "Newton's Third Law"

            # 6. Record Session Event
            try:
                event = SessionEvent(
                    id=uuid.uuid4(),
                    student_id=uid,
                    event_type="quiz_answered",
                    payload={
                        "topic": topic,
                        "question_id": str(question_id) if question_id else None,
                        "selected_option": selected_option,
                        "correct_option": expected_correct,
                        "is_correct": is_correct,
                        "new_mastery_score": mastery_rec.mastery_score,
                    },
                )
                db.add(event)
                db.commit()
            except Exception as ev_err:
                db.rollback()
                logger.warning("Could not persist session event for quiz submission: %s", ev_err)

            return {
                "is_correct": is_correct,
                "correct_answer": expected_correct,
                "explanation": explanation or ("Correct answer verified." if is_correct else f"The correct answer is: {expected_correct}"),
                "mastery_score": mastery_rec.mastery_score,
                "correct_streak": mastery_rec.correct_streak,
                "total_attempts": mastery_rec.total_attempts,
                "total_correct": mastery_rec.total_correct,
                "recommended_difficulty": rec_diff,
                "recommended_next": rec_next,
            }
        finally:
            if close_db:
                db.close()

