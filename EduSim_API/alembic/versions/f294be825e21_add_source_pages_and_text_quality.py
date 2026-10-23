"""add_source_pages_and_text_quality

Revision ID: f294be825e21
Revises: e183ad714e10
Create Date: 2026-10-23 19:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f294be825e21"
down_revision = "e183ad714e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add ocr_page_count and text_quality to books
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ocr_page_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("text_quality", sa.String(length=50), nullable=True))

    # 2. Add source_page_start and source_page_end to curriculum_nodes
    with op.batch_alter_table("curriculum_nodes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_page_start", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("source_page_end", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    # 1. Remove columns from curriculum_nodes
    with op.batch_alter_table("curriculum_nodes", schema=None) as batch_op:
        batch_op.drop_column("source_page_end")
        batch_op.drop_column("source_page_start")

    # 2. Remove columns from books
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.drop_column("text_quality")
        batch_op.drop_column("ocr_page_count")
