"""
i18n module — dict-based translation with fallback to English.
New onboarding uses this from day 1. Old handlers can migrate gradually.
"""

from locales.en import EN_STRINGS
from locales.ru import RU_STRINGS

_STRINGS = {"en": EN_STRINGS, "ru": RU_STRINGS}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated string. Falls back to EN if key missing."""
    strings = _STRINGS.get(lang, _STRINGS["en"])
    text = strings.get(key, _STRINGS["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


def add_language(code: str, strings: dict):
    """Register a new language at runtime."""
    _STRINGS[code] = strings
