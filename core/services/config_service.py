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

_DEFAULT_ONBOARDING_STEPS = [
    {"id": "photo_request",    "label_en": "Photo Request",    "label_ru": "Запрос фото",       "enabled": True, "locked": False},
    {"id": "activity_picker",  "label_en": "Activity Picker",  "label_ru": "Выбор активностей", "enabled": True, "locked": False},
    {"id": "connection_mode",  "label_en": "Connection Mode",  "label_ru": "Режим связей",      "enabled": True, "locked": False},
    {"id": "adaptive_buttons", "label_en": "Adaptive Buttons", "label_ru": "Адаптивные кнопки", "enabled": True, "locked": False},
]

CACHE_TTL = 60  # seconds


class ConfigService:
    def __init__(self, config_repo):
        self._repo = config_repo
        self._menu_cache = None
        self._menu_cache_time = 0
        self._steps_cache = None
        self._steps_cache_time = 0

    async def get_menu_buttons(self) -> list[dict]:
        """Return all menu buttons sorted by order. Cached for 60s."""
        now = time.time()
        if self._menu_cache is not None and (now - self._menu_cache_time) < CACHE_TTL:
            return self._menu_cache

        config = await self._repo.get_menu_buttons()
        if config and "buttons" in config:
            buttons = sorted(config["buttons"], key=lambda b: b.get("order", 0))
        else:
            buttons = _DEFAULT_BUTTONS

        self._menu_cache = buttons
        self._menu_cache_time = now
        return buttons

    async def get_onboarding_steps(self) -> list[dict]:
        """Return onboarding steps config. Cached for 60s."""
        now = time.time()
        if self._steps_cache is not None and (now - self._steps_cache_time) < CACHE_TTL:
            return self._steps_cache

        config = await self._repo.get_onboarding_steps()
        if config and "steps" in config:
            steps = config["steps"]
        else:
            steps = _DEFAULT_ONBOARDING_STEPS

        self._steps_cache = steps
        self._steps_cache_time = now
        return steps

    async def is_step_enabled(self, step_id: str) -> bool:
        """Check if a specific onboarding step is enabled."""
        steps = await self.get_onboarding_steps()
        for step in steps:
            if step["id"] == step_id:
                return step.get("enabled", True)
        # Unknown step — default to enabled
        return True

    def invalidate_cache(self):
        """Force next call to re-read from DB."""
        self._menu_cache = None
        self._menu_cache_time = 0
        self._steps_cache = None
        self._steps_cache_time = 0
