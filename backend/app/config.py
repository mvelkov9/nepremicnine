"""Application settings via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    app_version: str = "0.11.0"
    max_upload_size_mb: int = 1024

    # Postgres
    database_url: str = "postgresql+asyncpg://nepremicnine:changeme_in_production@postgres:5432/nepremicnine"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    jwt_secret_key: str = "changeme_generate_a_real_secret_key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.app_env == "production":
        if "changeme" in s.jwt_secret_key or "changeme" in s.database_url:
            raise RuntimeError(
                "Placeholder credentials detected in production. Set JWT_SECRET_KEY and DATABASE_URL to real values."
            )
        if len(s.jwt_secret_key) < 32:
            raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters in production.")
    return s
