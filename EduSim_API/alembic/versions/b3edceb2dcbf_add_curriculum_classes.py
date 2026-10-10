from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'b3edceb2dcbf'
down_revision = '0001_create_persistence_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if "chapters" in existing_tables:
        chap_cols = [c["name"] for c in inspector.get_columns("chapters")]
        chap_indexes = [idx["name"] for idx in inspector.get_indexes("chapters")]
        if "ix_chapters_class_name" in chap_indexes:
            op.drop_index(op.f('ix_chapters_class_name'), table_name='chapters')
        if "class_name" in chap_cols:
            with op.batch_alter_table("chapters") as batch_op:
                batch_op.drop_column('class_name')

    if "subjects" in existing_tables:
        subj_cols = [c["name"] for c in inspector.get_columns("subjects")]
        subj_indexes = [idx["name"] for idx in inspector.get_indexes("subjects")]
        with op.batch_alter_table("subjects") as batch_op:
            if "class_id" not in subj_cols:
                batch_op.add_column(sa.Column('class_id', sa.Integer(), nullable=False))
            if "ix_subjects_code" in subj_indexes:
                batch_op.drop_index(op.f('ix_subjects_code'))
            batch_op.create_index(op.f('ix_subjects_code'), ['code'], unique=False)
            if "ix_subjects_class_id" not in subj_indexes:
                batch_op.create_index(op.f('ix_subjects_class_id'), ['class_id'], unique=False)

    if "topics" in existing_tables:
        top_cols = [c["name"] for c in inspector.get_columns("topics")]
        with op.batch_alter_table("topics") as batch_op:
            if "has_simulation" not in top_cols:
                batch_op.add_column(sa.Column('has_simulation', sa.Boolean(), nullable=True))
            if "simulation_route" not in top_cols:
                batch_op.add_column(sa.Column('simulation_route', sa.String(length=255), nullable=True))

    if "user_sessions" in existing_tables:
        sess_indexes = [idx["name"] for idx in inspector.get_indexes("user_sessions")]
        if "ix_user_sessions_session_key" in sess_indexes:
            op.drop_index(op.f('ix_user_sessions_session_key'), table_name='user_sessions')


def downgrade() -> None:
    pass

