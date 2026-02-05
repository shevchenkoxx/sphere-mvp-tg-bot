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

    # Row 1: Main actions
    builder.button(text="👥 Participants", callback_data=f"event_participants_{event_code}")
    builder.button(text="🔄 Matching", callback_data=f"event_match_{event_code}")
    builder.button(text="📊 Stats", callback_data=f"event_stats_{event_code}")

    # Row 2: Info management
    builder.button(text="ℹ️ Info", callback_data=f"event_info_{event_code}")
    builder.button(text="🔗 Import URL", callback_data=f"event_import_{event_code}")
    builder.button(text="✏️ Edit", callback_data=f"event_edit_{event_code}")

    # Row 3: Broadcast
    builder.button(text="📢 Broadcast", callback_data=f"event_broadcast_{event_code}")

    builder.adjust(3, 3, 1)
    return builder.as_markup()


def get_event_info_keyboard(event_code: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for event info view"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Back", callback_data=f"event_back_{event_code}")
    builder.button(text="📋 Full Schedule", callback_data=f"event_schedule_{event_code}")
    builder.button(text="🎤 All Speakers", callback_data=f"event_speakers_{event_code}")
    builder.adjust(1, 2)
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
    """Match action keyboard with pagination and feedback"""
    builder = InlineKeyboardBuilder()

    # Row 1: Action buttons (Chat + Profile)
    chat_text = "💬 Chat" if lang == "en" else "💬 Написать"
    profile_text = "👤 Profile" if lang == "en" else "👤 Профиль"
    builder.button(text=chat_text, callback_data=f"chat_match_{match_id}")
    builder.button(text=profile_text, callback_data=f"view_profile_{match_id}")
    builder.adjust(2)

    # Row 2: AI Speed Dating button
    speed_text = "⚡ AI Speed Dating" if lang == "en" else "⚡ AI Знакомство"
    builder.row(InlineKeyboardButton(text=speed_text, callback_data=f"speed_dating_{match_id}"))

    # Row 3: Feedback buttons
    feedback_label = "Match quality:" if lang == "en" else "Качество матча:"
    builder.row(
        InlineKeyboardButton(text=f"{feedback_label} 👍", callback_data=f"feedback_good_{match_id}"),
        InlineKeyboardButton(text="👎", callback_data=f"feedback_bad_{match_id}")
    )

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


