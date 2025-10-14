from __future__ import annotations

import os
from typing import List

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field


# Load .env from repo root (pos-lv2/.env) if present
load_dotenv(find_dotenv(filename=".env", usecwd=True), override=True)


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings(BaseModel):
    app_name: str = Field(default="POS Lv2 API")
    # CORS
    allowed_origins: List[str] = Field(
        default_factory=lambda: _split_csv(os.getenv("ALLOWED_ORIGINS", "http://localhost:3000"))
    )
    # Database URL (optional at this stage)
    database_url: str | None = Field(default=os.getenv("DATABASE_URL"))


_SETTINGS_CACHE: Settings | None = None


def get_settings() -> Settings:
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is None:
        _SETTINGS_CACHE = Settings()
    return _SETTINGS_CACHE

