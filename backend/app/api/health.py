"""Health check endpoint."""

import logging
import os

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "models",
    "price_model.joblib",
)


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    settings = get_settings()

    checks: dict[str, str] = {}

    # Database check
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.warning("Health check: database unreachable")
        checks["database"] = "error"

    # Redis check
    try:
        redis = getattr(request.app.state, "redis", None)
        if redis is not None:
            await redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "not_configured"
    except Exception:
        logger.warning("Health check: redis unreachable")
        checks["redis"] = "error"

    # Model check
    if os.path.exists(MODEL_PATH):
        checks["model"] = "loaded"
    else:
        checks["model"] = "not_found"

    overall = "healthy" if all(v in ("ok", "loaded") for v in checks.values()) else "degraded"

    response = HealthResponse(
        status=overall,
        checks=checks,
        version=settings.app_version,
    )
    # Keep environment internal in production, but expose the app version everywhere.
    if settings.app_env != "production":
        response.environment = settings.app_env

    return response
