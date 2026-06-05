"""Centralised application settings.

All environment variable reads are concentrated here.
No other module may read environment variables directly.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings, populated from environment variables."""

    DATABASE_URL: str = "postgresql://postgres:postgres@db:5432/health_insurance"


# Global settings instance
settings = Settings()
