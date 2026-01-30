from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings - reads from environment variables"""

    # Telegram
    telegram_bot_token: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""

    # AI Services
    openai_api_key: str = ""

    # App Settings
    admin_telegram_ids: List[int] = []
    default_match_threshold: float = 0.6
    max_matches_per_event: int = 10

    # Environment
    env: str = "development"
    debug: bool = False

    @field_validator('admin_telegram_ids', mode='before')
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return v
        return []

    # Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,  # SUPABASE_URL == supabase_url
    )


# Create settings instance
settings = Settings()

# Debug: print what we got (remove in production)
if os.getenv("DEBUG", "").lower() == "true":
    print(f"Settings loaded:")
    print(f"  SUPABASE_URL: {'set' if settings.supabase_url else 'MISSING'}")
    print(f"  SUPABASE_KEY: {'set' if settings.supabase_key else 'MISSING'}")
