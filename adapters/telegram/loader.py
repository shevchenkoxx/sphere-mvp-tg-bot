"""
Telegram bot loader - initializes bot, dispatcher, and services.
"""

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import settings

# Core services
from core.services import EventService, MatchingService, UserService
from core.services.config_service import ConfigService
from infrastructure.ai import OpenAIService, WhisperVoiceService
from infrastructure.ai.embedding_service import EmbeddingService
from infrastructure.ai.event_parser_service import EventParserService
from infrastructure.ai.meetup_ai_service import MeetupAIService
from infrastructure.ai.speed_dating_service import SpeedDatingService

# Infrastructure
from infrastructure.database import (
    SupabaseEventRepository,
    SupabaseMatchRepository,
    SupabaseUserRepository,
)
from infrastructure.database.config_repository import ConfigRepository
from infrastructure.database.meetup_repository import MeetupRepository
from infrastructure.database.speed_dating_repository import SpeedDatingRepository

# === BOT INITIALIZATION ===
bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# === REPOSITORIES ===
user_repo = SupabaseUserRepository()
event_repo = SupabaseEventRepository()
match_repo = SupabaseMatchRepository()


# === AI SERVICES ===
ai_service = OpenAIService()
voice_service = WhisperVoiceService()
embedding_service = EmbeddingService()
speed_dating_service = SpeedDatingService()
event_parser_service = EventParserService()
meetup_ai_service = MeetupAIService()


# === ADDITIONAL REPOSITORIES ===
speed_dating_repo = SpeedDatingRepository()
meetup_repo = MeetupRepository()
config_repo = ConfigRepository()


# === CONFIG SERVICE ===
config_service = ConfigService(config_repo)


# === BUSINESS SERVICES ===
user_service = UserService(user_repo=user_repo, ai_service=ai_service)
event_service = EventService(event_repo=event_repo, user_repo=user_repo)
matching_service = MatchingService(
    match_repo=match_repo,
    event_repo=event_repo,
    ai_service=ai_service
)
