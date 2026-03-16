"""Region lookup: municipality → statistical region."""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RegionLookup(Base):
    __tablename__ = "region_lookup"
    __table_args__ = (UniqueConstraint("obcina_naziv", "vir", name="uq_region_lookup_naziv_vir"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    obcina_sifra: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)
    obcina_naziv: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    eid_statisticna_regija: Mapped[str | None] = mapped_column(String(50), nullable=True)
    regija_naziv: Mapped[str] = mapped_column(String(200), nullable=False)
    vir: Mapped[str] = mapped_column(String(50), default="privzeto", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
