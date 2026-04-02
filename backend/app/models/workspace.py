"""Saved viewer/admin workspace definitions."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_user_page_updated", "user_id", "page", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), default="private", nullable=False)
    page: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    filters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tab: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sort: Mapped[str | None] = mapped_column(String(120), nullable=True)
    columns_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
