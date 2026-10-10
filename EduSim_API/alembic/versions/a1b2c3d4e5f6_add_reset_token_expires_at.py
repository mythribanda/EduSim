from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fc62e10ff6d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if 'users' in existing_tables:
        cols = [c["name"] for c in inspector.get_columns('users')]
        if 'reset_token_expires_at' not in cols:
            with op.batch_alter_table('users') as batch_op:
                batch_op.add_column(
                    sa.Column('reset_token_expires_at', sa.DateTime(timezone=True), nullable=True)
                )


def downgrade() -> None:
    pass

