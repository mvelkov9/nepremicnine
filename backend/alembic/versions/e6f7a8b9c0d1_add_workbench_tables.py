"""add workbench tables

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-04-02 12:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("activity_events"):
        op.create_table(
            "activity_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("scope", sa.String(length=40), nullable=False),
            sa.Column("category", sa.String(length=60), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("link", sa.String(length=255), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("activity_events", "ix_activity_events_scope_created"):
        op.create_index("ix_activity_events_scope_created", "activity_events", ["scope", "created_at"], unique=False)
    if not _index_exists("activity_events", "ix_activity_events_user_created"):
        op.create_index("ix_activity_events_user_created", "activity_events", ["user_id", "created_at"], unique=False)
    if not _index_exists("activity_events", op.f("ix_activity_events_user_id")):
        op.create_index(op.f("ix_activity_events_user_id"), "activity_events", ["user_id"], unique=False)

    if not _table_exists("prepare_runs"):
        op.create_table(
            "prepare_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("stage", sa.String(length=120), nullable=True),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_pairs", sa.Integer(), nullable=True),
            sa.Column("current_pair_index", sa.Integer(), nullable=True),
            sa.Column("current_label", sa.String(length=200), nullable=True),
            sa.Column("pairs_completed", sa.Integer(), nullable=True),
            sa.Column("rows", sa.Integer(), nullable=True),
            sa.Column("spatial_phase", sa.String(length=80), nullable=True),
            sa.Column("source_pairs_json", sa.Text(), nullable=True),
            sa.Column("enrichment_options_json", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("prepare_runs", "ix_prepare_runs_created_at"):
        op.create_index("ix_prepare_runs_created_at", "prepare_runs", ["created_at"], unique=False)
    if not _index_exists("prepare_runs", op.f("ix_prepare_runs_created_by")):
        op.create_index(op.f("ix_prepare_runs_created_by"), "prepare_runs", ["created_by"], unique=False)
    if not _index_exists("prepare_runs", op.f("ix_prepare_runs_job_id")):
        op.create_index(op.f("ix_prepare_runs_job_id"), "prepare_runs", ["job_id"], unique=True)
    if not _index_exists("prepare_runs", op.f("ix_prepare_runs_status")):
        op.create_index(op.f("ix_prepare_runs_status"), "prepare_runs", ["status"], unique=False)
    if not _index_exists("prepare_runs", op.f("ix_prepare_runs_updated_at")):
        op.create_index(op.f("ix_prepare_runs_updated_at"), "prepare_runs", ["updated_at"], unique=False)

    if not _table_exists("watchlist_items"):
        op.create_table(
            "watchlist_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("entity_type", sa.String(length=40), nullable=False),
            sa.Column("entity_key", sa.String(length=200), nullable=False),
            sa.Column("display_label", sa.String(length=200), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "entity_type", "entity_key", name="uq_watchlist_user_entity"),
        )
    if not _index_exists("watchlist_items", "ix_watchlist_user_created"):
        op.create_index("ix_watchlist_user_created", "watchlist_items", ["user_id", "created_at"], unique=False)
    if not _index_exists("watchlist_items", op.f("ix_watchlist_items_user_id")):
        op.create_index(op.f("ix_watchlist_items_user_id"), "watchlist_items", ["user_id"], unique=False)

    if not _table_exists("workspaces"):
        op.create_table(
            "workspaces",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("scope", sa.String(length=40), nullable=False),
            sa.Column("page", sa.String(length=80), nullable=False),
            sa.Column("filters_json", sa.Text(), nullable=True),
            sa.Column("tab", sa.String(length=80), nullable=True),
            sa.Column("sort", sa.String(length=120), nullable=True),
            sa.Column("columns_json", sa.Text(), nullable=True),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("workspaces", "ix_workspaces_user_page_updated"):
        op.create_index(
            "ix_workspaces_user_page_updated", "workspaces", ["user_id", "page", "updated_at"], unique=False
        )
    if not _index_exists("workspaces", op.f("ix_workspaces_page")):
        op.create_index(op.f("ix_workspaces_page"), "workspaces", ["page"], unique=False)
    if not _index_exists("workspaces", op.f("ix_workspaces_user_id")):
        op.create_index(op.f("ix_workspaces_user_id"), "workspaces", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_workspaces_user_id"), table_name="workspaces")
    op.drop_index(op.f("ix_workspaces_page"), table_name="workspaces")
    op.drop_index("ix_workspaces_user_page_updated", table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index(op.f("ix_watchlist_items_user_id"), table_name="watchlist_items")
    op.drop_index("ix_watchlist_user_created", table_name="watchlist_items")
    op.drop_table("watchlist_items")

    op.drop_index(op.f("ix_prepare_runs_updated_at"), table_name="prepare_runs")
    op.drop_index(op.f("ix_prepare_runs_status"), table_name="prepare_runs")
    op.drop_index(op.f("ix_prepare_runs_job_id"), table_name="prepare_runs")
    op.drop_index(op.f("ix_prepare_runs_created_by"), table_name="prepare_runs")
    op.drop_index("ix_prepare_runs_created_at", table_name="prepare_runs")
    op.drop_table("prepare_runs")

    op.drop_index(op.f("ix_activity_events_user_id"), table_name="activity_events")
    op.drop_index("ix_activity_events_user_created", table_name="activity_events")
    op.drop_index("ix_activity_events_scope_created", table_name="activity_events")
    op.drop_table("activity_events")
