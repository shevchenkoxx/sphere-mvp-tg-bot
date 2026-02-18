"""
Outgoing message logger — wraps Bot.__call__ to capture all API responses.
Fire-and-forget, never blocks or crashes the bot.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# API methods that carry user-visible content
_CONTENT_METHODS = {
    "SendMessage", "SendPhoto", "SendVoice", "SendDocument",
    "SendSticker", "SendAnimation", "SendVideo", "SendVideoNote",
    "EditMessageText", "EditMessageCaption",
}

# Methods to skip entirely (noisy, no content)
_SKIP_METHODS = {
    "DeleteMessage", "AnswerCallbackQuery", "GetUpdates",
    "DeleteWebhook", "GetMe", "GetFile", "SetMyCommands",
    "SetChatMenuButton", "GetChat", "GetChatMember",
}


def install_outgoing_logger(bot, conv_log_repo):
    """
    Monkey-patch bot.__call__ to log outgoing API calls.
    Call once at startup.
    """
    original_call = bot.__class__.__call__

    async def _logging_call(self, method, request_timeout=None):
        # Execute the original call first
        result = await original_call(self, method, request_timeout)

        method_name = type(method).__name__
        if method_name in _SKIP_METHODS:
            return result

        if method_name in _CONTENT_METHODS:
            asyncio.create_task(_log_outgoing(conv_log_repo, method, method_name))

        return result

    bot.__class__.__call__ = _logging_call


async def _log_outgoing(conv_log_repo, method, method_name: str):
    """Extract fields from the API method and log."""
    try:
        chat_id = getattr(method, "chat_id", None)
        if chat_id is None:
            return

        content: Optional[str] = None
        msg_type = "text"
        has_media = False

        if method_name in ("SendMessage", "EditMessageText"):
            content = getattr(method, "text", None)
        elif method_name == "EditMessageCaption":
            content = getattr(method, "caption", None)
        elif method_name == "SendPhoto":
            content = getattr(method, "caption", None)
            msg_type = "photo"
            has_media = True
        elif method_name == "SendVoice":
            content = getattr(method, "caption", None)
            msg_type = "voice"
            has_media = True
        elif method_name == "SendDocument":
            content = getattr(method, "caption", None)
            msg_type = "document"
            has_media = True
        elif method_name == "SendSticker":
            msg_type = "sticker"
            has_media = True
        elif method_name in ("SendAnimation", "SendVideo", "SendVideoNote"):
            content = getattr(method, "caption", None)
            msg_type = "video" if "Video" in method_name else "animation"
            has_media = True

        await conv_log_repo.log_message(
            telegram_user_id=int(chat_id),
            direction="out",
            message_type=msg_type,
            content=content,
            api_method=method_name,
            has_media=has_media,
        )
    except Exception as e:
        logger.debug(f"Outgoing log error: {e}")
