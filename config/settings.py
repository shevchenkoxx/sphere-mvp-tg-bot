from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os
from pathlib import Path

# Only load .env file if it exists (for local development)
# On Railway, env vars are set directly
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)


class Settings(BaseSettings):
    """Application settings - single source of truth for configuration"""

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
    debug: bool = True

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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
