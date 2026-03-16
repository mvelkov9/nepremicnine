"""FastAPI application factory."""

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from arq import create_pool
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.gzip import GZipMiddleware

from app.api.admin import router as admin_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.data import router as data_router
from app.api.health import router as health_router
from app.api.model import router as model_router
from app.api.predict import router as predict_router
from app.api.regions import router as regions_router
from app.api.stats import router as stats_router
from app.api.train import router as train_router
from app.config import get_settings
from app.database import Base, engine
from app.rate_limit import limiter
from app.tasks.training_worker import _parse_redis_url

logger = logging.getLogger(__name__)


def configure_logging():
    """Configure logging: JSON in production, simple format in development."""
    settings = get_settings()
    is_production = settings.app_env == "production"
    if is_production:
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    else:
        fmt = "%(asctime)s %(levelname)-8s %(name)s  %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables (dev only — production uses Alembic)
    settings = get_settings()
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    # Redis pool for token blacklist
    app.state.redis = await create_pool(_parse_redis_url(settings.redis_url))
    yield
    # Shutdown
    await app.state.redis.close()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    is_production = settings.app_env == "production"

    app = FastAPI(
        title="Nepremicnine API",
        description="Slovenian real estate price analysis & prediction",
        version=settings.app_version,
        lifespan=lifespan,
        # Disable interactive docs in production to reduce attack surface
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # GZip compression for responses >= 1000 bytes
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Global exception handler — structured 500 without stack trace leaks
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled exception request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    # Security response headers
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    # Structured request logging with correlation IDs
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        user_id = getattr(request.state, "user_id", None)
        logger.info(
            "method=%s path=%s status_code=%d duration_ms=%.2f user_id=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            user_id or "-",
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response

    # Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(data_router, prefix="/api")
    app.include_router(regions_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")
    app.include_router(train_router, prefix="/api")
    app.include_router(predict_router, prefix="/api")
    app.include_router(model_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(analysis_router, prefix="/api")

    return app


app = create_app()
