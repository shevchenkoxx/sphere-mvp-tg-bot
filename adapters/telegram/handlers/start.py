"""
Start handler - /start command and main menu.
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
            # Check if onboarding completed
            if not user.onboarding_completed:
                # Save event code for joining after onboarding
                await state.update_data(pending_event=event_code)
                await message.answer(
                    f"Привет! Ты хочешь присоединиться к <b>{event.name}</b>.\n\n"
                    "Для этого давай быстро познакомимся — мне нужно узнать о тебе немного больше, "
                    "чтобы найти тебе интересные знакомства!\n\n"
                    "Как тебя зовут?"
                )
                await state.set_state(OnboardingStates.waiting_name)
            else:
                # Show event info and join button
                await message.answer(
                    f"<b>{event.name}</b>\n\n"
                    f"{event.location or 'Локация не указана'}\n"
                    f"{event.description or ''}\n\n"
                    "Хочешь присоединиться?",
                    reply_markup=get_join_event_keyboard(event_code)
                )
        else:
            await message.answer(
                "К сожалению, ивент не найден или уже завершился.\n\n"
                "Используй /menu для просмотра доступных функций."
            )
    else:
        # Regular /start
        await start_command(message, state)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Handle regular /start"""
    user = await user_service.get_or_create_user(
        platform=MessagePlatform.TELEGRAM,
        platform_user_id=str(message.from_user.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    if user.onboarding_completed:
        name = user.display_name or message.from_user.first_name
        await message.answer(
            f"С возвращением, <b>{name}</b>!\n\n"
            "Выбери, что хочешь сделать:",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer(
            "Привет! Я <b>Sphere</b> — помогу тебе найти интересных людей!\n\n"
            "Чтобы начать, мне нужно узнать о тебе немного больше. "
            "Это займёт пару минут.\n\n"
            "Как тебя зовут?"
        )
        await state.set_state(OnboardingStates.waiting_name)


@router.message(Command("menu"))
async def menu_command(message: Message):
    """Show main menu"""
    await message.answer(
        "<b>Главное меню</b>\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("help"))
async def help_command(message: Message):
    """Show help"""
    await message.answer(
        "<b>Sphere — умные знакомства</b>\n\n"
        "Сканируй QR-коды на ивентах\n"
        "Получай персональные матчи\n"
        "Общайся с интересными людьми\n\n"
        "<b>Команды:</b>\n"
        "/start — начать\n"
        "/menu — главное меню\n"
        "/profile — мой профиль\n"
        "/matches — мои матчи\n"
        "/help — эта справка"
    )


# === MAIN MENU CALLBACKS ===

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Return to main menu"""
    await callback.message.edit_text(
        "<b>Главное меню</b>\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_profile")
async def show_profile(callback: CallbackQuery):
    """Show user profile"""
    user = await user_service.get_user_by_platform(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not user:
        await callback.answer("Профиль не найден", show_alert=True)
        return

    interests = ', '.join([get_interest_display(i) for i in user.interests]) or 'Не указаны'
    goals = ', '.join([get_goal_display(g) for g in user.goals]) or 'Не указаны'

    await callback.message.edit_text(
        f"<b>Твой профиль</b>\n\n"
        f"<b>Имя:</b> {user.display_name or 'Не указано'}\n"
        f"<b>Город:</b> {user.city_current or 'Не указан'}\n"
        f"<b>Интересы:</b> {interests}\n"
        f"<b>Цели:</b> {goals}\n"
        f"<b>О себе:</b> {user.bio or 'Не заполнено'}",
        reply_markup=get_back_to_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_events")
async def show_events(callback: CallbackQuery):
    """Show user's events"""
    events = await event_service.get_user_events(
        MessagePlatform.TELEGRAM,
        str(callback.from_user.id)
    )

    if not events:
        await callback.message.edit_text(
            "<b>Твои ивенты</b>\n\n"
            "У тебя пока нет ивентов.\n"
            "Сканируй QR-коды на мероприятиях, чтобы присоединиться!",
            reply_markup=get_back_to_menu_keyboard()
        )
    else:
        text = "<b>Твои ивенты</b>\n\n"
        for event in events:
            text += f"• {event.name}\n"

        await callback.message.edit_text(text, reply_markup=get_back_to_menu_keyboard())

    await callback.answer()


@router.callback_query(F.data == "my_matches")
async def show_matches_menu(callback: CallbackQuery):
    """Show matches (redirect to matches handler)"""
    from adapters.telegram.handlers.matches import list_matches_callback
    await list_matches_callback(callback)
