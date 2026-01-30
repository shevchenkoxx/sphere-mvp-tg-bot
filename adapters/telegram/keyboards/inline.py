"""
Inline keyboards for Telegram bot.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from core.domain.constants import INTERESTS, GOALS


# === ONBOARDING ===

def get_skip_keyboard() -> InlineKeyboardMarkup:
    """Keyboard with skip button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить", callback_data="skip_step")
    return builder.as_markup()


def get_interests_keyboard(selected: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting interests"""
    if selected is None:
        selected = []

    builder = InlineKeyboardBuilder()

    for key, data in INTERESTS.items():
        is_selected = key in selected
        emoji = data.get("emoji", "")
        # Map emoji names to actual emoji (simplified)
        emoji_map = {
            "art": "\U0001F3A8", "computer": "\U0001F4BB", "running": "\U0001F3C3",
            "books": "\U0001F4DA", "musical_note": "\U0001F3B5", "clapper": "\U0001F3AC",
            "airplane": "\U00002708", "cooking": "\U0001F373", "video_game": "\U0001F3AE",
            "chart_increasing": "\U0001F4C8", "person_in_lotus_position": "\U0001F9D8",
            "seedling": "\U0001F331", "coin": "\U0001FA99", "rocket": "\U0001F680",
            "brain": "\U0001F9E0", "palette": "\U0001F3A8"
        }
        emoji_char = emoji_map.get(emoji, "")
        label = data.get("label_ru", key)

        if is_selected:
            display_text = f"[x] {emoji_char} {label}"
        else:
            display_text = f"{emoji_char} {label}"

        builder.button(text=display_text, callback_data=f"interest_{key}")

    builder.adjust(2)  # 2 buttons per row

    # Confirm button if at least 1 selected
    if selected:
        builder.row(
            InlineKeyboardButton(
                text=f"Готово ({len(selected)}/5)",
                callback_data="interests_done"
            )
        )

    return builder.as_markup()


def get_goals_keyboard(selected: List[str] = None) -> InlineKeyboardMarkup:
    """Keyboard for selecting goals"""
    if selected is None:
        selected = []

    builder = InlineKeyboardBuilder()

    for key, data in GOALS.items():
        is_selected = key in selected
        emoji = data.get("emoji", "")
        emoji_map = {
            "people_holding_hands": "\U0001F46B", "briefcase": "\U0001F4BC",
            "two_hearts": "\U0001F495", "handshake": "\U0001F91D",
            "direct_hit": "\U0001F3AF", "art": "\U0001F3A8",
            "busts_in_silhouette": "\U0001F465", "graduation_cap": "\U0001F393"
        }
        emoji_char = emoji_map.get(emoji, "")
        label = data.get("label_ru", key)

        if is_selected:
            display_text = f"[x] {emoji_char} {label}"
        else:
            display_text = f"{emoji_char} {label}"

        builder.button(text=display_text, callback_data=f"goal_{key}")

    builder.adjust(2)

    if selected:
        builder.row(
            InlineKeyboardButton(
                text=f"Готово ({len(selected)}/3)",
                callback_data="goals_done"
            )
        )

    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Profile confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Всё верно!", callback_data="confirm_profile")
    builder.button(text="Изменить", callback_data="edit_profile")
    builder.adjust(2)
    return builder.as_markup()


# === EVENTS ===

def get_event_actions_keyboard(event_code: str) -> InlineKeyboardMarkup:
    """Event management keyboard (for admins)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Участники", callback_data=f"event_participants_{event_code}")
    builder.button(text="Запустить матчинг", callback_data=f"event_match_{event_code}")
    builder.button(text="Статистика", callback_data=f"event_stats_{event_code}")
    builder.adjust(2)
    return builder.as_markup()


def get_join_event_keyboard(event_code: str) -> InlineKeyboardMarkup:
    """Join event keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Присоединиться", callback_data=f"join_event_{event_code}")
    return builder.as_markup()


# === MATCHES ===

def get_match_keyboard(match_id: str) -> InlineKeyboardMarkup:
    """Match action keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Написать", callback_data=f"chat_match_{match_id}")
    builder.button(text="Профиль", callback_data=f"view_profile_{match_id}")
    builder.adjust(2)
    return builder.as_markup()


def get_chat_keyboard(match_id: str) -> InlineKeyboardMarkup:
    """Chat keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="К матчам", callback_data="back_to_matches")
    return builder.as_markup()


# === MAIN MENU ===

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Мой профиль", callback_data="my_profile")
    builder.button(text="Мои ивенты", callback_data="my_events")
    builder.button(text="Мои матчи", callback_data="my_matches")
    builder.adjust(2)
    return builder.as_markup()


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Back to menu button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="< Назад в меню", callback_data="back_to_menu")
    return builder.as_markup()
