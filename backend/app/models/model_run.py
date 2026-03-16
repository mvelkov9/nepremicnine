"""Model training run records."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_csv_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mae: Mapped[float | None] = mapped_column(nullable=True)
    rmse: Mapped[float | None] = mapped_column(nullable=True)
    r2: Mapped[float | None] = mapped_column(nullable=True)
    mape: Mapped[float | None] = mapped_column(nullable=True)
    median_ae: Mapped[float | None] = mapped_column(nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(nullable=True)
    per_type_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    combined_metrics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    trained_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
