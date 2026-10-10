from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'fc62e10ff6d1'
down_revision = 'd8ab0c44fa40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if 'chapters' in existing_tables:
        uqs = [u.get("name") for u in inspector.get_unique_constraints('chapters')]
        if 'uq_subject_chapter_name' not in uqs:
            try:
                with op.batch_alter_table('chapters') as batch_op:
                    batch_op.create_unique_constraint('uq_subject_chapter_name', ['subject_id', 'name'])
            except Exception:
                pass

    if 'topics' in existing_tables:
        uqs = [u.get("name") for u in inspector.get_unique_constraints('topics')]
        if 'uq_chapter_topic_name' not in uqs:
            try:
                with op.batch_alter_table('topics') as batch_op:
                    batch_op.create_unique_constraint('uq_chapter_topic_name', ['chapter_id', 'name'])
            except Exception:
                pass


def downgrade() -> None:
    pass

