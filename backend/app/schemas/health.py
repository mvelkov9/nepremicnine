"""Health check schema."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    checks: dict[str, str] | None = None
