"""
Centralized language detection for all handlers.

Currently hardcoded to English. When multi-language support is needed,
update this single file to detect from Telegram language settings.
"""

from aiogram.types import Message, CallbackQuery
from typing import Union


def detect_lang(source: Union[Message, CallbackQuery, None] = None) -> str:
    """
    Detect user language. Currently always returns English.

    To enable real detection, uncomment the block below.

    Args:
        source: Message or CallbackQuery from Telegram (unused for now).

    Returns:
        Language code ("en" or "ru").
    """
    # TODO: Enable real detection when multi-language is needed:
    # if source:
    #     user = source.from_user if hasattr(source, 'from_user') else None
    #     if user and user.language_code and user.language_code.startswith("ru"):
    #         return "ru"
    return "en"


def get_language_name(lang: str) -> str:
    """Get full language name for LLM prompts."""
    return "Russian" if lang == "ru" else "English"
