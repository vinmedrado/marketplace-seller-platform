"""Adiciona armazenamento de nonce OAuth de uso único."""
from alembic import op

from models.orm import OAuthState

revision = "0004_oauth_state_nonce"
down_revision = "0003_user_invite_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    OAuthState.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    OAuthState.__table__.drop(bind=op.get_bind(), checkfirst=True)
