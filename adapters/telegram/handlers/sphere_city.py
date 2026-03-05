"""
Sphere City Handler - City-based matching outside events.

Flow:
1. User clicks "🏙️ Sphere City" in matches menu
2. If no city_current → show city picker
3. Show onboarding message explaining Sphere City
4. Show city-based matches
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.domain.models import MessagePlatform
from adapters.telegram.loader import user_service, matching_service
from adapters.telegram.keyboards.inline import (
    get_city_picker_keyboard,
    get_sphere_city_menu_keyboard,
    get_back_to_menu_keyboard,
    get_main_menu_keyboard,
    SPHERE_CITIES,
)

from core.utils.language import detect_lang

logger = logging.getLogger(__name__)

router = Router(name="sphere_city")


# === FSM States ===

class SphereCityStates(StatesGroup):
    """States for Sphere City flow"""
    entering_custom_city = State()  # Waiting for custom city input


# === Entry Point ===

@router.callback_query(F.data == "sphere_city")
async def sphere_city_entry(callback: CallbackQuery, state: FSMContext):
    """Entry point to Sphere City"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        msg = "Profile not found" if lang == "en" else "Профиль не найден"
        await callback.answer(msg, show_alert=True)
        return

    # Check if user has a city set
    if not user.city_current:
        # Show city picker
        if lang == "ru":
            text = (
                "🏙️ <b>Sphere City</b>\n\n"
                "Выбери свой город, чтобы находить интересных людей рядом.\n\n"
                "В каком городе ты сейчас?"
            )
        else:
            text = (
                "🏙️ <b>Sphere City</b>\n\n"
                "Choose your city to find interesting people nearby.\n\n"
                "What city are you in?"
            )
        await callback.message.edit_text(text, reply_markup=get_city_picker_keyboard(lang, back_callback="back_to_menu"))
    else:
        # Show Sphere City menu
        await show_sphere_city_menu(callback, user, lang)

    await callback.answer()


async def show_sphere_city_menu(callback: CallbackQuery, user, lang: str):
    """Show Sphere City main menu with match count"""

    city_display = user.city_current

    # Try to get localized city name
    for city_key, names in SPHERE_CITIES.items():
        if city_key == user.city_current.lower() or names["en"].lower() == user.city_current.lower():
            city_display = names.get(lang, names["en"])
            break

    # Get city match count
    match_count = await get_city_match_count(user)

    if lang == "ru":
        text = (
            f"🏙️ <b>Sphere City — {city_display}</b>\n\n"
            "Здесь ты найдёшь интересных людей в своём городе.\n"
            "Матчи обновляются каждую неделю.\n\n"
            f"📊 Доступно матчей: <b>{match_count}</b>"
        )
    else:
        text = (
            f"🏙️ <b>Sphere City — {city_display}</b>\n\n"
            "Find interesting people in your city.\n"
            "Matches update weekly.\n\n"
            f"📊 Available matches: <b>{match_count}</b>"
        )

    has_matches = match_count > 0
    await callback.message.edit_text(
        text,
        reply_markup=get_sphere_city_menu_keyboard(has_matches, lang)
    )


async def get_city_match_count(user) -> int:
    """Get count of available city matches for user"""
    try:
        matches = await matching_service.get_city_matches(user.id, user.city_current)
        return len(matches)
    except Exception as e:
        logger.error(f"Error getting city match count: {e}")
        return 0


# === City Selection ===

@router.callback_query(F.data.startswith("city_select_"))
async def handle_city_selection(callback: CallbackQuery, state: FSMContext):
    """Handle city selection from picker"""
    lang = detect_lang(callback)
    city_key = callback.data.replace("city_select_", "")

    if city_key == "other":
        # Ask for custom city input
        if lang == "ru":
            text = "🌍 Напиши название своего города:"
        else:
            text = "🌍 Type your city name:"

        await callback.message.edit_text(text)
        await state.set_state(SphereCityStates.entering_custom_city)
        await callback.answer()
        return

    # Get city name
    city_names = SPHERE_CITIES.get(city_key)
    if city_names:
        city_name = city_names["en"]  # Store English name for consistency
    else:
        city_name = city_key

    # Clear any leftover state
    await state.clear()

    # Save city to user profile
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        city_current=city_name
    )

    # Get updated user
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if lang == "ru":
        await callback.answer(f"✅ Город сохранён: {city_names.get('ru', city_name)}")
    else:
        await callback.answer(f"✅ City saved: {city_name}")

    # Show Sphere City menu
    await show_sphere_city_menu(callback, user, lang)


@router.message(SphereCityStates.entering_custom_city, F.text)
async def handle_custom_city(message: Message, state: FSMContext):
    """Handle custom city input"""
    lang = "en"  # Always use English

    city_name = message.text.strip()[:100]

    if len(city_name) < 2:
        if lang == "ru":
            await message.answer("Название города слишком короткое. Попробуй ещё раз:")
        else:
            await message.answer("City name is too short. Try again:")
        return

    # Save city to user profile
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id),
        city_current=city_name
    )

    await state.clear()

    # Get user
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(message.from_user.id)
    )

    if lang == "ru":
        text = (
            f"✅ Город сохранён: <b>{city_name}</b>\n\n"
            "🏙️ Теперь ты в Sphere City!"
        )
    else:
        text = (
            f"✅ City saved: <b>{city_name}</b>\n\n"
            "🏙️ You're now in Sphere City!"
        )

    # Get match count
    match_count = await get_city_match_count(user)
    has_matches = match_count > 0

    await message.answer(text, reply_markup=get_sphere_city_menu_keyboard(has_matches, lang))


# === City Matches ===

@router.callback_query(F.data == "sphere_city_matches")
async def show_city_matches(callback: CallbackQuery, state: FSMContext):
    """Show city-based matches using the shared match display"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user or not user.city_current:
        msg = "Set your city first" if lang == "en" else "Сначала выбери город"
        await callback.answer(msg, show_alert=True)
        return

    # Use the shared match display with city filter
    from adapters.telegram.handlers.matches import list_matches_callback
    await list_matches_callback(callback, index=0, city=user.city_current, state=state)


# === Cities List ===

@router.callback_query(F.data == "sphere_city_cities")
async def show_cities(callback: CallbackQuery):
    """Show city picker to browse/select a city"""
    lang = detect_lang(callback)

    if lang == "ru":
        text = "🏙 <b>Города</b>\n\nВыбери город, чтобы найти людей:"
    else:
        text = "🏙 <b>Cities</b>\n\nPick a city to find people:"

    await callback.message.edit_text(
        text,
        reply_markup=get_city_picker_keyboard(lang, back_callback="sphere_city")
    )
    await callback.answer()


# === Change City ===

@router.callback_query(F.data == "sphere_city_change")
async def change_city(callback: CallbackQuery):
    """Show city picker to change city"""
    lang = detect_lang(callback)

    if lang == "ru":
        text = "📍 Выбери новый город:"
    else:
        text = "📍 Choose a new city:"

    await callback.message.edit_text(
        text,
        reply_markup=get_city_picker_keyboard(lang, back_callback="sphere_city")
    )
    await callback.answer()
