"""create persistence schema

Revision ID: 0001_create_persistence_schema
Revises: 
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

from app.src.config.database import Base
from app.src.models import user as user_models  # noqa: F401
from app.src.models import persistence as persistence_models  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0001_create_persistence_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = [
        user_models.User.__table__,
        persistence_models.CurriculumClass.__table__,
        persistence_models.Subject.__table__,
        persistence_models.Chapter.__table__,
        persistence_models.Topic.__table__,
        persistence_models.ChatHistory.__table__,
        persistence_models.FormulaHistory.__table__,
        persistence_models.SimulationHistory.__table__,
        persistence_models.UserSetting.__table__,
        persistence_models.UserSession.__table__,
    ]
    Base.metadata.create_all(bind=bind, tables=tables)


def downgrade() -> None:
    pass

