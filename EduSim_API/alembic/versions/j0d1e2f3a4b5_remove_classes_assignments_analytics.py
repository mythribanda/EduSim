"""remove classes, assignments, enrollments, and teacher fields

Revision ID: j0d1e2f3a4b5
Revises: i9c0d1e2f3a4
Create Date: 2026-10-10 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "j0d1e2f3a4b5"
down_revision = "i9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Drop dependent tables first in correct foreign-key order
    tables_to_drop = [
        "submissions",
        "assignments",
        "student_enrollments",
        "teacher_class_subjects",
        "classes",
    ]
    for table_name in tables_to_drop:
        if table_name in existing_tables:
            op.drop_table(table_name)

    # 2. Drop educator_id and class_id columns from users
    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    with op.batch_alter_table("users", schema=None) as batch_op:
        if "educator_id" in existing_columns:
            # Check foreign keys on users
            fks = inspector.get_foreign_keys("users")
            for fk in fks:
                if "educator_id" in fk.get("constrained_columns", []):
                    batch_op.drop_constraint(fk["name"], type_="foreignkey")
            batch_op.drop_column("educator_id")
        if "class_id" in existing_columns:
            batch_op.drop_column("class_id")


def downgrade() -> None:
    # Intentionally omitted as this is a permanent removal of unused features
    pass
