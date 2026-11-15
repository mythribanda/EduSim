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
    def _generate_topic_fallback_questions(
        topic: str,
        subject: str = "Science",
        class_level: str = "10",
        difficulty: str = "medium",
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """High-fidelity curriculum-aligned questions when LLM is unavailable or times out."""
        t_low = (topic or "").lower()
        sub_low = (subject or "").lower()

        bank = []
        if any(w in t_low for w in ["newton", "inertia", "first law", "law of motion"]):
            bank = [
                {
                    "question": "According to Newton's First Law of Motion, what is required to change an object's state of rest or uniform motion?",
                    "options": [
                        "An unbalanced external net force",
                        "Continuous applied energy",
                        "Zero gravitational attraction",
                        "A constant mass increase"
                    ],
                    "correct": "An unbalanced external net force",
                    "explanation": "An object maintains its state of rest or uniform velocity unless acted upon by a non-zero net external force (\\sum \\vec{F} \\neq 0)."
                },
                {
                    "question": "Which physical quantity serves as a direct quantitative measure of an object's inertia?",
                    "options": ["Mass", "Velocity", "Volume", "Weight"],
                    "correct": "Mass",
                    "explanation": "Mass is the intrinsic scalar quantity that directly quantifies an object's resistance to acceleration (inertia)."
                },
                {
                    "question": "If the vector sum of all forces acting on a moving object is zero (\\sum \\vec{F} = 0), what happens to its motion?",
                    "options": [
                        "It continues moving with constant velocity in a straight line",
                        "It immediately comes to an abrupt halt",
                        "Its acceleration increases linearly",
                        "It begins to oscillate back and forth"
                    ],
                    "correct": "It continues moving with constant velocity in a straight line",
                    "explanation": "By Newton's First Law, when \\sum \\vec{F} = 0, \\vec{a} = 0, meaning velocity remains strictly constant in magnitude and direction."
                },
                {
                    "question": "A passenger jolts forward when a bus driver applies the brakes suddenly. This phenomenon is explained by:",
                    "options": [
                        "Inertia of motion",
                        "Gravitational acceleration",
                        "Centripetal reaction force",
                        "Newton's Third Law action-reaction"
                    ],
                    "correct": "Inertia of motion",
                    "explanation": "The passenger's upper body continues moving forward at the bus's original velocity due to inertia until an external restraining force acts."
                }
            ]
        elif any(w in t_low for w in ["second law", "force", "acceleration", "f = ma"]):
            bank = [
                {
                    "question": "Newton's Second Law mathematically states that the net force on an object is equal to the rate of change of its:",
                    "options": ["Linear momentum", "Kinetic energy", "Angular acceleration", "Total displacement"],
                    "correct": "Linear momentum",
                    "explanation": "\\vec{F}_{net} = \\frac{d\\vec{p}}{dt}. When mass is constant, this reduces to \\vec{F} = m\\vec{a}."
                },
                {
                    "question": "If an object of mass 4 kg experiences a net force of 20 N, what is its acceleration?",
                    "options": ["5 m/s²", "80 m/s²", "0.2 m/s²", "16 m/s²"],
                    "correct": "5 m/s²",
                    "explanation": "Using a = F / m: 20 N / 4 kg = 5 m/s²."
                },
                {
                    "question": "What is the SI unit of force in base SI units?",
                    "options": ["kg·m/s²", "kg·m²/s²", "kg·m/s", "kg/m²"],
                    "correct": "kg·m/s²",
                    "explanation": "One Newton (N) is defined as 1 kg·m/s²."
                }
            ]
        elif any(w in t_low for w in ["gravit", "kepler", "orbit", "planetary"]):
            bank = [
                {
                    "question": "According to Newton's Law of Universal Gravitation, the gravitational force between two bodies is inversely proportional to:",
                    "options": [
                        "The square of the distance between their centers",
                        "The distance between their centers",
                        "The product of their masses",
                        "The cube of their orbital period"
                    ],
                    "correct": "The square of the distance between their centers",
                    "explanation": "F = G(m_1 m_2)/r², exhibiting an inverse-square relationship with distance r."
                },
                {
                    "question": "What is the approximate acceleration due to gravity (g) near the Earth's surface?",
                    "options": ["9.8 m/s²", "6.67 m/s²", "3.14 m/s²", "1.62 m/s²"],
                    "correct": "9.8 m/s²",
                    "explanation": "The standard mean surface gravitational acceleration on Earth is 9.80665 m/s²."
                }
            ]
        elif any(w in t_low for w in ["energy", "work", "power", "kinetic"]):
            bank = [
                {
                    "question": "The work done by a constant force on an object is zero if the angle between force and displacement is:",
                    "options": ["90° (perpendicular)", "0° (parallel)", "180° (anti-parallel)", "45°"],
                    "correct": "90° (perpendicular)",
                    "explanation": "W = F · d · cos(θ). Since cos(90°) = 0, no work is done when force is orthogonal to motion."
                },
                {
                    "question": "If the speed of a vehicle is tripled, its kinetic energy increases by a factor of:",
                    "options": ["9", "3", "6", "27"],
                    "correct": "9",
                    "explanation": "Kinetic energy KE = 1/2 m v². Because KE scales with v², (3v)² = 9v²."
                }
            ]
        elif any(w in t_low for w in ["cell", "mitochondria", "dna", "plant", "organ"]):
            bank = [
                {
                    "question": "Which cellular organelle is primarily responsible for synthesizing adenosine triphosphate (ATP)?",
                    "options": ["Mitochondria", "Endoplasmic Reticulum", "Golgi Apparatus", "Lysosome"],
                    "correct": "Mitochondria",
                    "explanation": "Mitochondria perform cellular respiration to generate ATP, acting as the powerhouse of the cell."
                },
                {
                    "question": "What structural component is found in plant cells but absent in typical animal cells?",
                    "options": ["Cell wall of cellulose", "Mitochondria", "Cell membrane", "Ribosomes"],
                    "correct": "Cell wall of cellulose",
                    "explanation": "Plant cells possess a rigid outer cellulose cell wall that provides structural support and turgor pressure maintenance."
                }
            ]
        elif any(w in t_low for w in ["math", "rational", "fraction", "number", "polynomial", "algebra"]):
            bank = [
                {
                    "question": "A rational number is formally defined as any number that can be expressed in the form p/q, where:",
                    "options": [
                        "p and q are integers and q ≠ 0",
                        "p and q are natural numbers and q > p",
                        "p and q are real numbers and q = 0",
                        "p and q are irrational primes"
                    ],
                    "correct": "p and q are integers and q ≠ 0",
                    "explanation": "Rational numbers are ratios of two integers p and q, subject strictly to the non-zero denominator condition q ≠ 0."
                },
                {
                    "question": "What is the additive inverse of -7/12?",
                    "options": ["7/12", "-12/7", "12/7", "0"],
                    "correct": "7/12",
                    "explanation": "The additive inverse of a number x satisfies x + (-x) = 0. (-7/12) + (7/12) = 0."
                }
            ]
        else:
            bank = [
                {
                    "question": f"Which statement best characterizes the core principle of {topic}?",
                    "options": [
                        f"It describes verifiable, repeatable relationships in {subject}",
                        "It only applies in theoretical models without empirical observation",
                        "It contradicts conservation laws of physical systems",
                        "It varies randomly depending on geographical coordinate"
                    ],
                    "correct": f"It describes verifiable, repeatable relationships in {subject}",
                    "explanation": f"In {subject}, concepts such as {topic} are established through systematic observation, testing, and mathematical modeling."
                },
                {
                    "question": f"When analyzing {topic} in Class {class_level}, what is the standard method of investigation?",
                    "options": [
                        "Identifying key variables and testing relationships experimentally",
                        "Assuming all parameters remain infinitely large",
                        "Neglecting dimensional consistency across equations",
                        "Ignoring baseline boundary conditions"
                    ],
                    "correct": "Identifying key variables and testing relationships experimentally",
                    "explanation": "Scientific methodology relies on isolating independent variables, measuring dependent responses, and verifying unit consistency."
                },
                {
                    "question": f"How is knowledge of {topic} practically applied in technology and science?",
                    "options": [
                        "To predict system behaviors and optimize real-world solutions",
                        "Solely for decorative and linguistic descriptions",
                        "To bypass thermodynamic limits entirely",
                        "Without any mathematical or observational basis"
                    ],
                    "correct": "To predict system behaviors and optimize real-world solutions",
                    "explanation": "Understanding fundamental concepts allows scientists and engineers to model, simulate, and design practical applications."
                }
            ]

        return bank[:count]

    @staticmethod
    async def generate_cached_questions(
        topic: str,
        subject: str = "Science",
        difficulty: str = "medium",
        class_level: Union[str, int] = "10",
        count: int = 3,
        formula: str = "",
        exclude_questions: Optional[List[str]] = None,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Question generator with caching logic:
        1. Check DB questions table: SELECT questions WHERE topic=? AND difficulty=? LIMIT count
        2. If enough cached questions exist, return them (zero AI cost)
        3. If not enough, call Ollama/AI with fallback to generate the shortfall
        4. Validate, cache new questions to the database for future instant hits, and return.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            norm_topic = (topic or "Science Concepts").strip()
            norm_subject = (subject or "Science").strip()
            norm_diff = (difficulty or "medium").strip().lower()
            norm_class = str(class_level or "10").strip()

            # -------------------------------------------------------------
            # Step 1: Check database cache
            # -------------------------------------------------------------
            cached_rows = (
                db.query(Question)
                .filter(
                    func.lower(Question.topic).ilike(f"%{norm_topic.lower()[:20]}%"),
                    func.lower(Question.difficulty) == norm_diff,
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
            # Step 3: Calculate shortfall & attempt generation
            # -------------------------------------------------------------
            shortfall = count - len(result)
            logger.info(
                "[Question Cache MISS/PARTIAL] Cached=%d, Shortfall=%d for topic=%r subject=%r difficulty=%r class=%r",
                len(result), shortfall, norm_topic, norm_subject, norm_diff, norm_class,
            )

            prompt = (
                f"Generate {shortfall} multiple-choice quiz questions about {norm_topic} in {norm_subject} "
                f"at {norm_diff} level for Class {norm_class}. "
                f"Return ONLY a JSON array: [{{\"question\": \"...\", \"options\": [\"a\", \"b\", \"c\", \"d\"], \"correct\": \"...\", \"explanation\": \"...\"}}]"
            )
            system_prompt = (
                f"You are an expert educator in {norm_subject} creating curriculum-aligned multiple choice questions. "
                "Output ONLY a valid JSON array matching the exact structure requested. Do not include markdown code blocks or prose."
            )

            parsed_questions: List[Dict[str, Any]] = []
            try:
                ai_resp = await call_ai(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                    timeout=30.0,
                    response_format={"type": "json_object"},
                )
                raw_text = ai_resp.get("text", "")
                parsed_questions = QuestionService._parse_llm_json(raw_text)
            except Exception as e:
                logger.warning("LLM question generation failed: %s; falling back to curriculum question bank", e)

            # If LLM didn't return enough questions, pull from verified curriculum generator
            if len(parsed_questions) < shortfall:
                fallback_items = QuestionService._generate_topic_fallback_questions(
                    topic=norm_topic,
                    subject=norm_subject,
                    class_level=norm_class,
                    difficulty=norm_diff,
                    count=shortfall - len(parsed_questions),
                )
                parsed_questions.extend(fallback_items)

            # -------------------------------------------------------------
            # Step 4: Validate, save to questions table, and add to results
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
            raw_uid = student_id or "a0000000-0000-4000-a000-000000000001"
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

