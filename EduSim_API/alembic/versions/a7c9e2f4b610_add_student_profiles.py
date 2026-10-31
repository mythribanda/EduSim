"""create student_profiles table

Revision ID: a7c9e2f4b610
Revises: f294be825e21
"""

from alembic import op
import sqlalchemy as sa

revision = "a7c9e2f4b610"
down_revision = "f294be825e21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_profiles",
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "skill_level",
            sa.String(length=50),
            nullable=False,
            server_default="beginner",
        ),
        sa.Column(
            "mastered_topics",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "misconceptions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("student_profiles")
