"""
Rate limiting middleware for Telegram bot.

Prevents users from spamming commands and wasting API calls.
Uses in-memory storage with per-user tracking.
"""

import time
import logging
from typing import Any, Awaitable, Callable, Dict
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from core.domain.constants import (
    RATE_LIMIT_COMMANDS,
    RATE_LIMIT_MATCHING,
    RATE_LIMIT_INTERVAL_SECONDS,
)

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    """
    Simple rate limiter: tracks request timestamps per user.
    Drops requests that exceed the limit within the interval.
    """

    def __init__(
        self,
        default_limit: int = RATE_LIMIT_COMMANDS,
        interval: int = RATE_LIMIT_INTERVAL_SECONDS,
    ):
        self.default_limit = default_limit
        self.interval = interval
        # {user_id: [timestamp, timestamp, ...]}
        self._requests: Dict[int, list] = defaultdict(list)
        # Commands with stricter limits
        self._strict_commands = {
            "/find_matches": RATE_LIMIT_MATCHING,
            "/matches": RATE_LIMIT_MATCHING,
            "retry_matching": RATE_LIMIT_MATCHING,
        }

    def _get_limit(self, event: TelegramObject) -> int:
        """Get rate limit for this specific event."""
        if isinstance(event, Message) and event.text:
            cmd = event.text.split()[0].split("@")[0]
            if cmd in self._strict_commands:
                return self._strict_commands[cmd]
        elif isinstance(event, CallbackQuery) and event.data:
            if event.data in self._strict_commands:
                return self._strict_commands[event.data]
        return self.default_limit

    def _cleanup(self, user_id: int, now: float):
        """Remove expired timestamps."""
        cutoff = now - self.interval
        self._requests[user_id] = [
            ts for ts in self._requests[user_id] if ts > cutoff
        ]

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Extract user_id
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)

        user_id = user.id
        now = time.monotonic()
        self._cleanup(user_id, now)

        limit = self._get_limit(event)
        if len(self._requests[user_id]) >= limit:
            logger.warning(f"Rate limit hit for user {user_id} (limit={limit})")
            # Silently drop for callbacks, send warning for messages
            if isinstance(event, Message):
                await event.answer(
                    "You're sending too many requests. Please wait a moment."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "Too many requests. Please wait.",
                    show_alert=False,
                )
            return  # Drop the request

        self._requests[user_id].append(now)
        return await handler(event, data)
