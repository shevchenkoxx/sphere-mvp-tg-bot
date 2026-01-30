"""
Start handler - /start command and main menu.
Fast, friendly, conversational.
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

router = Router()


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
            if not user.onboarding_completed:
                # Save event code, start quick onboarding
                await state.update_data(pending_event=event_code)
                await message.answer(
                    f"👋 Привет! Ты на <b>{event.name}</b>\n\n"
                    "Давай быстро познакомимся — займёт 1 минуту!\n\n"
                    "Как тебя зовут?"
                )
                await state.set_state(OnboardingStates.waiting_name)
            else:
                await message.answer(
                    f"🎉 <b>{event.name}</b>\n\n"
                    f"📍 {event.location or ''}\n\n"
                    "Присоединяйся!",
                    reply_markup=get_join_event_keyboard(event_code)
                )
        else:
            await message.answer("Упс, ивент не найден 😕")
    else:
        await start_command(message, state)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle regular /start - quick and friendly"""
    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(message.from_user.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    if user.onboarding_completed:
        name = user.display_name or message.from_user.first_name or "друг"
        await message.answer(
            f"👋 {name}!\n\n"
            "Что делаем?",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer(
            "👋 Привет! Я помогу найти интересных людей.\n\n"
            "Займёт 1 минуту. Как тебя зовут?"
        )
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
        "/menu — меню"
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
