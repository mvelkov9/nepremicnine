"""Prediction log entries."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PredictionLog(Base):
    __tablename__ = "prediction_logs"
    __table_args__ = (Index("ix_prediction_logs_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    predicted_price_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
