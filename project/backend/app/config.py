"""
config.py — Environment variable loading and application settings.

All configuration is read from environment variables (with .env fallback via
python-dotenv).  Swapping SQLite → PostgreSQL later only requires changing
DATABASE_URL in .env — no code changes needed.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    APP_NAME: str = "AI College Request Automation"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # ── Database ───────────────────────────────────────────────────────────────
    # SQLite for local dev; swap to postgresql+asyncpg://... for prod.
    DATABASE_URL: str = "sqlite+aiosqlite:///./college_requests.db"

    # ── AI Microservice ────────────────────────────────────────────────────────
    AI_SERVICE_URL: str = "http://localhost:8001"
    AI_SERVICE_TIMEOUT_SECONDS: float = 5.0
    AI_SERVICE_MAX_RETRIES: int = 2

    # ── Notion ─────────────────────────────────────────────────────────────────
    NOTION_API_KEY: str = Field(default="", description="Notion integration token")
    NOTION_REQUESTS_DB_ID: str = Field(default="", description="Notion DB for requests")
    NOTION_RUNLOG_DB_ID: str = Field(default="", description="Notion DB for run logs")
    NOTION_APPROVALS_DB_ID: str = Field(default="", description="Notion DB for approvals")

    # ── Polling ────────────────────────────────────────────────────────────────
    APPROVAL_POLL_INTERVAL_SECONDS: float = 7.0
    APPROVAL_POLL_MAX_WAIT_SECONDS: float = 3600.0  # 1 hour max

    # ── Idempotency ────────────────────────────────────────────────────────────
    IDEMPOTENCY_WINDOW_SECONDS: int = 300  # 5 minutes

    # ── Input validation limits ────────────────────────────────────────────────
    REQUEST_TEXT_MAX_LENGTH: int = 5000

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