def get_events_keyboard(current_mode: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Events screen with mode toggle button and join event option"""
    builder = InlineKeyboardBuilder()

    # Join event button
    if lang == "ru":
        builder.button(text="📲 Ввести код ивента", callback_data="enter_event_code")
    else:
        builder.button(text="📲 Enter event code", callback_data="enter_event_code")

    # Toggle button - shows what you can switch TO
    if current_mode == "event":
        if lang == "ru":
            builder.button(text="🏙️ Переключить на Sphere City", callback_data="toggle_matching_mode")
        else:
            builder.button(text="🏙️ Switch to Sphere City", callback_data="toggle_matching_mode")
    else:
        if lang == "ru":
            builder.button(text="🎉 Переключить на Event", callback_data="toggle_matching_mode")
        else:
            builder.button(text="🎉 Switch to Event mode", callback_data="toggle_matching_mode")

    # Back to menu
    builder.button(text="← Menu" if lang == "en" else "← Меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


# === PROFILE EDITING ===

def get_profile_with_edit_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Profile view with edit button"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="✏️ Редактировать", callback_data="edit_my_profile")
        builder.button(text="← Меню", callback_data="back_to_menu")
    else:
        builder.button(text="✏️ Edit", callback_data="edit_my_profile")
        builder.button(text="← Menu", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_edit_mode_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Choose edit mode: quick or conversational"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="📝 Выбрать поле", callback_data="edit_mode_quick")
        builder.button(text="💬 Описать изменения", callback_data="edit_mode_chat")
        builder.button(text="← Назад", callback_data="my_profile")
    else:
        builder.button(text="📝 Edit field", callback_data="edit_mode_quick")
        builder.button(text="💬 Describe changes", callback_data="edit_mode_chat")
        builder.button(text="← Back", callback_data="my_profile")
    builder.adjust(1)
    return builder.as_markup()


def get_edit_field_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Choose which field to edit"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="📝 О себе", callback_data="edit_field_bio")
        builder.button(text="🔍 Ищу", callback_data="edit_field_looking_for")
        builder.button(text="💡 Могу помочь", callback_data="edit_field_can_help")
        builder.button(text="#️⃣ Интересы", callback_data="edit_field_interests")
        builder.button(text="🎯 Цели", callback_data="edit_field_goals")
        builder.button(text="📸 Фото", callback_data="edit_field_photo")
        builder.button(text="← Назад", callback_data="edit_my_profile")
    else:
        builder.button(text="📝 About me", callback_data="edit_field_bio")
        builder.button(text="🔍 Looking for", callback_data="edit_field_looking_for")
        builder.button(text="💡 Can help with", callback_data="edit_field_can_help")
        builder.button(text="#️⃣ Interests", callback_data="edit_field_interests")
        builder.button(text="🎯 Goals", callback_data="edit_field_goals")
        builder.button(text="📸 Photo", callback_data="edit_field_photo")
        builder.button(text="← Back", callback_data="edit_my_profile")
    builder.adjust(2)
    return builder.as_markup()


def get_edit_confirm_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Confirm or cancel edit"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="✅ Подтвердить", callback_data="edit_confirm")
        builder.button(text="❌ Отмена", callback_data="edit_cancel")
    else:
        builder.button(text="✅ Confirm", callback_data="edit_confirm")
        builder.button(text="❌ Cancel", callback_data="edit_cancel")
    builder.adjust(2)
    return builder.as_markup()


def get_edit_continue_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Continue editing or finish"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="✏️ Продолжить", callback_data="edit_my_profile")
        builder.button(text="✅ Готово", callback_data="my_profile")
    else:
        builder.button(text="✏️ Continue editing", callback_data="edit_my_profile")
        builder.button(text="✅ Done", callback_data="my_profile")
    builder.adjust(2)
    return builder.as_markup()


# === SPHERE CITY ===

# Cities available in MVP
SPHERE_CITIES = {
    "moscow": {"en": "Moscow", "ru": "Москва"},
    "kyiv": {"en": "Kyiv", "ru": "Киев"},
    "dubai": {"en": "Dubai", "ru": "Дубай"},
    "berlin": {"en": "Berlin", "ru": "Берлин"},
    "london": {"en": "London", "ru": "Лондон"},
    "new_york": {"en": "New York", "ru": "Нью-Йорк"},
    "tbilisi": {"en": "Tbilisi", "ru": "Тбилиси"},
    "yerevan": {"en": "Yerevan", "ru": "Ереван"},
}


def get_city_picker_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """City selection keyboard for Sphere City"""
    builder = InlineKeyboardBuilder()

    for city_key, names in SPHERE_CITIES.items():
        city_name = names.get(lang, names["en"])
        builder.button(text=city_name, callback_data=f"city_select_{city_key}")

    # Other option for custom input
    other_text = "🌍 Other..." if lang == "en" else "🌍 Другой..."
    builder.button(text=other_text, callback_data="city_select_other")

    # Back button
    back_text = "← Back" if lang == "en" else "← Назад"
    builder.button(text=back_text, callback_data="back_to_menu")

    builder.adjust(2)  # 2 cities per row
    return builder.as_markup()


def get_sphere_city_menu_keyboard(has_matches: bool = True, lang: str = "en") -> InlineKeyboardMarkup:
    """Sphere City main menu"""
    builder = InlineKeyboardBuilder()

    if has_matches:
        view_text = "👀 View matches" if lang == "en" else "👀 Посмотреть матчи"
        builder.button(text=view_text, callback_data="sphere_city_matches")

    change_city = "📍 Change city" if lang == "en" else "📍 Сменить город"
    builder.button(text=change_city, callback_data="sphere_city_change")

    back_text = "← Menu" if lang == "en" else "← Меню"
    builder.button(text=back_text, callback_data="back_to_menu")

    builder.adjust(1)
    return builder.as_markup()


def get_matches_menu_keyboard(
    has_event: bool = False,
    event_name: str = None,
    lang: str = "en"
) -> InlineKeyboardMarkup:
    """Matches menu with event and Sphere City options"""
    builder = InlineKeyboardBuilder()

    if has_event and event_name:
        event_text = f"🎉 {event_name}"
        builder.button(text=event_text, callback_data="event_matches")

    city_text = "🏙️ Sphere City" if lang == "en" else "🏙️ Sphere City"
    builder.button(text=city_text, callback_data="sphere_city")

    back_text = "← Menu" if lang == "en" else "← Меню"
    builder.button(text=back_text, callback_data="back_to_menu")

    builder.adjust(1)
    return builder.as_markup()


# === AI SPEED DATING ===

def get_speed_dating_result_keyboard(match_id: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for speed dating preview result"""
    builder = InlineKeyboardBuilder()

    # Row 1: Main actions
    chat_text = "💬 Write" if lang == "en" else "💬 Написать"
    regen_text = "🔄 Again" if lang == "en" else "🔄 Ещё раз"
    builder.button(text=chat_text, callback_data=f"chat_match_{match_id}")
    builder.button(text=regen_text, callback_data=f"speed_dating_regen_{match_id}")
    builder.adjust(2)

    # Row 2: Back to match
    back_text = "← Back to match" if lang == "en" else "← К матчу"
    builder.row(InlineKeyboardButton(text=back_text, callback_data="back_to_matches"))

    return builder.as_markup()


# === PERSONALIZATION ===

def get_connection_mode_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for selecting connection mode in personalization flow"""
    builder = InlineKeyboardBuilder()

    if lang == "ru":
        builder.button(text="🎯 Получить помощь/совет", callback_data="conn_mode_receive_help")
        builder.button(text="💪 Помочь другим/поделиться", callback_data="conn_mode_give_help")
        builder.button(text="🔄 Обменяться опытом", callback_data="conn_mode_exchange")
    else:
        builder.button(text="🎯 Get help/advice", callback_data="conn_mode_receive_help")
        builder.button(text="💪 Help others/share", callback_data="conn_mode_give_help")
        builder.button(text="🔄 Exchange experience", callback_data="conn_mode_exchange")

    builder.adjust(1)
    return builder.as_markup()


def get_adaptive_buttons_keyboard(buttons: list, lang: str = "en") -> InlineKeyboardMarkup:
    """Create keyboard from LLM-generated personalized buttons"""
    builder = InlineKeyboardBuilder()

    for i, btn_text in enumerate(buttons[:3]):  # Max 3 buttons
        builder.button(text=btn_text, callback_data=f"adaptive_btn_{i}")

    builder.adjust(1)
    return builder.as_markup()


def get_skip_personalization_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Skip button for personalization steps"""
    builder = InlineKeyboardBuilder()
    text = "⏩ Skip" if lang == "en" else "⏩ Пропустить"
    builder.button(text=text, callback_data="skip_personalization_step")
    return builder.as_markup()


# === MATCHES PHOTO REQUEST ===

def get_matches_photo_keyboard(lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for photo request when opening matches"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="⏩ Позже", callback_data="skip_matches_photo")
    else:
        builder.button(text="⏩ Later", callback_data="skip_matches_photo")
    return builder.as_markup()


# === FEEDBACK ===

def get_feedback_keyboard(match_id: str, lang: str = "en") -> InlineKeyboardMarkup:
    """Keyboard for match feedback"""
    builder = InlineKeyboardBuilder()
    if lang == "ru":
        builder.button(text="👍", callback_data=f"feedback_good_{match_id}")
        builder.button(text="👎", callback_data=f"feedback_bad_{match_id}")
    else:
        builder.button(text="👍", callback_data=f"feedback_good_{match_id}")
        builder.button(text="👎", callback_data=f"feedback_bad_{match_id}")
    builder.adjust(2)
    return builder.as_markup()


# Legacy support
def get_skip_keyboard() -> InlineKeyboardMarkup:
    return get_skip_or_voice_keyboard()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    return get_quick_confirm_keyboard()
