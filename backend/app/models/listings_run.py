"""Listing scoring run results."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ListingsRun(Base):
    __tablename__ = "listings_runs"
    __table_args__ = (Index("ix_listings_runs_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overpriced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    underpriced_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    market_aligned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
