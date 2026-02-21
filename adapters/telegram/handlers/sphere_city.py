"""
Sphere City Handler - City-based matching outside events.

Flow:
1. User clicks "🏙️ Sphere City" in matches menu
2. If no city_current → show city picker
3. Show onboarding message explaining Sphere City
4. Show city-based matches
"""

import logging
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.domain.models import MessagePlatform
from adapters.telegram.loader import user_service, matching_service, bot, voice_service
from adapters.telegram.keyboards.inline import (
    get_city_picker_keyboard,
    get_sphere_city_menu_keyboard,
    get_back_to_menu_keyboard,
    get_main_menu_keyboard,
    get_global_menu_keyboard,
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
    await callback.answer()  # Answer immediately to prevent Telegram loading spinner
    lang = detect_lang(callback)

    try:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(callback.from_user.id)
        )
    except Exception as e:
        logger.error(f"Sphere City entry DB error: {e}")
        await callback.message.edit_text(
            "Something went wrong. Try again." if lang == "en" else "Что-то пошло не так. Попробуй ещё раз.",
            reply_markup=get_back_to_menu_keyboard(lang)
        )
        return

    if not user:
        try:
            await callback.message.edit_text(
                "Profile not found" if lang == "en" else "Профиль не найден",
                reply_markup=get_back_to_menu_keyboard(lang)
            )
        except Exception:
            pass
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
        try:
            await callback.message.edit_text(text, reply_markup=get_city_picker_keyboard(lang))
        except Exception:
            pass
    else:
        # Show Sphere City menu
        try:
            await show_sphere_city_menu(callback, user, lang)
        except Exception as e:
            logger.error(f"Sphere City menu error: {e}")
            try:
                await callback.message.edit_text(
                    "Something went wrong. Try again." if lang == "en" else "Что-то пошло не так. Попробуй ещё раз.",
                    reply_markup=get_back_to_menu_keyboard(lang)
                )
            except Exception:
                pass


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
    """Get count of users in the same city (potential matches)."""
    if not user or not user.city_current:
        return 0
    from infrastructure.database.user_repository import SupabaseUserRepository
    user_repo = SupabaseUserRepository()
    try:
        candidates = await user_repo.get_users_by_city(
            city=user.city_current,
            exclude_user_id=user.id,
            limit=100
        )
        return len(candidates)
    except Exception:
        return 0


# === City Selection ===

@router.callback_query(F.data.startswith("city_select_"))
async def handle_city_selection(callback: CallbackQuery, state: FSMContext):
    """Handle city selection from picker"""
    lang = detect_lang(callback)
    city_key = callback.data.replace("city_select_", "")

    if city_key == "other":
        # Ask for custom city input with back button
        if lang == "ru":
            text = "🌍 Напиши название своего города:"
        else:
            text = "🌍 Type your city name:"

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        back_builder = InlineKeyboardBuilder()
        back_text = "◀️ Pick from list" if lang == "en" else "◀️ Выбрать из списка"
        back_builder.button(text=back_text, callback_data="sphere_city_change")
        await callback.message.edit_text(text, reply_markup=back_builder.as_markup())
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
        display = city_names.get('ru', city_name) if city_names else city_name
        await callback.answer(f"✅ Город сохранён: {display}")
    else:
        await callback.answer(f"✅ City saved: {city_name}")

    # Show Sphere City menu
    await show_sphere_city_menu(callback, user, lang)


@router.message(SphereCityStates.entering_custom_city, F.voice)
async def handle_custom_city_voice(message: Message, state: FSMContext):
    """Handle voice city name — transcribe and treat as text."""
    try:
        await bot.send_chat_action(message.chat.id, "typing")
        file_info = await bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        transcript = await voice_service.download_and_transcribe(file_url)
        if transcript and transcript.strip():
            message.text = transcript.strip()
            await handle_custom_city(message, state)
            return
    except Exception as e:
        logger.error(f"City voice transcription failed: {e}", exc_info=True)

    lang = detect_lang(message)
    err = "Не удалось распознать. Попробуй ещё раз:" if lang == "ru" else "Couldn't recognize. Try again:"
    await message.answer(err)


