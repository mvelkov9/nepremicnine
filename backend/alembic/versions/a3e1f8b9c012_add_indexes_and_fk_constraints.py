"""Add missing indexes, FK constraints, and partial index for active jobs.

Revision ID: a3e1f8b9c012
Revises: f5ab9d4c4f21
Create Date: 2026-03-18 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3e1f8b9c012"
down_revision: str | None = "f5ab9d4c4f21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- dataset_files: add FK and index on uploaded_by ---
    op.create_index("ix_dataset_files_uploaded_by", "dataset_files", ["uploaded_by"])
    op.create_foreign_key(
        "fk_dataset_files_uploaded_by_users",
        "dataset_files",
        "users",
        ["uploaded_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- model_runs: add FK and index on trained_by ---
    op.create_index("ix_model_runs_trained_by", "model_runs", ["trained_by"])
    op.create_foreign_key(
        "fk_model_runs_trained_by_users",
        "model_runs",
        "users",
        ["trained_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- training_jobs: partial index for active jobs, index on created_at ---
    op.create_index("ix_training_jobs_created_at", "training_jobs", ["created_at"])
    op.execute(
        "CREATE INDEX ix_training_jobs_active ON training_jobs (updated_at) WHERE status IN ('queued', 'running')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_training_jobs_active")
    op.drop_index("ix_training_jobs_created_at", table_name="training_jobs")
    op.drop_constraint("fk_model_runs_trained_by_users", "model_runs", type_="foreignkey")
    op.drop_index("ix_model_runs_trained_by", table_name="model_runs")
    op.drop_constraint("fk_dataset_files_uploaded_by_users", "dataset_files", type_="foreignkey")
    op.drop_index("ix_dataset_files_uploaded_by", table_name="dataset_files")
