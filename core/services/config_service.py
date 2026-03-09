"""
Config service with in-memory cache (60s TTL).
Falls back to hardcoded defaults if bot_config table is missing.
"""

import logging
import time

logger = logging.getLogger(__name__)

# Hardcoded defaults — used if DB is unreachable
_DEFAULT_BUTTONS = [
    {"id": "my_profile",     "emoji": "👤", "label_en": "Profile",        "label_ru": "Профиль",              "enabled": True, "locked": True,  "order": 0},
    {"id": "my_events",      "emoji": "🎉", "label_en": "Events",         "label_ru": "Ивенты",               "enabled": True, "locked": False, "order": 1},
    {"id": "my_matches",     "emoji": "💫", "label_en": "Matches",        "label_ru": "Матчи",                "enabled": True, "locked": True,  "order": 2},
    {"id": "my_activities",  "emoji": "🎯", "label_en": "My Activities",  "label_ru": "Мои активности",       "enabled": True, "locked": False, "order": 3},
    {"id": "my_invitations", "emoji": "📩", "label_en": "Invitations",    "label_ru": "Приглашения",          "enabled": True, "locked": False, "order": 4},
    {"id": "vibe_new",       "emoji": "🔮", "label_en": "Check Our Vibe", "label_ru": "Проверь совместимость", "enabled": True, "locked": False, "order": 5},
    {"id": "giveaway_info",  "emoji": "🎁", "label_en": "Giveaway",       "label_ru": "Giveaway",             "enabled": True, "locked": False, "order": 6},
]

CACHE_TTL = 60  # seconds


class ConfigService:
    def __init__(self, config_repo):
        self._repo = config_repo
        self._cache = None
        self._cache_time = 0

    async def get_menu_buttons(self) -> list[dict]:
        """Return all menu buttons sorted by order. Cached for 60s. Filtering by enabled/locked is done by the keyboard builder."""
        now = time.time()
        if self._cache is not None and (now - self._cache_time) < CACHE_TTL:
            return self._cache

        config = await self._repo.get_menu_buttons()
        if config and "buttons" in config:
            buttons = sorted(config["buttons"], key=lambda b: b.get("order", 0))
        else:
            buttons = _DEFAULT_BUTTONS

        self._cache = buttons
        self._cache_time = now
        return buttons

    def invalidate_cache(self):
        """Force next call to re-read from DB."""
        self._cache = None
        self._cache_time = 0
