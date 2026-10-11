"""
EduSim_API/tests/test_mastery.py
Unit tests for EduSim Mastery Score calculation and update_mastery persistence flow.
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
from app.src.models.school import StudentTopicMastery
from app.src.services.mastery import (
    calculate_mastery_score,
    update_mastery,
    get_weak_topics,
    get_recommended_difficulty,
)


@pytest.fixture
def db_session():
    """Create an isolated in-memory SQLite database for testing mastery updates."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_mastery_scoring_formula_edge_cases():
    """
    Verify exact test cases required:
    - 0/10 correct -> low mastery (0.0)
    - 5/10 correct -> approximately 30 points from accuracy before streak contribution
    - 10/10 correct + 10 streak -> 100
    - 10/10 correct + 0 streak -> 60
    - 5/10 correct + 5 streak -> 50
    """
    # 0 attempts
    assert calculate_mastery_score(correct_streak=0, total_correct=0, total_attempts=0) == 0.0

    # 0/10 correct (0% accuracy, 0 streak) -> 0.0
    score_zero = calculate_mastery_score(correct_streak=0, total_correct=0, total_attempts=10)
    assert score_zero == 0.0

    # 5/10 correct with 0 streak -> 30 points (50% accuracy * 60 + 0)
    score_accuracy_only = calculate_mastery_score(correct_streak=0, total_correct=5, total_attempts=10)
    assert score_accuracy_only == 30.0

    # 10/10 correct + 10 streak -> 100 (100% * 60 + (10/10)*40 = 60 + 40 = 100)
    score_max = calculate_mastery_score(correct_streak=10, total_correct=10, total_attempts=10)
    assert score_max == 100.0

    # 10/10 correct + 0 streak -> 60 (100% * 60 + (0/10)*40 = 60 + 0 = 60)
    score_perfect_acc_zero_streak = calculate_mastery_score(correct_streak=0, total_correct=10, total_attempts=10)
    assert score_perfect_acc_zero_streak == 60.0

    # 5/10 correct + 5 streak -> 50 (50% * 60 + (5/10)*40 = 30 + 20 = 50)
    score_mid = calculate_mastery_score(correct_streak=5, total_correct=5, total_attempts=10)
    assert score_mid == 50.0


def test_mastery_clamping():
    """Verify values above maximum or with large streaks clamp cleanly to 0-100."""
    # Streak > 10 capped at 10 (40 points)
    score_streak_overflow = calculate_mastery_score(correct_streak=25, total_correct=10, total_attempts=10)
    assert score_streak_overflow == 100.0

    # Negative numbers handled gracefully
    score_neg = calculate_mastery_score(correct_streak=-5, total_correct=0, total_attempts=10)
    assert score_neg == 0.0


def test_update_mastery_persistence_flow(db_session):
    """
    Verify that update_mastery():
    1. Creates the StudentTopicMastery record if not exists.
    2. Correctly updates total_attempts, total_correct, correct_streak.
    3. Calculates and persists the accurate mastery score to the DB.
    """
    student_id = uuid.uuid4()
    topic_id = "newton-second-law"

    # 1. First attempt: Correct
    rec1 = update_mastery(student_id=student_id, topic_id=topic_id, is_correct=True, db=db_session)
    assert rec1.total_attempts == 1
    assert rec1.total_correct == 1
    assert rec1.correct_streak == 1
    # Accuracy: (1/1)*60 = 60; Streak: (1/10)*40 = 4 -> Total = 64.0
    assert rec1.mastery_score == 64.0

    # Verify persisted in database session directly
    db_rec1 = db_session.query(StudentTopicMastery).filter(
        StudentTopicMastery.student_id == student_id,
        StudentTopicMastery.topic_id == topic_id,
    ).first()
    assert db_rec1 is not None
    assert db_rec1.mastery_score == 64.0

    # 2. Second attempt: Incorrect
    rec2 = update_mastery(student_id=student_id, topic_id=topic_id, is_correct=False, db=db_session)
    assert rec2.total_attempts == 2
    assert rec2.total_correct == 1
    assert rec2.correct_streak == 0
    # Accuracy: (1/2)*60 = 30; Streak: (0/10)*40 = 0 -> Total = 30.0
    assert rec2.mastery_score == 30.0

    # Verify updated in database
    db_session.expire_all()
    db_rec2 = db_session.query(StudentTopicMastery).filter(
        StudentTopicMastery.student_id == student_id,
        StudentTopicMastery.topic_id == topic_id,
    ).first()
    assert db_rec2.mastery_score == 30.0
    assert db_rec2.correct_streak == 0
    assert db_rec2.total_attempts == 2

    # 3. Third attempt: Correct
    rec3 = update_mastery(student_id=student_id, topic_id=topic_id, is_correct=True, db=db_session)
    assert rec3.total_attempts == 3
    assert rec3.total_correct == 2
    assert rec3.correct_streak == 1
    # Accuracy: (2/3)*60 = 40.0; Streak: (1/10)*40 = 4.0 -> Total = 44.0
    assert rec3.mastery_score == 44.0


def test_weak_topics_and_recommended_difficulty(db_session):
    """Verify weak topic filtering (<40) and recommended difficulty bands."""
    student_id = uuid.uuid4()
    
    # Topic 1: Low score (<40) -> weak topic -> recommended difficulty 'easy'
    # 1/5 correct with 0 streak = (1/5)*60 = 12.0
    for _ in range(4):
        update_mastery(student_id=student_id, topic_id="projectile-motion", is_correct=False, db=db_session)
    update_mastery(student_id=student_id, topic_id="projectile-motion", is_correct=True, db=db_session)

    weak = get_weak_topics(student_id=student_id, db=db_session)
    assert len(weak) == 1
    assert weak[0].topic_id == "projectile-motion"
    assert weak[0].mastery_score < 40.0

    diff = get_recommended_difficulty(student_id=student_id, topic_id="projectile-motion", db=db_session)
    assert diff == "easy"