@router.message(SphereCityStates.entering_custom_city, F.text)
async def handle_custom_city(message: Message, state: FSMContext):
    """Handle custom city input"""
    lang = detect_lang(message)

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
    """Show city-based matches using the rich card viewer"""
    from adapters.telegram.handlers.matches import list_matches_callback
    await list_matches_callback(callback, match_scope="city", state=state)


# === Change City ===

@router.callback_query(F.data == "sphere_city_change")
async def change_city(callback: CallbackQuery):
    """Show city picker to change city"""
    lang = detect_lang(callback)

    if lang == "ru":
        text = "📍 Выбери новый город:"
    else:
        text = "📍 Choose a new city:"

    await callback.message.edit_text(text, reply_markup=get_city_picker_keyboard(lang))
    await callback.answer()


# === GLOBAL MATCHING ===

@router.callback_query(F.data == "global_matches_entry")
async def global_entry(callback: CallbackQuery):
    """Entry point for global matching"""
    await callback.answer()
    lang = detect_lang(callback)

    try:
        user = await user_service.get_user_by_platform(
            MessagePlatform.TELEGRAM,
            str(callback.from_user.id)
        )
    except Exception as e:
        logger.error(f"Global entry DB error: {e}")
        try:
            await callback.message.edit_text(
                "Something went wrong. Try again." if lang == "en" else "Что-то пошло не так.",
                reply_markup=get_back_to_menu_keyboard(lang)
            )
        except Exception:
            pass
        return

    if not user:
        try:
            await callback.message.edit_text(
                "Profile not found" if lang == "en" else "Профиль не найден",
                reply_markup=get_back_to_menu_keyboard(lang)
            )
        except Exception:
            pass
        return

    # Auto-set matching_scope to global when entering
    if user.matching_scope != "global":
        await user_service.update_user(
            MessagePlatform.TELEGRAM,
            str(callback.from_user.id),
            matching_scope="global"
        )

    # Get real global candidate count
    from infrastructure.database.user_repository import SupabaseUserRepository
    user_repo = SupabaseUserRepository()
    try:
        candidates = await user_repo.get_global_candidates(
            exclude_user_id=user.id, limit=100
        )
        match_count = len(candidates)
    except Exception:
        match_count = 0

    meeting_badge = ""
    if user.meeting_preference == "online":
        meeting_badge = " 🌐 Online"
    elif user.meeting_preference == "offline":
        meeting_badge = " 📍 Offline"
    else:
        meeting_badge = " 🌐 Online & Offline"

    if lang == "ru":
        text = (
            f"🌍 <b>Глобальный Матчинг</b>{meeting_badge}\n\n"
            "Находи интересных людей по всему миру.\n"
            "Общайтесь онлайн или встречайтесь, если вы в одном городе.\n\n"
            f"📊 Доступно матчей: <b>{match_count}</b>"
        )
    else:
        text = (
            f"🌍 <b>Global Matching</b>{meeting_badge}\n\n"
            "Find interesting people around the world.\n"
            "Connect online or meet IRL if you're in the same city.\n\n"
            f"📊 Available matches: <b>{match_count}</b>"
        )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_global_menu_keyboard(match_count, lang)
        )
    except Exception:
        pass


@router.callback_query(F.data == "global_matches_view")
async def show_global_matches(callback: CallbackQuery, state: FSMContext):
    """Show global matches using the rich card viewer"""
    from adapters.telegram.handlers.matches import list_matches_callback
    await list_matches_callback(callback, match_scope="global", state=state)


@router.callback_query(F.data == "toggle_scope")
async def toggle_scope(callback: CallbackQuery):
    """Toggle matching scope between city and global"""
    lang = detect_lang(callback)

    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Profile not found", show_alert=True)
        return

    new_scope = "global" if user.matching_scope == "city" else "city"
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id),
        matching_scope=new_scope
    )

    if new_scope == "global":
        await global_entry(callback)
    else:
        await sphere_city_entry(callback, None)
