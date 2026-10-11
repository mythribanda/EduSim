"""
EduSim_API/tests/test_learning_loop.py
End-to-end unit and integration tests for Phase 1 Physics Learning Loop.
"""

import sys
import os
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.src.config.database import Base
from app.src.models.persistence import Topic, Chapter, Subject, CurriculumClass, SessionEvent, StudentProfile
from app.src.models.user import User
from app.src.models.school import StudentTopicMastery, Question
from app.src.services.mastery import calculate_mastery_score
from app.src.modules.simulation_synthesis.templates import get_precompiled_template, PRECOMPILED_PHYSICS_TEMPLATES
from app.src.services.question_service import QuestionService
from app.src.api.students_router import determine_recommended_next, resolve_topic_name


@pytest.fixture(scope="module")
def db_session():
    """Create an in-memory SQLite database for testing the learning loop."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_mastery_score_scaling():
    """Verify mastery score scales properly to 0-100% instead of old 4.6% max."""
    # 0 attempts
    assert calculate_mastery_score(correct_streak=0, total_correct=0, total_attempts=0) == 0.0

    # 10/10 correct with 10 streak -> should equal 100.0 (60 + 40)
    score_perfect = calculate_mastery_score(correct_streak=10, total_correct=10, total_attempts=10)
    assert score_perfect == 100.0

    # 5/10 correct (50% accuracy = 30) with 3 streak (12) -> should equal 42.0
    score_mid = calculate_mastery_score(correct_streak=3, total_correct=5, total_attempts=10)
    assert score_mid == 42.0

    # 8/10 correct (80% accuracy = 48) with 5 streak (20) -> should equal 68.0
    score_good = calculate_mastery_score(correct_streak=5, total_correct=8, total_attempts=10)
    assert score_good == 68.0


def test_simulation_synthesis_precompiled_templates():
    """Verify precompiled physics templates return valid DSL instantaneously."""
    tpl_newton = get_precompiled_template("newton's second law")
    assert tpl_newton is not None
    assert "dsl" in tpl_newton
    assert "objects" in tpl_newton["dsl"]
    assert "environment" in tpl_newton["dsl"]

    tpl_projectile = get_precompiled_template("projectile motion")
    assert tpl_projectile is not None
    assert "dsl" in tpl_projectile
    assert "objects" in tpl_projectile["dsl"]

    tpl_pendulum = get_precompiled_template("simple pendulum")
    assert tpl_pendulum is not None
    assert "dsl" in tpl_pendulum
    assert "constraints" in tpl_pendulum["dsl"]


def test_student_topic_progression(db_session):
    """Verify pedagogical progression recommends logical next topic."""
    rec1 = determine_recommended_next(["Newton's First Law"], [], uuid.uuid4(), db_session)
    assert rec1 == "Newton's Second Law"

    rec2 = determine_recommended_next(["Newton's Second Law"], [], uuid.uuid4(), db_session)
    assert rec2 == "Newton's Third Law"

    rec_weak = determine_recommended_next([], ["Projectile Motion"], uuid.uuid4(), db_session)
    assert rec_weak == "Projectile Motion"


@pytest.mark.asyncio
async def test_question_generation_and_answer_submission(db_session):
    """Verify question generation, evaluation, mastery update and recommendations."""
    student = User(
        id=uuid.uuid4(),
        email="student_tester@edusim.org",
        password_hash="mock_hash",
        name="Student Tester",
        role="student",
    )
    db_session.add(student)
    
    # Pre-cache a question for the topic
    cached_q = Question(
        id=uuid.uuid4(),
        topic="Newton's Second Law",
        difficulty="Medium",
        class_level="10",
        question="What is the equation for Newton's Second Law?",
        options=["F = m*a", "E = m*c^2", "v = d/t", "P = W/t"],
        correct="F = m*a",
        explanation="Force equals mass times acceleration."
    )
    db_session.add(cached_q)
    db_session.commit()

    questions = await QuestionService.generate_cached_questions(
        topic="Newton's Second Law",
        difficulty="Medium",
        class_level="10",
        count=1,
        db=db_session
    )
    assert len(questions) == 1
    q1 = questions[0]
    q1_text = q1["question"] if isinstance(q1, dict) else q1.question
    q1_correct = q1["correct"] if isinstance(q1, dict) else q1.correct
    assert q1_text == "What is the equation for Newton's Second Law?"
    assert q1_correct == "F = m*a"

    submit_res = await QuestionService.submit_question_answer(
        topic="Newton's Second Law",
        selected_option="F = m*a",
        student_id=str(student.id),
        correct_option="F = m*a",
        db=db_session
    )
    is_correct = submit_res.get("is_correct") if isinstance(submit_res, dict) else submit_res.is_correct
    streak = (submit_res.get("correct_streak") or submit_res.get("streak")) if isinstance(submit_res, dict) else submit_res.correct_streak
    mastery_score = submit_res.get("mastery_score") if isinstance(submit_res, dict) else submit_res.mastery_score

    assert is_correct is True
    assert streak >= 1
    assert mastery_score > 0

    mastery_record = db_session.query(StudentTopicMastery).filter(
        StudentTopicMastery.student_id == student.id
    ).first()
    assert mastery_record is not None
    assert mastery_record.total_attempts >= 1
    assert mastery_record.total_correct >= 1
    assert mastery_record.correct_streak >= 1
    assert mastery_record.mastery_score > 0
