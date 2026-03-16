"""add_training_progress_and_model_run_details

Revision ID: c1b7d9c2a114
Revises: f5ab9d4c4f21
Create Date: 2026-03-16 21:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1b7d9c2a114"
down_revision: str | Sequence[str] | None = "f5ab9d4c4f21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("training_jobs", sa.Column("current_model", sa.String(length=120), nullable=True))
    op.add_column("training_jobs", sa.Column("current_model_index", sa.Integer(), nullable=True))
    op.add_column("training_jobs", sa.Column("total_models", sa.Integer(), nullable=True))
    op.add_column("training_jobs", sa.Column("current_model_progress", sa.Integer(), nullable=True))
    op.add_column("training_jobs", sa.Column("elapsed_sec", sa.Float(), nullable=True))

    op.add_column("model_runs", sa.Column("mape", sa.Float(), nullable=True))
    op.add_column("model_runs", sa.Column("median_ae", sa.Float(), nullable=True))
    op.add_column("model_runs", sa.Column("duration_sec", sa.Float(), nullable=True))
    op.add_column("model_runs", sa.Column("per_type_count", sa.Integer(), nullable=True))
    op.add_column("model_runs", sa.Column("model_type", sa.String(length=120), nullable=True))
    op.add_column("model_runs", sa.Column("combined_metrics_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("model_runs", "combined_metrics_json")
    op.drop_column("model_runs", "model_type")
    op.drop_column("model_runs", "per_type_count")
    op.drop_column("model_runs", "duration_sec")
    op.drop_column("model_runs", "median_ae")
    op.drop_column("model_runs", "mape")

    op.drop_column("training_jobs", "elapsed_sec")
    op.drop_column("training_jobs", "current_model_progress")
    op.drop_column("training_jobs", "total_models")
    op.drop_column("training_jobs", "current_model_index")
    op.drop_column("training_jobs", "current_model")
