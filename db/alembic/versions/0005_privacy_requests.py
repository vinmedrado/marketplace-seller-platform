"""Adiciona protocolos de exercício de direitos LGPD."""
from alembic import op

from models.orm import PrivacyRequest

revision = "0005_privacy_requests"
down_revision = "0004_oauth_state_nonce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    PrivacyRequest.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    PrivacyRequest.__table__.drop(bind=op.get_bind(), checkfirst=True)
