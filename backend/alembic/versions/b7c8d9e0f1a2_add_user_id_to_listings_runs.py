"""add user_id to listings runs

Revision ID: b7c8d9e0f1a2
Revises: e6f7a8b9c0d1
Create Date: 2026-04-22 15:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _foreign_key_exists(table_name: str, foreign_key_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(fk["name"] == foreign_key_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    if not _table_exists("listings_runs"):
        return

    if not _column_exists("listings_runs", "user_id"):
        op.add_column("listings_runs", sa.Column("user_id", sa.Integer(), nullable=True))

    if not _foreign_key_exists("listings_runs", "fk_listings_runs_user_id_users"):
        op.create_foreign_key(
            "fk_listings_runs_user_id_users",
            "listings_runs",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _index_exists("listings_runs", op.f("ix_listings_runs_user_id")):
        op.create_index(op.f("ix_listings_runs_user_id"), "listings_runs", ["user_id"], unique=False)

    if not _index_exists("listings_runs", "ix_listings_runs_user_created"):
        op.create_index("ix_listings_runs_user_created", "listings_runs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    if not _table_exists("listings_runs"):
        return

    if _index_exists("listings_runs", "ix_listings_runs_user_created"):
        op.drop_index("ix_listings_runs_user_created", table_name="listings_runs")

    if _index_exists("listings_runs", op.f("ix_listings_runs_user_id")):
        op.drop_index(op.f("ix_listings_runs_user_id"), table_name="listings_runs")

    if _foreign_key_exists("listings_runs", "fk_listings_runs_user_id_users"):
        op.drop_constraint("fk_listings_runs_user_id_users", "listings_runs", type_="foreignkey")

    if _column_exists("listings_runs", "user_id"):
        op.drop_column("listings_runs", "user_id")
