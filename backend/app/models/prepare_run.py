"""Tracked ETN preparation runs for admin drill-down surfaces."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrepareRun(Base):
    __tablename__ = "prepare_runs"
    __table_args__ = (Index("ix_prepare_runs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(120), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_pairs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_pair_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pairs_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spatial_phase: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_pairs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
