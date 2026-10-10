"""add class_id and educator_id to users

Revision ID: h8b9c0d1e2f3
Revises: g7b8c9d0e1f2
Create Date: 2026-09-08 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "h8b9c0d1e2f3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("users")]

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "class_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("class_id", sa.UUID(as_uuid=True), nullable=True)
            )
        if "educator_id" not in existing_columns:
            batch_op.add_column(
                sa.Column("educator_id", sa.UUID(as_uuid=True), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_users_educator_id_users",
                "users",
                ["educator_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("users")]

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "educator_id" in existing_columns:
            batch_op.drop_constraint("fk_users_educator_id_users", type_="foreignkey")
            batch_op.drop_column("educator_id")
        if "class_id" in existing_columns:
            batch_op.drop_column("class_id")
