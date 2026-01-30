"""
Inline keyboards for Telegram bot.
Optimized for fast, friendly onboarding.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from core.domain.constants import INTERESTS, GOALS


# === ONBOARDING ===

def get_skip_or_voice_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for bio step - skip or encourage voice"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить →", callback_data="skip_bio")
    return builder.as_markup()


def get_quick_confirm_keyboard() -> InlineKeyboardMarkup:
    """Quick confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✓ Всё ок!", callback_data="confirm_profile")
    builder.button(text="Изменить", callback_data="edit_profile")
    builder.adjust(2)
    return builder.as_markup()


def get_interests_keyboard(selected: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting interests - compact and visual"""
    if selected is None:
        selected = []

    # Emoji mapping
    emoji_map = {
        "art": "🎨", "tech": "💻", "sport": "🏃", "books": "📚",
        "music": "🎵", "cinema": "🎬", "travel": "✈️", "cooking": "🍳",
        "gaming": "🎮", "business": "📈", "wellness": "🧘", "ecology": "🌱",
        "crypto": "💰", "startups": "🚀", "psychology": "🧠", "design": "🎨"
    }

    builder = InlineKeyboardBuilder()

    for key, data in INTERESTS.items():
        is_selected = key in selected
        emoji = emoji_map.get(key, "•")
        label = data.get("label_ru", key)

        # Short label for compact buttons
        short_label = label[:12] if len(label) > 12 else label

        if is_selected:
            display_text = f"✓ {emoji} {short_label}"
        else:
            display_text = f"{emoji} {short_label}"

        builder.button(text=display_text, callback_data=f"interest_{key}")

    builder.adjust(2)  # 2 buttons per row for readability

    # Done button - always visible, shows count
    count = len(selected)
    if count >= 1:
        builder.row(
            InlineKeyboardButton(
                text=f"Готово ({count}) →",
                callback_data="interests_done"
            )
        )

    return builder.as_markup()


def get_goals_keyboard(selected: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting goals - compact"""
    if selected is None:
        selected = []

    emoji_map = {
        "friends": "👥", "networking": "💼", "dating": "💕",
        "business": "🤝", "mentorship": "🎯", "creative": "🎨",
        "cofounders": "👬", "learning": "🎓"
    }

    builder = InlineKeyboardBuilder()

    for key, data in GOALS.items():
        is_selected = key in selected
        emoji = emoji_map.get(key, "•")
        label = data.get("label_ru", key)

        if is_selected:
            display_text = f"✓ {emoji} {label}"
        else:
            display_text = f"{emoji} {label}"

        builder.button(text=display_text, callback_data=f"goal_{key}")

    builder.adjust(2)

    count = len(selected)
    if count >= 1:
        builder.row(
            InlineKeyboardButton(
                text=f"Готово ({count}) →",
                callback_data="goals_done"
            )
        )

    return builder.as_markup()


# === EVENTS ===

def get_event_actions_keyboard(event_code: str) -> InlineKeyboardMarkup:
    """Event management keyboard (for admins)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Участники", callback_data=f"event_participants_{event_code}")
    builder.button(text="🔄 Матчинг", callback_data=f"event_match_{event_code}")
    builder.button(text="📊 Стата", callback_data=f"event_stats_{event_code}")
    builder.adjust(3)
    return builder.as_markup()


def get_join_event_keyboard(event_code: str) -> InlineKeyboardMarkup:
    """Join event keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✓ Присоединиться", callback_data=f"join_event_{event_code}")
    return builder.as_markup()


# === MATCHES ===

def get_match_keyboard(match_id: str) -> InlineKeyboardMarkup:
    """Match action keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Написать", callback_data=f"chat_match_{match_id}")
    builder.button(text="👤 Профиль", callback_data=f"view_profile_{match_id}")
    builder.adjust(2)
    return builder.as_markup()


def get_chat_keyboard(match_id: str) -> InlineKeyboardMarkup:
    """Chat keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="back_to_matches")
    return builder.as_markup()


# === MAIN MENU ===

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard - clean and simple"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Профиль", callback_data="my_profile")
    builder.button(text="🎉 Ивенты", callback_data="my_events")
    builder.button(text="💫 Матчи", callback_data="my_matches")
    builder.adjust(3)
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Back to menu button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="← Меню", callback_data="back_to_menu")
    return builder.as_markup()


# Legacy support
def get_skip_keyboard() -> InlineKeyboardMarkup:
    return get_skip_or_voice_keyboard()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    return get_quick_confirm_keyboard()
