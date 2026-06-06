"""Centralised application settings.

All environment variable reads are concentrated here.
No other module may read environment variables directly.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/health_insurance"
    ENCRYPTION_KEY: str


# Global settings instance
settings = Settings()
