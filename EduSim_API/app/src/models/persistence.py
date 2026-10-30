
import uuid

from sqlalchemy import (
    Boolean,
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


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# TODO: [Curriculum V2 Migration] Legacy curriculum models (curriculum_classes, subjects, chapters, topics).
# The source of truth has moved to `books` and `curriculum_nodes` in curriculum_pipeline_models.py.
# Retained because students_router, tutor service, auth stats, and learning loop still reference them.
class CurriculumClass(Base, TimestampMixin):
    __tablename__ = "curriculum_classes"

    id = Column(Integer, primary_key=True)  # Using Integer to match TS class ID
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = Column(Integer, ForeignKey("curriculum_classes.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    display_order = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_id", "code", name="uq_class_subject_code"),
    )


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_id", "name", name="uq_subject_chapter_name"),
    )


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    has_simulation = Column(Boolean, default=False)
    simulation_route = Column(String(255), nullable=True)
    display_order = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("chapter_id", "name", name="uq_chapter_topic_name"),
    )


class ChatHistory(Base, TimestampMixin):
    __tablename__ = "chat_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    session_type = Column(String(50), nullable=False, index=True)  # 'tutor' or 'formula_lab'
    role = Column(String(30), nullable=False, index=True)  # 'user' or 'assistant'
    topic = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)


class FormulaHistory(Base, TimestampMixin):
    __tablename__ = "formula_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    formula_id = Column(String(200), nullable=False, index=True)
    input_json = Column(JSON, nullable=False)
    output_json = Column(JSON, nullable=True)
    calculation_steps_json = Column(JSON, nullable=True)
    graph_json = Column(JSON, nullable=True)


class SimulationHistory(Base, TimestampMixin):
    __tablename__ = "simulation_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    simulation_id = Column(String(120), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    dsl_json = Column(JSON, nullable=True)
    runtime_json = Column(JSON, nullable=True)
    snapshot_json = Column(JSON, nullable=True)
    ui_state_json = Column(JSON, nullable=True)
    score = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class UserSetting(Base, TimestampMixin):
    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    setting_key = Column(String(120), nullable=False, index=True)
    setting_value = Column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "setting_key", name="uq_user_setting_key"),
    )


class UserSession(Base, TimestampMixin):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_key = Column(String(500), nullable=False)
    device_info = Column(JSON, nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_logout_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    metadata_json = Column(JSON, nullable=True)


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skill_level = Column(String(50), default="beginner", nullable=False)
    mastered_topics = Column(JSON, default=list, nullable=False)
    misconceptions = Column(JSON, default=list, nullable=False)
    metadata_json = Column(JSON, nullable=True)


class SessionEvent(Base):
    """
    Session events tracking user interactions (started, answered, completed, asked_tutor).
    Used for activity stream, streaks, and session analytics.
    """
    __tablename__ = "session_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = Column(UUID(as_uuid=True), nullable=True)
    event_type = Column(Text, nullable=False, index=True)
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationship to user
    student = relationship("User", foreign_keys=[student_id], lazy="joined")

