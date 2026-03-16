"""Async training job tracking."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[JobStatus] = mapped_column(String(20), default=JobStatus.queued, nullable=False, index=True)
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    csv_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fitted_trees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_trees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trees_per_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    eta_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
