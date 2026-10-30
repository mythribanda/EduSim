import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
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


class Book(Base):
    __tablename__ = "books"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    board = Column(String(50), nullable=False)
    class_num = Column(Integer, nullable=False)
    subject = Column(String(100), nullable=False)
    language = Column(String(50), nullable=True)
    part = Column(Integer, nullable=True)
    total_pages = Column(Integer, nullable=False, default=0)
    ocr_page_count = Column(Integer, nullable=False, default=0, server_default="0")
    text_quality = Column(String(50), nullable=True)
    sha256 = Column(String(64), nullable=True)
    extraction_status = Column(String(50), nullable=False, default="ok")
    pipeline_version = Column(String(50), nullable=False, default="2.0.0")
    source_files = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, server_default="1")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    nodes = relationship("CurriculumNode", back_populates="book", cascade="all, delete-orphan", passive_deletes=True)


class CurriculumNode(Base):
    __tablename__ = "curriculum_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number = Column(String(50), nullable=False, index=True)
    level = Column(String(50), nullable=False)  # chapter, topic, subtopic, activity, subheading
    parent_id = Column(UUID(as_uuid=True), ForeignKey("curriculum_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    order_index = Column(Integer, nullable=False, default=0)
    official_number = Column(String(100), nullable=True)
    title = Column(Text, nullable=False)
    normalized_title = Column(Text, nullable=False)
    occurrence_index = Column(Integer, nullable=False, default=0)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    source_page_start = Column(Integer, nullable=False, default=1, server_default="1")
    source_page_end = Column(Integer, nullable=False, default=1, server_default="1")
    source_file = Column(String(255), nullable=True)
    ocr_needed = Column(Boolean, default=False, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    identity_key = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_run_id = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    book = relationship("Book", back_populates="nodes")
    parent = relationship("CurriculumNode", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("book_id", "identity_key", name="uq_book_identity_key"),
        Index("ix_curriculum_nodes_lookup", "book_id", "chapter_number", "level", "is_active"),
    )
