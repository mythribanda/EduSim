from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'd8ab0c44fa40'
down_revision = 'b3edceb2dcbf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    for tbl in ('chapters', 'classes', 'curriculum_classes', 'subjects', 'topics'):
        if tbl in existing_tables:
            cols = [c["name"] for c in inspector.get_columns(tbl)]
            if 'display_order' not in cols:
                with op.batch_alter_table(tbl) as batch_op:
                    batch_op.add_column(sa.Column('display_order', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    pass

