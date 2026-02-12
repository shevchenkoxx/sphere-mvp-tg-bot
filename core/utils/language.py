"""
Centralized language detection for all handlers.

Default: English. Auto-switches to Russian if user's Telegram language is "ru".
"""

from aiogram.types import Message, CallbackQuery
from typing import Union


def detect_lang(source: Union[Message, CallbackQuery, None] = None) -> str:
    """
    Detect user language from Telegram settings.

    Default: English ("en").
    Returns "ru" only if user's Telegram language_code starts with "ru".

    Args:
        source: Message or CallbackQuery from Telegram.

    Returns:
        Language code ("en" or "ru").
    """
    if source:
        user = source.from_user if hasattr(source, 'from_user') else None
        if user and user.language_code and user.language_code.startswith("ru"):
            return "ru"
    return "en"


def get_language_name(lang: str) -> str:
    """Get full language name for LLM prompts."""
    return "Russian" if lang == "ru" else "English"
