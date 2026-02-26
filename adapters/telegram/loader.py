"""
Telegram bot loader - initializes bot, dispatcher, and services.
"""

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from config.settings import settings

# Infrastructure
from infrastructure.database import (
    SupabaseUserRepository,
    SupabaseEventRepository,
    SupabaseMatchRepository,
)
from infrastructure.ai import OpenAIService, WhisperVoiceService
from infrastructure.ai.embedding_service import EmbeddingService
from infrastructure.ai.speed_dating_service import SpeedDatingService
from infrastructure.ai.event_parser_service import EventParserService
from infrastructure.ai.meetup_ai_service import MeetupAIService
from infrastructure.ai.orchestrator_service import OrchestratorService
from infrastructure.database.speed_dating_repository import SpeedDatingRepository
from infrastructure.database.meetup_repository import MeetupRepository
from infrastructure.database.conversation_log_repository import ConversationLogRepository
from infrastructure.database.community_repository import SupabaseCommunityRepository
from infrastructure.database.user_source_repository import SupabaseUserSourceRepository
from infrastructure.database.game_repository import SupabaseGameRepository

# Core services
from core.services import UserService, EventService, MatchingService
from core.services.community_service import CommunityService
from core.services.game_service import GameService
from core.services.observation_service import ObservationService
from core.services.community_pulse_service import CommunityPulseService
from core.services.bingo_service import BingoService
from core.services.story_service import StoryService


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
orchestrator_service = OrchestratorService()


# === ADDITIONAL REPOSITORIES ===
speed_dating_repo = SpeedDatingRepository()
meetup_repo = MeetupRepository()
conv_log_repo = ConversationLogRepository()
community_repo = SupabaseCommunityRepository()
user_source_repo = SupabaseUserSourceRepository()
game_repo = SupabaseGameRepository()


# === BUSINESS SERVICES ===
user_service = UserService(user_repo=user_repo, ai_service=ai_service)
event_service = EventService(event_repo=event_repo, user_repo=user_repo)
matching_service = MatchingService(
    match_repo=match_repo,
    event_repo=event_repo,
    ai_service=ai_service
)
community_service = CommunityService(
    community_repo=community_repo,
    user_repo=user_repo,
    bot=bot,
)
game_service = GameService(
    game_repo=game_repo,
    community_repo=community_repo,
    user_repo=user_repo,
)
observation_service = ObservationService(user_repo=user_repo)
pulse_service = CommunityPulseService(
    observation_service=observation_service,
    community_repo=community_repo,
    user_repo=user_repo,
)
bingo_service = BingoService(
    game_repo=game_repo,
    community_repo=community_repo,
    user_repo=user_repo,
)
story_service = StoryService()
