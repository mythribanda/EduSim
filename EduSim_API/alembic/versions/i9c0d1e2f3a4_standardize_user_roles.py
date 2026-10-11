"""standardize user roles to student, teacher, admin

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
Create Date: 2026-10-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i9c0d1e2f3a4"
down_revision = "h8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Standardize existing data:
    # 'educator' -> 'teacher', 'parent' -> 'student', keep 'admin', others default to 'student'
    op.execute("UPDATE users SET role = 'teacher' WHERE role = 'educator'")
    op.execute("UPDATE users SET role = 'student' WHERE role = 'parent'")
    op.execute("UPDATE users SET role = 'student' WHERE role IS NULL OR role NOT IN ('student', 'teacher', 'admin')")

    # 2. Add server default and CHECK constraint if not present
    from sqlalchemy.engine.reflection import Inspector
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_check_constraints = [
        c.get("name") for c in inspector.get_check_constraints("users")
    ]

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.String(20),
            server_default="student",
            nullable=True,
        )
        if "ck_users_role" not in existing_check_constraints:
            batch_op.create_check_constraint(
                "ck_users_role",
                "role IN ('student', 'teacher', 'admin')",
            )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.alter_column(
            "role",
            existing_type=sa.String(20),
            server_default=None,
            nullable=True,
        )
