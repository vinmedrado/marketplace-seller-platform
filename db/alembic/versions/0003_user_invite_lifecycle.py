"""Adiciona expiração e aceite auditável aos convites."""
from alembic import op
from sqlalchemy import Column, DateTime, inspect

revision = "0003_user_invite_lifecycle"
down_revision = "0002_remove_plaintext_marketplace_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "user_invites" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("user_invites")}
    with op.batch_alter_table("user_invites") as batch:
        if "expires_at" not in columns:
            batch.add_column(Column("expires_at", DateTime(timezone=True), nullable=True))
        if "accepted_at" not in columns:
            batch.add_column(Column("accepted_at", DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_invites") as batch:
        batch.drop_column("accepted_at")
        batch.drop_column("expires_at")
