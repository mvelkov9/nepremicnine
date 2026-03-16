"""Health check schema."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str | None = None
    environment: str | None = None
    checks: dict[str, str] | None = None
