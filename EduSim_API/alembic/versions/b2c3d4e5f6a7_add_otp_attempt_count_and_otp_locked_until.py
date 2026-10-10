from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if 'users' in existing_tables:
        cols = [c["name"] for c in inspector.get_columns('users')]
        with op.batch_alter_table('users') as batch_op:
            if 'otp_attempt_count' not in cols:
                batch_op.add_column(
                    sa.Column('otp_attempt_count', sa.Integer(), nullable=False, server_default='0')
                )
            if 'otp_locked_until' not in cols:
                batch_op.add_column(
                    sa.Column('otp_locked_until', sa.DateTime(timezone=True), nullable=True)
                )


def downgrade() -> None:
    pass

