"""add_books_and_curriculum_nodes

Revision ID: e183ad714e10
Revises: j0d1e2f3a4b5
Create Date: 2026-10-23 18:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e183ad714e10"
down_revision = "j0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create books table
    op.create_table(
        "books",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("board", sa.String(length=50), nullable=False),
        sa.Column("class_num", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("part", sa.Integer(), nullable=True),
        sa.Column("total_pages", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("extraction_status", sa.String(length=50), server_default="ok", nullable=False),
        sa.Column("pipeline_version", sa.String(length=50), server_default="2.0.0", nullable=False),
        sa.Column("source_files", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_books_code"),
    )
    op.create_index("ix_books_code", "books", ["code"], unique=True)

    # 2. Create curriculum_nodes table
    op.create_table(
        "curriculum_nodes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", sa.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_number", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.UUID(as_uuid=True), sa.ForeignKey("curriculum_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("order_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("official_number", sa.String(length=100), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("occurrence_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("source_file", sa.String(length=255), nullable=True),
        sa.Column("ocr_needed", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("identity_key", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_seen_run_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("book_id", "identity_key", name="uq_book_identity_key"),
    )
    op.create_index("ix_curriculum_nodes_book_id", "curriculum_nodes", ["book_id"])
    op.create_index("ix_curriculum_nodes_chapter_number", "curriculum_nodes", ["chapter_number"])
    op.create_index("ix_curriculum_nodes_parent_id", "curriculum_nodes", ["parent_id"])
    op.create_index("ix_curriculum_nodes_identity_key", "curriculum_nodes", ["identity_key"])
    op.create_index(
        "ix_curriculum_nodes_lookup",
        "curriculum_nodes",
        ["book_id", "chapter_number", "level", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_curriculum_nodes_lookup", table_name="curriculum_nodes")
    op.drop_index("ix_curriculum_nodes_identity_key", table_name="curriculum_nodes")
    op.drop_index("ix_curriculum_nodes_parent_id", table_name="curriculum_nodes")
    op.drop_index("ix_curriculum_nodes_chapter_number", table_name="curriculum_nodes")
    op.drop_index("ix_curriculum_nodes_book_id", table_name="curriculum_nodes")
    op.drop_table("curriculum_nodes")

    op.drop_index("ix_books_code", table_name="books")
    op.drop_table("books")
