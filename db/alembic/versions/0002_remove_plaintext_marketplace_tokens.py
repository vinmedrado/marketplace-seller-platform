"""Remove colunas legadas que armazenavam tokens sem criptografia."""
from alembic import op
from sqlalchemy import inspect

revision = "0002_remove_plaintext_marketplace_tokens"
down_revision = "0001_orm_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "marketplace_accounts" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("marketplace_accounts")}
    removable = [name for name in ("access_token", "refresh_token") if name in columns]
    if not removable:
        return
    with op.batch_alter_table("marketplace_accounts") as batch:
        for name in removable:
            batch.drop_column(name)


def downgrade() -> None:
    # Tokens removidos não devem ser restaurados.
    pass
