"""audit: user_id FK + settings column

Revision ID: 0004_audit_user_fk_and_settings
Revises: 0002_users
Create Date: 2026-05-14 18:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_audit_user_fk_and_settings"
down_revision: str | None = "0002_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audits",
        sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("audits", sa.Column("user_id", sa.UUID(), nullable=True))
    op.create_index("ix_audits_user_id", "audits", ["user_id"])
    op.create_foreign_key(
        "fk_audits_user_id", "audits", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    # uwaga: jeśli masz w dev stare audyty bez user_id — usuń je przed tym krokiem
    op.alter_column("audits", "user_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint("fk_audits_user_id", "audits", type_="foreignkey")
    op.drop_index("ix_audits_user_id", table_name="audits")
    op.drop_column("audits", "user_id")
    op.drop_column("audits", "settings")
