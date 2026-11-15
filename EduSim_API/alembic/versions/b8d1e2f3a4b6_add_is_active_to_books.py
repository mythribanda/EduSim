"""add is_active to books

Revision ID: b8d1e2f3a4b6
Revises: a7c9e2f4b610
Create Date: 2026-11-12 16:47:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b8d1e2f3a4b6"
down_revision = "a7c9e2f4b610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c["name"] for c in inspector.get_columns("books")]
    if "is_active" not in cols:
        with op.batch_alter_table("books", schema=None) as batch_op:
            batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.drop_column("is_active")
