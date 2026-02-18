"""
Middleware for Telegram bot.

- ThrottlingMiddleware: rate limiting
- ConversationLoggingMiddleware: logs all incoming messages/callbacks
- ContentTypeMiddleware: detects content type and injects into handler data
"""

import asyncio
import time
import logging
from typing import Any, Awaitable, Callable, Dict, Optional
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, ContentType
from aiogram.fsm.context import FSMContext

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


# ---------------------------------------------------------------------------
# Content type detection helpers
# ---------------------------------------------------------------------------

def detect_content_type(message: Message) -> str:
    """Return a simple string label for the message content type."""
    if message.voice:
        return "voice"
    if message.photo:
        return "photo"
    if message.document:
        return "document"
    if message.video:
        return "video"
    if message.video_note:
        return "video_note"
    if message.sticker:
        return "sticker"
    if message.animation:
        return "animation"
    if message.audio:
        return "audio"
    if message.contact:
        return "contact"
    if message.location:
        return "location"
    if message.text:
        return "text"
    return "other"


# ---------------------------------------------------------------------------
# Conversation Logging Middleware
# ---------------------------------------------------------------------------

class ConversationLoggingMiddleware(BaseMiddleware):
    """
    Logs every incoming Message and CallbackQuery to conversation_logs.
    Fire-and-forget — never blocks the handler pipeline.
    """

    def __init__(self, conv_log_repo):
        self.repo = conv_log_repo

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Log in background, then pass through
        asyncio.create_task(self._log(event, data))
        return await handler(event, data)

    async def _log(self, event: TelegramObject, data: Dict[str, Any]):
        try:
            fsm_state = None
            state: Optional[FSMContext] = data.get("state")
            if state:
                try:
                    raw = await state.get_state()
                    fsm_state = raw
                except Exception:
                    pass

            if isinstance(event, Message) and event.from_user:
                msg_type = detect_content_type(event)
                content = event.text or event.caption
                await self.repo.log_message(
                    telegram_user_id=event.from_user.id,
                    direction="in",
                    message_type=msg_type,
                    content=content,
                    telegram_message_id=event.message_id,
                    has_media=msg_type not in ("text", "other", "contact", "location"),
                    fsm_state=fsm_state,
                )

            elif isinstance(event, CallbackQuery) and event.from_user:
                await self.repo.log_message(
                    telegram_user_id=event.from_user.id,
                    direction="in",
                    message_type="callback",
                    callback_data=event.data,
                    fsm_state=fsm_state,
                )
        except Exception as e:
            logger.debug(f"Conv log middleware error: {e}")


# ---------------------------------------------------------------------------
# Content Type Middleware
# ---------------------------------------------------------------------------

class ContentTypeMiddleware(BaseMiddleware):
    """
    Detects the content type of incoming Messages and injects
    `data["content_type"]` (str) so handlers can branch on it
    without manual checks.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            data["content_type"] = detect_content_type(event)
        return await handler(event, data)
