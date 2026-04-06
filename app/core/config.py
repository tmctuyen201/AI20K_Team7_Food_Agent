"""Configuration management using pydantic-settings.

Loads environment variables from .env file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Provider
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Google APIs
    google_places_api_key: str = ""
    google_geocoding_api_key: str = ""
    serp_api_key: str = ""

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017/foodie_agent"
    mongo_root_user: str = "admin"
    mongo_root_password: str = "password"

    # JWT Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Rate Limiting
    rate_limit_per_minute: int = 60

    # Application
    environment: Literal["development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Internal: derived values
    @property
    def llm_api_key(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        return self.openai_api_key

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Global singleton
settings = Settings()
