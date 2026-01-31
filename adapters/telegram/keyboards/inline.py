"""
Inline keyboards for Telegram bot.
Optimized for fast, friendly onboarding.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from core.domain.constants import INTERESTS, GOALS


# === ONBOARDING ===

def get_skip_or_voice_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for bio step - skip or encourage voice"""
    builder = InlineKeyboardBuilder()
    text = "Skip →" if lang == "en" else "Пропустить →"
    builder.button(text=text, callback_data="skip_bio")
    return builder.as_markup()


def get_quick_confirm_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Quick confirmation keyboard"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="✓ Всё ок!", callback_data="confirm_profile")
        builder.button(text="Изменить", callback_data="edit_profile")
    else:
        builder.button(text="✓ Looks good!", callback_data="confirm_profile")
        builder.button(text="Edit", callback_data="edit_profile")
    builder.adjust(2)
    return builder.as_markup()


def get_interests_keyboard(selected: List[str] = None, lang: str = "en") -> InlineKeyboardMarkup:
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
    label_key = "label_ru" if lang == "ru" else "label_en"

    for key, data in INTERESTS.items():
        is_selected = key in selected
        emoji = emoji_map.get(key, "•")
        label = data.get(label_key, data.get("label_en", key))

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
        done_text = f"Done ({count}) →" if lang == "en" else f"Готово ({count}) →"
        builder.row(
            InlineKeyboardButton(
                text=done_text,
                callback_data="interests_done"
            )
        )

    return builder.as_markup()


def get_goals_keyboard(selected: List[str] = None, lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for selecting goals - compact"""
    if selected is None:
        selected = []

    emoji_map = {
        "friends": "👥", "networking": "💼", "dating": "💕",
        "business": "🤝", "mentorship": "🎯", "creative": "🎨",
        "cofounders": "👬", "learning": "🎓"
    }

    builder = InlineKeyboardBuilder()
    label_key = "label_ru" if lang == "ru" else "label_en"

    for key, data in GOALS.items():
        is_selected = key in selected
        emoji = emoji_map.get(key, "•")
        label = data.get(label_key, data.get("label_en", key))

        if is_selected:
            display_text = f"✓ {emoji} {label}"
        else:
            display_text = f"{emoji} {label}"

        builder.button(text=display_text, callback_data=f"goal_{key}")

    builder.adjust(2)

    count = len(selected)
    if count >= 1:
        done_text = f"Done ({count}) →" if lang == "en" else f"Готово ({count}) →"
        builder.row(
            InlineKeyboardButton(
                text=done_text,
                callback_data="goals_done"
            )
        )

    return builder.as_markup()


# === EVENTS ===

def get_event_actions_keyboard(event_code: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Event management keyboard (for admins)"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="👥 Участники", callback_data=f"event_participants_{event_code}")
        builder.button(text="🔄 Матчинг", callback_data=f"event_match_{event_code}")
        builder.button(text="📊 Стата", callback_data=f"event_stats_{event_code}")
    else:
        builder.button(text="👥 Participants", callback_data=f"event_participants_{event_code}")
        builder.button(text="🔄 Matching", callback_data=f"event_match_{event_code}")
        builder.button(text="📊 Stats", callback_data=f"event_stats_{event_code}")
    builder.adjust(3)
    return builder.as_markup()


def get_join_event_keyboard(event_code: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Join event keyboard"""
    builder = InlineKeyboardBuilder()
    text = "✓ Join" if lang == "en" else "✓ Присоединиться"
    builder.button(text=text, callback_data=f"join_event_{event_code}")
    return builder.as_markup()


# === MATCHES ===

def get_match_keyboard(
    match_id: str,
    current_index: int = 0,
    total_matches: int = 1,
    lang: str = "en"
) -> InlineKeyboardMarkup:
    """Match action keyboard with pagination"""
    builder = InlineKeyboardBuilder()

    # Action buttons
    chat_text = "💬 Chat" if lang == "en" else "💬 Написать"
    profile_text = "👤 Profile" if lang == "en" else "👤 Профиль"
    builder.button(text=chat_text, callback_data=f"chat_match_{match_id}")
    builder.button(text=profile_text, callback_data=f"view_profile_{match_id}")
    builder.adjust(2)

    # Pagination buttons (if more than 1 match)
    if total_matches > 1:
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"match_prev_{current_index}"))
        nav_row.append(InlineKeyboardButton(text=f"{current_index + 1}/{total_matches}", callback_data="match_counter"))
        if current_index < total_matches - 1:
            nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"match_next_{current_index}"))
        builder.row(*nav_row)

    # Back to menu button
    menu_text = "← Menu" if lang == "en" else "← Меню"
    builder.row(InlineKeyboardButton(text=menu_text, callback_data="back_to_menu"))

    return builder.as_markup()


def get_chat_keyboard(match_id: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Chat keyboard"""
    builder = InlineKeyboardBuilder()
    back_text = "← Back" if lang == "en" else "← Назад"
    builder.button(text=back_text, callback_data="back_to_matches")
    return builder.as_markup()


def get_profile_view_keyboard(match_id: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for viewing match profile - back to match and menu"""
    builder = InlineKeyboardBuilder()
    chat_text = "💬 Chat" if lang == "en" else "💬 Написать"
    back_text = "← Back" if lang == "en" else "← Назад"
    menu_text = "← Menu" if lang == "en" else "← Меню"
    builder.button(text=chat_text, callback_data=f"chat_match_{match_id}")
    builder.button(text=back_text, callback_data="back_to_matches")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=menu_text, callback_data="back_to_menu"))
    return builder.as_markup()


# === MAIN MENU ===

def get_main_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Main menu keyboard - clean and simple"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="👤 Профиль", callback_data="my_profile")
        builder.button(text="🎉 Ивенты", callback_data="my_events")
        builder.button(text="💫 Матчи", callback_data="my_matches")
    else:
        builder.button(text="👤 Profile", callback_data="my_profile")
        builder.button(text="🎉 Events", callback_data="my_events")
        builder.button(text="💫 Matches", callback_data="my_matches")
    builder.adjust(3)
    return builder.as_markup()


def get_back_to_menu_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Back to menu button"""
    builder = InlineKeyboardBuilder()
    builder.button(text="← Menu" if lang == "en" else "← Меню", callback_data="back_to_menu")
    return builder.as_markup()


# Legacy support
def get_skip_keyboard() -> InlineKeyboardMarkup:
    return get_skip_or_voice_keyboard()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    return get_quick_confirm_keyboard()
