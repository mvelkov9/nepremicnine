"""Region lookup schemas."""

from pydantic import BaseModel


class RegionLookupResponse(BaseModel):
    id: int
    obcina_sifra: str | None = None
    obcina_naziv: str
    regija_naziv: str
    vir: str

    model_config = {"from_attributes": True}


class RegionListResponse(BaseModel):
    regions: list[RegionLookupResponse]
    total: int
