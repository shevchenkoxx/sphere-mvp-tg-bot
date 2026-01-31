"""
Start handler - /start command and main menu.
Fast, friendly, conversational.
Multilingual: English default, Russian supported.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext

from core.domain.models import MessagePlatform
from core.domain.constants import get_interest_display, get_goal_display
from adapters.telegram.loader import user_service, event_service, bot
from adapters.telegram.keyboards import (
    get_main_menu_keyboard,
    get_join_event_keyboard,
    get_back_to_menu_keyboard,
)
from adapters.telegram.states import OnboardingStates
from adapters.telegram.config import ONBOARDING_VERSION

router = Router()


def detect_lang(message: Message) -> str:
    """Detect language from Telegram settings. Default: English."""
    lang_code = message.from_user.language_code or "en"
    return "ru" if lang_code.startswith(("ru", "uk")) else "en"


@router.message(CommandStart(deep_link=True))
async def start_with_deep_link(message: Message, command: CommandObject, state: FSMContext):
    """Handle /start with deep link (QR code entry)"""
    args = command.args

    # Get or create user
    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(message.from_user.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    # Check if deep link is for event
    if args and args.startswith("event_"):
        event_code = args.replace("event_", "")
        event = await event_service.get_event_by_code(event_code)

        if event:
            lang = detect_lang(message)
            if not user.onboarding_completed:
                # Start onboarding with event context
                if ONBOARDING_VERSION == "audio":
                    from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
                    await start_audio_onboarding(
                        message, state,
                        event_name=event.name,
                        event_code=event_code
                    )
                elif ONBOARDING_VERSION == "v2":
                    from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
                    await start_conversational_onboarding(
                        message, state,
                        event_name=event.name,
                        event_code=event_code
                    )
                else:
                    # Legacy v1 flow
                    await state.update_data(pending_event=event_code, language=lang)
                    if lang == "ru":
                        text = f"👋 Привет! Ты на <b>{event.name}</b>\n\nДавай познакомимся! Как тебя зовут?"
                    else:
                        text = f"👋 Hi! You're at <b>{event.name}</b>\n\nLet's get to know each other! What's your name?"
                    await message.answer(text)
                    await state.set_state(OnboardingStates.waiting_name)
            else:
                if lang == "ru":
                    text = f"🎉 <b>{event.name}</b>\n\n📍 {event.location or ''}\n\nПрисоединяйся!"
                else:
                    text = f"🎉 <b>{event.name}</b>\n\n📍 {event.location or ''}\n\nJoin the event!"
                await message.answer(text, reply_markup=get_join_event_keyboard(event_code))
        else:
            lang = detect_lang(message)
            await message.answer("Event not found 😕" if lang == "en" else "Ивент не найден 😕")
    else:
        await start_command(message, state)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle regular /start - quick and friendly"""
    lang = detect_lang(message)

    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(message.from_user.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    if user.onboarding_completed:
        name = user.display_name or message.from_user.first_name or ("friend" if lang == "en" else "друг")
        text = f"👋 {name}!\n\n" + ("What would you like to do?" if lang == "en" else "Что делаем?")
        await message.answer(text, reply_markup=get_main_menu_keyboard(lang))
    else:
        # Start onboarding
        if ONBOARDING_VERSION == "audio":
            from adapters.telegram.handlers.onboarding_audio import start_audio_onboarding
            await start_audio_onboarding(message, state)
        elif ONBOARDING_VERSION == "v2":
            from adapters.telegram.handlers.onboarding_v2 import start_conversational_onboarding
            await start_conversational_onboarding(message, state)
        else:
            # Legacy v1 flow
            await state.update_data(language=lang)
            if lang == "ru":
                text = "👋 Привет! Я помогу найти интересных людей.\n\nКак тебя зовут?"
            else:
                text = "👋 Hi! I help you find interesting people to meet.\n\nWhat's your name?"
            await message.answer(text)
            await state.set_state(OnboardingStates.waiting_name)


@router.message(Command("menu"))
async def menu_command(message: Message):
    """Show main menu"""
    await message.answer("Что делаем?", reply_markup=get_main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message):
    """Show help - short and clear"""
    await message.answer(
        "<b>Sphere</b> — умные знакомства на ивентах\n\n"
        "📱 Сканируй QR → получай матчи → общайся\n\n"
        "/start — начать\n"
        "/menu — меню\n"
        "/reset — сбросить профиль (тест)"
    )


@router.message(Command("reset"))
async def reset_command(message: Message, state: FSMContext):
    """Reset user profile for testing"""
    from config.settings import settings

    user_id = str(message.from_user.id)

    # Check if admin or debug mode
    is_admin = message.from_user.id in settings.admin_telegram_ids
    is_debug = settings.debug

    if not is_admin and not is_debug:
        await message.answer("⛔ Команда доступна только админам")
        return

    # Reset user onboarding status
    await user_service.update_user(
        MessagePlatform.TELEGRAM,
        user_id,
        onboarding_completed=False
    )

    # Clear FSM state
    await state.clear()

    await message.answer(
        "🔄 Профиль сброшен!\n\n"
        "Напиши /start чтобы начать заново."
    )


# === MAIN MENU CALLBACKS ===

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Return to main menu"""
    await callback.message.edit_text(
        "Что делаем?",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_profile")
async def show_profile(callback: CallbackQuery):
    """Show user profile - compact"""
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    interests = ', '.join([get_interest_display(i) for i in user.interests[:3]]) or '—'
    goals = ', '.join([get_goal_display(g) for g in user.goals[:2]]) or '—'

    text = (
        f"<b>{user.display_name or 'Аноним'}</b>\n\n"
        f"🎯 {interests}\n"
        f"🎪 {goals}\n"
    )
    if user.bio:
        text += f"\n<i>{user.bio[:100]}{'...' if len(user.bio) > 100 else ''}</i>"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "my_events")
async def show_events(callback: CallbackQuery):
    """Show user's events"""
    events = await event_service.get_user_events(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not events:
        text = "Пока нет ивентов.\nСканируй QR-коды чтобы присоединиться!"
    else:
        text = "<b>Твои ивенты:</b>\n\n"
        for event in events[:5]:
            text += f"• {event.name}\n"

    await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "my_matches")
async def show_matches_menu(callback: CallbackQuery):
    """Show matches"""
    from adapters.telegram.handlers.matches import list_matches_callback
    await list_matches_callback(callback)


# === FALLBACK FOR OLD/STALE CALLBACKS ===
# Note: Audio callbacks (audio_ready, audio_confirm, etc.) are handled by onboarding_audio.py
# Only catch them here if user is NOT in any onboarding state

@router.callback_query(F.data.in_(["audio_ready", "audio_confirm", "audio_retry", "switch_to_text"]))
async def stale_audio_callback(callback: CallbackQuery, state: FSMContext):
    """Handle clicks on old audio onboarding buttons - only when NOT in onboarding"""
    current_state = await state.get_state()

    # If user is in any onboarding state, don't handle here - let onboarding handlers do it
    if current_state and ("AudioOnboarding" in current_state or "Onboarding" in current_state):
        return  # Let the actual onboarding handler process this

    # Otherwise it's a stale button
    await callback.answer("Эта кнопка устарела. Напиши /start", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
