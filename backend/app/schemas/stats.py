"""Statistics response schemas."""

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_records: int = 0
    avg_price: float | None = None
    median_price: float | None = None
    avg_area: float | None = None
    median_area: float | None = None
    avg_price_per_m2: float | None = None
    top_municipalities: list[dict] = []
    property_types: list[dict] = []


class RegionStats(BaseModel):
    region: str
    count: int = 0
    avg_price: float | None = None
    median_price: float | None = None
    avg_price_per_m2: float | None = None


class PriceDistribution(BaseModel):
    bins: list[float]
    counts: list[int]
    bin_labels: list[str]


class TrendPoint(BaseModel):
    year: str
    count: int = 0
    avg_price: float | None = None
    median_price: float | None = None
    by_type: dict = {}


class MunicipalityRegion(BaseModel):
    municipality: str
    region: str
    count: int = 0
