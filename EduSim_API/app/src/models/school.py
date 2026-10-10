import uuid
import secrets
from sqlalchemy import (
    Boolean,
    CheckConstraint,
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


def generate_join_code() -> str:
    """Generate an 8-character uppercase alphanumeric join code (e.g. PHY10A9B)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(8))


class Class(Base):
    """
    Teacher classroom model representing a distinct class section (e.g., '10-A', '10-B').
    Created by a teacher/educator and allows student self-enrollment via join_code.
    """
    __tablename__ = "classes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    grade_level = Column(String(50), nullable=False)
    institution_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    join_code = Column(String(20), unique=True, index=True, nullable=False, default=generate_join_code)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    teacher = relationship("User", foreign_keys=[created_by], lazy="joined")
    teacher_subjects = relationship(
        "TeacherClassSubject",
        back_populates="class_",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    enrollments = relationship(
        "StudentEnrollment",
        back_populates="class_",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TeacherClassSubject(Base):
    """
    Mapping between a teacher, a class, and a subject taught.
    A teacher can teach Physics to 10-A and 10-B simultaneously.
    """
    __tablename__ = "teacher_class_subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_id], lazy="joined")
    class_ = relationship("Class", back_populates="teacher_subjects", foreign_keys=[class_id])

    __table_args__ = (
        UniqueConstraint("teacher_id", "class_id", "subject", name="uq_teacher_class_subject"),
        Index("ix_tcs_class_subject", "class_id", "subject"),
        Index("ix_tcs_teacher_subject", "teacher_id", "subject"),
    )


class StudentEnrollment(Base):
    """
    Student enrollment record linking a student to an active/inactive class.
    """
    __tablename__ = "student_enrollments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(20), default="active", nullable=False)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], lazy="joined")
    class_ = relationship("Class", back_populates="enrollments", foreign_keys=[class_id])

    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="chk_enrollment_status"),
        UniqueConstraint("student_id", "class_id", name="uq_student_class_enrollment"),
        Index("ix_enrollment_student_status", "student_id", "status"),
        Index("ix_enrollment_class_status", "class_id", "status"),
    )


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


class Assignment(Base):
    """
    A teacher-created assignment linked to a class (and optionally a curriculum module).
    Students in that class can submit responses; teachers then grade submissions.
    """
    __tablename__ = "assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    module_id = Column(String(255), nullable=True, index=True)
    due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    max_score = Column(Float, default=100.0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_id], lazy="joined")
    class_ = relationship("Class", foreign_keys=[class_id])
    submissions = relationship(
        "Submission",
        back_populates="assignment",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_assignment_class_due", "class_id", "due_date"),
        Index("ix_assignment_teacher_created", "teacher_id", "created_at"),
    )


class Submission(Base):
    """
    A student's submission for a specific Assignment.
    Status lifecycle: pending → submitted → graded.
    """
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, nullable=True)
    feedback = Column(String, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    assignment = relationship("Assignment", back_populates="submissions", foreign_keys=[assignment_id])
    student = relationship("User", foreign_keys=[student_id], lazy="joined")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'submitted', 'graded')", name="chk_submission_status"),
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),
        Index("ix_submission_student_status", "student_id", "status"),
        Index("ix_submission_assignment_status", "assignment_id", "status"),
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
    "generate_join_code",
    "Class",
    "TeacherClassSubject",
    "StudentEnrollment",
    "StudentTopicMastery",
    "Assignment",
    "Submission",
    "Question",
]
