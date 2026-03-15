"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.data import router as data_router
from app.api.regions import router as regions_router
from app.api.stats import router as stats_router
from app.api.train import router as train_router
from app.api.predict import router as predict_router
from app.api.model import router as model_router
from app.api.admin import router as admin_router
from app.api.analysis import router as analysis_router
from app.config import get_settings
from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables (dev only — production uses Alembic)
    settings = get_settings()
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nepremicnine API",
        description="Slovenian real estate price analysis & prediction",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
