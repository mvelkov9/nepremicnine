"""merge training progress and index constraint heads

Revision ID: d4e5f6a7b8c9
Revises: c1b7d9c2a114, a3e1f8b9c012
Create Date: 2026-03-19 18:55:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = ("c1b7d9c2a114", "a3e1f8b9c012")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass