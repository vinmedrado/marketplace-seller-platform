"""Baseline do esquema atual usando o ORM como fonte de verdade."""
from alembic import op

from db.base import Base
import models.orm  # noqa: F401

revision = "0001_orm_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
